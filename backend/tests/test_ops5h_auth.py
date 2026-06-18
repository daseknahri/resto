"""
OPS-5h customer-login hardening tests for accounts/views.py.

Covers three adjacent auth weaknesses on the customer-login surface:

  A) Session fixation — every customer-login finalizer (phone / Google / email) must
     rotate the session id via session.cycle_key() BEFORE writing customer_id, so a
     pre-auth / planted session id (SESSION_COOKIE_DOMAIN is shared across tenant
     subdomains) can't survive the privilege jump.

  B) SMS/email toll fraud — the OTP *request* views must enforce a per-RECIPIENT
     resend cooldown and an hourly cap, independent of the IP-keyed DRF throttle, and
     refuse (without sending, without resetting the verify attempt counter) when either
     is exceeded.

  C) CSPRNG — phone/email OTPs (full login credentials) must be drawn from the secrets
     module, not the non-CSPRNG random.randint.

All tests are unit-level (SimpleTestCase + mocks — no real DB / cache / network I/O).
"""
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    CustomerEmailRequestView,
    CustomerEmailVerifyView,
    CustomerGoogleAuthView,
    CustomerPhoneRequestView,
    CustomerPhoneVerifyView,
    _otp_recipient_guard,
    _otp_recipient_mark_sent,
    _rotate_customer_session,
    _OTP_RECIPIENT_MAX_PER_HOUR,
    _OTP_RESEND_COOLDOWN,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(**kwargs):
    defaults = dict(
        pk=1, id=1, name="Alice", email="alice@example.com", phone="+21261234567",
        phone_verified=True, email_verified=False, google_sub=None,
        wallet_balance=0, loyalty_points=0, lifetime_loyalty_points=0, birthday=None,
        locale="en", is_driver=False,
        is_driver_online=False, notify_order_updates=True,
        notify_review_prompts=True, notify_promotions=True,
        referral_code="ABCD1234", referral_reward_given=False,
        phone_digits="261234567",
    )
    defaults.update(kwargs)
    c = SimpleNamespace(**defaults)
    c.save = MagicMock()
    return c


class _RecordingSession:
    """A session double that records the relative order of cycle_key() vs the
    customer_id write, so a finalizer that rotates *after* (or never) is caught."""

    def __init__(self, customer_id=None):
        self._d = {}
        if customer_id is not None:
            self._d["customer_id"] = customer_id
        self.events = []
        self.cycle_key = MagicMock(side_effect=lambda: self.events.append("cycle"))

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __setitem__(self, key, value):
        if key == "customer_id":
            self.events.append("set_customer_id")
        self._d[key] = value

    def __getitem__(self, key):
        return self._d[key]

    def pop(self, key, default=None):
        return self._d.pop(key, default)


def _free_cache_mock():
    """cache double where the per-recipient guard sees an unthrottled recipient:
    no prior count (get → None) and a free cooldown slot (add → True)."""
    m = MagicMock()
    m.get.return_value = None
    m.add.return_value = True
    return m


# ══════════════════════════════════════════════════════════════════════════════
# A) Session fixation — finalizers rotate before login
# ══════════════════════════════════════════════════════════════════════════════

class SessionRotationHelperTests(SimpleTestCase):
    def test_cycle_key_called_when_session_present(self):
        req = SimpleNamespace(session=MagicMock())
        _rotate_customer_session(req)
        req.session.cycle_key.assert_called_once()

    def test_noop_when_no_session(self):
        # Must not raise when there is no session object (guard requirement).
        _rotate_customer_session(SimpleNamespace(session=None))
        _rotate_customer_session(SimpleNamespace())


class PhoneVerifyRotatesSessionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_rotates_session_before_setting_customer_id(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        objects_mock.get_or_create.return_value = (_make_customer(), True)
        sess = _RecordingSession()
        req = self.factory.post(
            "/api/customer/auth/phone/verify/",
            {"phone": "+21261234567", "code": "123456"}, format="json",
        )
        req.session = sess
        resp = CustomerPhoneVerifyView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sess.cycle_key.assert_called_once()
        # Rotation must happen BEFORE the customer_id write.
        self.assertEqual(sess.events, ["cycle", "set_customer_id"])


class GoogleAuthRotatesSessionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.views._verify_google_token")
    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_rotates_session_before_setting_customer_id(self, cache_mock, objects_mock, verify_mock):
        verify_mock.return_value = {"sub": "g-sub-1", "email": "a@b.co", "name": "A"}
        objects_mock.filter.return_value.first.return_value = None
        objects_mock.filter.return_value.exclude.return_value.first.return_value = None
        objects_mock.create.return_value = _make_customer(google_sub="g-sub-1")
        sess = _RecordingSession()
        req = self.factory.post(
            "/api/customer/auth/google/", {"credential": "tok"}, format="json",
        )
        req.session = sess
        with self.settings(GOOGLE_OAUTH_CLIENT_ID="client-123"):
            resp = CustomerGoogleAuthView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sess.cycle_key.assert_called_once()
        self.assertEqual(sess.events, ["cycle", "set_customer_id"])


class EmailVerifyRotatesSessionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_rotates_session_before_setting_customer_id(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        objects_mock.filter.return_value.first.return_value = None
        objects_mock.create.return_value = _make_customer(email="a@b.co")
        sess = _RecordingSession()
        req = self.factory.post(
            "/api/customer/auth/email/verify/",
            {"email": "a@b.co", "code": "123456"}, format="json",
        )
        req.session = sess
        resp = CustomerEmailVerifyView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sess.cycle_key.assert_called_once()
        self.assertEqual(sess.events, ["cycle", "set_customer_id"])


# ══════════════════════════════════════════════════════════════════════════════
# B) Toll fraud — per-recipient cooldown + hourly cap
# ══════════════════════════════════════════════════════════════════════════════

class OtpRecipientGuardTests(SimpleTestCase):
    @patch("accounts.views.cache")
    def test_allows_first_send(self, cache_mock):
        cache_mock.get.return_value = None       # no count yet
        cache_mock.add.return_value = True        # cooldown free
        self.assertIsNone(_otp_recipient_guard("+21261234567"))

    @patch("accounts.views.cache")
    def test_refuses_within_cooldown(self, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = False       # key already present → cooling down
        resp = _otp_recipient_guard("+21261234567")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_cooldown")

    @patch("accounts.views.cache")
    def test_refuses_over_hourly_cap(self, cache_mock):
        cache_mock.get.return_value = _OTP_RECIPIENT_MAX_PER_HOUR  # at the cap
        resp = _otp_recipient_guard("+21261234567")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_rate_limited")
        # Over the cap we must not even arm the cooldown / attempt a send.
        cache_mock.add.assert_not_called()

    @patch("accounts.views.cache")
    def test_mark_sent_increments_count(self, cache_mock):
        cache_mock.get.return_value = 2
        _otp_recipient_mark_sent("+21261234567")
        cache_mock.set.assert_called_once()
        args, _ = cache_mock.set.call_args
        self.assertEqual(args[0], "otp_count:+21261234567")
        self.assertEqual(args[1], 3)              # 2 + 1


class PhoneRequestTollFraudTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        patcher = patch(
            "accounts.views.CustomerOtpRequestThrottle.allow_request", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, cache_mock):
        req = self.factory.post(
            "/api/customer/auth/phone/request/",
            {"phone": "+21261234567"}, format="json",
        )
        req.session = MagicMock()
        return CustomerPhoneRequestView.as_view()(req)

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_cooldown_refuses_and_does_not_send(self, send_mock, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = False       # within cooldown
        resp = self._post(cache_mock)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_cooldown")
        send_mock.assert_not_called()
        # Must NOT store/reset the OTP record (which would zero the verify counter).
        cache_mock.set.assert_not_called()

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_over_cap_refuses_and_does_not_send(self, send_mock, cache_mock):
        cache_mock.get.return_value = _OTP_RECIPIENT_MAX_PER_HOUR
        resp = self._post(cache_mock)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_rate_limited")
        send_mock.assert_not_called()
        cache_mock.set.assert_not_called()

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_allowed_send_increments_recipient_count(self, send_mock, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = True
        resp = self._post(cache_mock)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        send_mock.assert_called_once()
        # The OTP record AND the per-recipient count were both written.
        keys_set = [c.args[0] for c in cache_mock.set.call_args_list]
        self.assertIn("customer_otp:+21261234567", keys_set)
        self.assertIn("otp_count:+21261234567", keys_set)


class EmailRequestTollFraudTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # Don't let the IP-keyed DRF throttle (real Django cache, shared across the test
        # session) shadow the per-recipient guard we're exercising here.
        patcher = patch(
            "accounts.views.CustomerEmailOtpRequestThrottle.allow_request", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self):
        req = self.factory.post(
            "/api/customer/auth/email/request/",
            {"email": "victim@example.com"}, format="json",
        )
        req.session = MagicMock()
        return CustomerEmailRequestView.as_view()(req)

    @patch("accounts.views.cache")
    def test_cooldown_refuses_and_does_not_send(self, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = False
        with patch("accounts.messaging.send_otp_email", MagicMock()) as send_mock:
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_cooldown")
        send_mock.assert_not_called()
        cache_mock.set.assert_not_called()

    @patch("accounts.views.cache")
    def test_over_cap_refuses_and_does_not_send(self, cache_mock):
        cache_mock.get.return_value = _OTP_RECIPIENT_MAX_PER_HOUR
        with patch("accounts.messaging.send_otp_email", MagicMock()) as send_mock:
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "otp_rate_limited")
        send_mock.assert_not_called()
        cache_mock.set.assert_not_called()

    @patch("accounts.views.cache")
    def test_allowed_send_increments_recipient_count(self, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = True
        with patch("accounts.messaging.send_otp_email", MagicMock()) as send_mock:
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        send_mock.assert_called_once()
        keys_set = [c.args[0] for c in cache_mock.set.call_args_list]
        self.assertIn("customer_email_otp:victim@example.com", keys_set)
        self.assertIn("otp_count:victim@example.com", keys_set)


# ══════════════════════════════════════════════════════════════════════════════
# C) CSPRNG — OTPs come from secrets, not random.randint
# ══════════════════════════════════════════════════════════════════════════════

class OtpCsprngSourceTests(SimpleTestCase):
    def test_phone_request_does_not_use_random_randint(self):
        src = inspect.getsource(CustomerPhoneRequestView)
        self.assertEqual(src.count("random.randint"), 0)
        self.assertIn("secrets.randbelow", src)

    def test_email_request_does_not_use_random_randint(self):
        src = inspect.getsource(CustomerEmailRequestView)
        self.assertEqual(src.count("random.randint"), 0)
        self.assertIn("secrets.randbelow", src)

    def test_module_no_longer_imports_random(self):
        import accounts.views as views_mod
        self.assertFalse(hasattr(views_mod, "random"))

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_phone_otp_is_six_digit_string(self, send_mock, cache_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = True
        factory = APIRequestFactory()
        with patch("accounts.views.CustomerOtpRequestThrottle.allow_request", return_value=True):
            req = factory.post(
                "/api/customer/auth/phone/request/",
                {"phone": "+21261234567"}, format="json",
            )
            req.session = MagicMock()
            with self.settings(DEBUG=True):
                resp = CustomerPhoneRequestView.as_view()(req)
        code = str(resp.data["debug_code"])
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertGreaterEqual(int(code), 100000)
        self.assertLessEqual(int(code), 999999)

    @patch("accounts.views.CustomerEmailOtpRequestThrottle.allow_request", return_value=True)
    @patch("accounts.views.cache")
    def test_email_otp_is_six_digit_string(self, cache_mock, throttle_mock):
        cache_mock.get.return_value = None
        cache_mock.add.return_value = True
        factory = APIRequestFactory()
        with patch("accounts.messaging.send_otp_email", MagicMock()):
            req = factory.post(
                "/api/customer/auth/email/request/",
                {"email": "a@b.co"}, format="json",
            )
            req.session = MagicMock()
            with self.settings(DEBUG=True):
                resp = CustomerEmailRequestView.as_view()(req)
        code = str(resp.data["debug_code"])
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())


# Sanity: the cooldown TTL constant exists and is the documented short window.
class OtpGuardConstantsTests(SimpleTestCase):
    def test_cooldown_is_short(self):
        self.assertLessEqual(_OTP_RESEND_COOLDOWN, 120)
        self.assertGreater(_OTP_RESEND_COOLDOWN, 0)

    def test_hourly_cap_is_bounded(self):
        self.assertGreaterEqual(_OTP_RECIPIENT_MAX_PER_HOUR, 1)
        self.assertLessEqual(_OTP_RECIPIENT_MAX_PER_HOUR, 20)
