"""
Tests for the customer authentication layer.

Covers: CustomerSessionView, CustomerPhoneRequestView, CustomerPhoneVerifyView,
CustomerEmailRequestView, CustomerEmailVerifyView, CustomerGoogleAuthView,
CustomerProfileUpdateView, CustomerOrdersView, _serialize_customer.

All tests are unit-level (SimpleTestCase + mocks — no real DB or cache I/O).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    CustomerEmailRequestView,
    CustomerEmailVerifyView,
    CustomerGoogleAuthView,
    CustomerOrdersView,
    CustomerPhoneRequestView,
    CustomerPhoneVerifyView,
    CustomerProfileUpdateView,
    CustomerSessionView,
    _serialize_customer,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(**kwargs):
    defaults = dict(
        pk=1,
        id=1,
        name="Alice",
        email="alice@example.com",
        phone="+21261234567",
        phone_verified=True,
        email_verified=False,
        google_sub=None,
        wallet_balance=0,
        loyalty_points=0,
        locale="en",
        is_driver=False,
        is_driver_online=False,
        notify_order_updates=True,
        notify_review_prompts=True,
    )
    defaults.update(kwargs)
    c = SimpleNamespace(**defaults)
    c.save = MagicMock()
    return c


def _session(customer_id=None):
    d = {}
    if customer_id is not None:
        d["customer_id"] = customer_id
    sess = MagicMock()
    sess.get = lambda key, default=None: d.get(key, default)
    sess.__setitem__ = lambda s, key, value: d.__setitem__(key, value)
    sess.pop = lambda key, default=None: d.pop(key, default)
    return sess


# ── _serialize_customer ───────────────────────────────────────────────────────

class SerializeCustomerTests(SimpleTestCase):
    def test_all_expected_fields_present(self):
        c = _make_customer()
        data = _serialize_customer(c)
        for field in ("id", "name", "email", "phone", "phone_verified", "email_verified", "has_google", "wallet_balance"):
            self.assertIn(field, data, f"Missing field: {field}")

    def test_has_google_false_when_no_google_sub(self):
        c = _make_customer(google_sub=None)
        self.assertFalse(_serialize_customer(c)["has_google"])

    def test_has_google_true_when_google_sub_present(self):
        c = _make_customer(google_sub="google-sub-abc")
        self.assertTrue(_serialize_customer(c)["has_google"])

    def test_phone_defaults_to_empty_string_when_none(self):
        c = _make_customer(phone=None)
        self.assertEqual(_serialize_customer(c)["phone"], "")

    def test_email_included(self):
        c = _make_customer(email="test@example.com")
        self.assertEqual(_serialize_customer(c)["email"], "test@example.com")

    def test_wallet_balance_serialized_as_string(self):
        c = _make_customer(wallet_balance=42)
        self.assertEqual(_serialize_customer(c)["wallet_balance"], "42")


# ── CustomerSessionView ───────────────────────────────────────────────────────

class CustomerSessionViewGetTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self, session=None):
        req = self.factory.get("/api/customer/session/")
        req.session = session or _session()
        return CustomerSessionView.as_view()(req)

    def test_returns_null_when_no_session(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["customer"])

    @patch("accounts.views.Customer.objects")
    def test_returns_serialized_customer_when_valid(self, objects_mock):
        customer = _make_customer()
        objects_mock.get.return_value = customer
        resp = self._get(session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data["customer"]
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["name"], "Alice")
        self.assertIn("phone_verified", data)
        self.assertIn("email_verified", data)
        self.assertIn("has_google", data)

    @patch("accounts.views.Customer.objects")
    def test_clears_session_on_stale_customer_id(self, objects_mock):
        from accounts.models import Customer
        objects_mock.get.side_effect = Customer.DoesNotExist
        sess = _session(customer_id=99)
        resp = self._get(session=sess)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["customer"])


class CustomerSessionViewDeleteTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_logout_succeeds(self):
        req = self.factory.delete("/api/customer/session/")
        req.session = _session(customer_id=1)
        resp = CustomerSessionView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("ok"))


# ── CustomerPhoneRequestView ──────────────────────────────────────────────────

class CustomerPhoneRequestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # Unit tests should not be constrained by throttle state from other tests.
        patcher = patch("accounts.views.CustomerOtpRequestThrottle.allow_request", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, data):
        req = self.factory.post("/api/customer/auth/phone/request/", data, format="json")
        req.session = _session()
        return CustomerPhoneRequestView.as_view()(req)

    def test_rejects_empty_phone(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_phone_too_long(self):
        resp = self._post({"phone": "+" + "1" * 31})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_phone_without_plus_prefix(self):
        """E.164 requires a leading '+'; bare national numbers must be rejected."""
        resp = self._post({"phone": "0612345678"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_phone")

    def test_rejects_phone_with_letters(self):
        """Non-digit characters other than the leading '+' must be rejected."""
        resp = self._post({"phone": "+212abc5678"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_phone")

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_sends_otp_for_valid_phone(self, send_mock, cache_mock):
        resp = self._post({"phone": "+21261234567"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        cache_mock.set.assert_called_once()
        send_mock.assert_called_once()

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_debug_mode_includes_code_in_response(self, send_mock, cache_mock):
        with self.settings(DEBUG=True):
            resp = self._post({"phone": "+21261234567"})
        self.assertIn("debug_code", resp.data)
        self.assertEqual(len(str(resp.data["debug_code"])), 6)

    @patch("accounts.views.cache")
    @patch("accounts.views._send_otp")
    def test_production_mode_omits_code(self, send_mock, cache_mock):
        with self.settings(DEBUG=False):
            resp = self._post({"phone": "+21261234567"})
        self.assertNotIn("debug_code", resp.data)


# ── CustomerPhoneVerifyView ───────────────────────────────────────────────────

class CustomerPhoneVerifyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, data, session=None):
        req = self.factory.post("/api/customer/auth/phone/verify/", data, format="json")
        req.session = session or _session()
        return CustomerPhoneVerifyView.as_view()(req)

    def test_rejects_missing_fields(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_missing_code(self):
        resp = self._post({"phone": "+21261234567"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.cache")
    def test_rejects_expired_otp(self, cache_mock):
        cache_mock.get.return_value = None
        resp = self._post({"phone": "+21261234567", "code": "123456"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "otp_expired")

    @patch("accounts.views.cache")
    def test_rejects_wrong_code(self, cache_mock):
        cache_mock.get.return_value = {"code": "999999", "attempts": 0}
        resp = self._post({"phone": "+21261234567", "code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_code")
        # Attempts counter should have been incremented and re-cached
        cache_mock.set.assert_called_once()

    @patch("accounts.views.time")
    @patch("accounts.views.cache")
    def test_wrong_code_write_back_uses_remaining_ttl(self, cache_mock, time_mock):
        """Wrong-guess write-back must use remaining TTL, not a fresh 5 min window."""
        # Simulate OTP was created 3 minutes ago (expires in 2 min = 120 s)
        expires_at = 1_000_120.0  # absolute timestamp
        time_mock.time.return_value = 1_000_000.0
        cache_mock.get.return_value = {"code": "999999", "attempts": 0, "expires_at": expires_at}
        self._post({"phone": "+21261234567", "code": "000000"})
        # The timeout kwarg passed to cache.set must be ~120 s (remaining), not 300 s
        _, kwargs = cache_mock.set.call_args
        timeout = kwargs.get("timeout") or cache_mock.set.call_args[0][2]
        self.assertLessEqual(timeout, 120)

    @patch("accounts.views.cache")
    def test_locks_after_max_attempts(self, cache_mock):
        cache_mock.get.return_value = {"code": "999999", "attempts": 5}
        resp = self._post({"phone": "+21261234567", "code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "too_many_attempts")
        cache_mock.delete.assert_called_once()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_creates_customer_on_first_verify(self, cache_mock, objects_mock):
        """get_or_create returns (customer, created=True) the first time."""
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer()
        objects_mock.get_or_create.return_value = (customer, True)
        sess = _session()
        resp = self._post({"phone": "+21261234567", "code": "123456"}, session=sess)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["customer"]["id"], 1)
        # New customer: save() should NOT be called (get_or_create handled it)
        customer.save.assert_not_called()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_updates_existing_customer_on_reverify(self, cache_mock, objects_mock):
        """get_or_create returns (customer, created=False) for existing phone."""
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(phone_verified=False)
        objects_mock.get_or_create.return_value = (customer, False)
        resp = self._post({"phone": "+21261234567", "code": "123456"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Existing customer: save() must be called to persist phone_verified=True
        customer.save.assert_called_once()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_sets_name_on_existing_nameless_customer(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(name="", phone_verified=True)
        objects_mock.get_or_create.return_value = (customer, False)
        resp = self._post({"phone": "+21261234567", "code": "123456", "name": "Bob"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.name, "Bob")

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_does_not_overwrite_existing_name(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(name="Alice", phone_verified=True)
        objects_mock.get_or_create.return_value = (customer, False)
        resp = self._post({"phone": "+21261234567", "code": "123456", "name": "Other"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.name, "Alice")  # unchanged

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_links_phone_to_existing_session_customer(self, cache_mock, objects_mock):
        """When a session customer already exists (e.g. Google/email auth), a verified
        phone should be linked to that existing account rather than creating a new one."""
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        existing = _make_customer(pk=42, phone=None, phone_verified=False)
        objects_mock.get.return_value = existing
        objects_mock.filter.return_value.exclude.return_value.first.return_value = None  # no conflict
        sess = _session(customer_id=42)
        resp = self._post({"phone": "+21261234567", "code": "123456"}, session=sess)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Phone and phone_verified should have been set
        self.assertEqual(existing.phone, "+21261234567")
        self.assertTrue(existing.phone_verified)
        existing.save.assert_called_once()
        # get_or_create should NOT be called — we updated the existing customer
        objects_mock.get_or_create.assert_not_called()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_phone_taken_by_other_account_returns_error(self, cache_mock, objects_mock):
        """If the phone is already registered to a *different* account, return phone_taken."""
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        existing = _make_customer(pk=42, phone=None, phone_verified=False)
        conflict = _make_customer(pk=99, phone="+21261234567", phone_verified=True)
        objects_mock.get.return_value = existing
        objects_mock.filter.return_value.exclude.return_value.first.return_value = conflict
        sess = _session(customer_id=42)
        resp = self._post({"phone": "+21261234567", "code": "123456"}, session=sess)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "phone_taken")
        # Phone must NOT be updated on the existing customer
        existing.save.assert_not_called()


# ── CustomerEmailRequestView ──────────────────────────────────────────────────

class CustomerEmailRequestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, data):
        req = self.factory.post("/api/customer/auth/email/request/", data, format="json")
        req.session = _session()
        return CustomerEmailRequestView.as_view()(req)

    def test_rejects_empty_body(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_missing_at_sign(self):
        resp = self._post({"email": "notanemail"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_email_over_254_chars(self):
        resp = self._post({"email": "a" * 250 + "@x.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.cache")
    def test_sends_otp_for_valid_email(self, cache_mock):
        with patch("accounts.messaging.send_otp_email", MagicMock()) as send_mock:
            req = self.factory.post(
                "/api/customer/auth/email/request/",
                {"email": "test@example.com"},
                format="json",
            )
            req.session = _session()
            resp = CustomerEmailRequestView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        cache_mock.set.assert_called_once()

    @patch("accounts.views.cache")
    def test_debug_mode_includes_code(self, cache_mock):
        with self.settings(DEBUG=True):
            with patch("accounts.messaging.send_otp_email", MagicMock()):
                req = self.factory.post(
                    "/api/customer/auth/email/request/",
                    {"email": "test@example.com"},
                    format="json",
                )
                req.session = _session()
                resp = CustomerEmailRequestView.as_view()(req)
        self.assertIn("debug_code", resp.data)

    @patch("accounts.views.cache")
    def test_production_mode_omits_code(self, cache_mock):
        with self.settings(DEBUG=False):
            with patch("accounts.messaging.send_otp_email", MagicMock()):
                req = self.factory.post(
                    "/api/customer/auth/email/request/",
                    {"email": "test@example.com"},
                    format="json",
                )
                req.session = _session()
                resp = CustomerEmailRequestView.as_view()(req)
        self.assertNotIn("debug_code", resp.data)


# ── CustomerEmailVerifyView ───────────────────────────────────────────────────

class CustomerEmailVerifyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, data, session=None):
        req = self.factory.post("/api/customer/auth/email/verify/", data, format="json")
        req.session = session or _session()
        return CustomerEmailVerifyView.as_view()(req)

    def test_rejects_missing_fields(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_missing_code(self):
        resp = self._post({"email": "a@b.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.cache")
    def test_rejects_expired_otp(self, cache_mock):
        cache_mock.get.return_value = None
        resp = self._post({"email": "a@b.com", "code": "123456"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "otp_expired")

    @patch("accounts.views.cache")
    def test_rejects_wrong_code(self, cache_mock):
        cache_mock.get.return_value = {"code": "999999", "attempts": 0}
        resp = self._post({"email": "a@b.com", "code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_code")

    @patch("accounts.views.cache")
    def test_locks_after_max_attempts(self, cache_mock):
        cache_mock.get.return_value = {"code": "999999", "attempts": 5}
        resp = self._post({"email": "a@b.com", "code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "too_many_attempts")

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_creates_new_customer_on_first_verify(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(pk=5, phone=None, phone_verified=False, email_verified=True)
        objects_mock.filter.return_value.first.return_value = None
        objects_mock.create.return_value = customer
        sess = _session()
        resp = self._post({"email": "new@example.com", "code": "123456"}, session=sess)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        objects_mock.create.assert_called_once()
        self.assertEqual(resp.data["customer"]["id"], 5)

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_marks_existing_customer_email_verified(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(email_verified=False)
        objects_mock.filter.return_value.first.return_value = customer
        resp = self._post({"email": "alice@example.com", "code": "123456"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(customer.email_verified)
        customer.save.assert_called_once()

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_sets_name_on_existing_nameless_customer(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(name="", email_verified=False)
        objects_mock.filter.return_value.first.return_value = customer
        resp = self._post({"email": "alice@example.com", "code": "123456", "name": "Carol"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.name, "Carol")

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views.cache")
    def test_does_not_overwrite_existing_name(self, cache_mock, objects_mock):
        cache_mock.get.return_value = {"code": "123456", "attempts": 0}
        customer = _make_customer(name="Existing", email_verified=False)
        objects_mock.filter.return_value.first.return_value = customer
        resp = self._post({"email": "alice@example.com", "code": "123456", "name": "Other"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.name, "Existing")


# ── CustomerGoogleAuthView ────────────────────────────────────────────────────

class CustomerGoogleAuthViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # The view guards against an unconfigured GOOGLE_OAUTH_CLIENT_ID.
        # Patch settings so all tests that pass a credential reach token verification.
        patcher = patch("accounts.views.settings")
        self.mock_settings = patcher.start()
        self.mock_settings.GOOGLE_OAUTH_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
        self.addCleanup(patcher.stop)

    def _post(self, data, session=None):
        req = self.factory.post("/api/customer/auth/google/", data, format="json")
        req.session = session or _session()
        return CustomerGoogleAuthView.as_view()(req)

    def test_rejects_missing_credential(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views._verify_google_token")
    def test_rejects_invalid_token(self, verify_mock):
        verify_mock.return_value = None
        resp = self._post({"credential": "bad-token"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_credential")

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views._verify_google_token")
    def test_creates_new_customer_for_unknown_google_sub(self, verify_mock, objects_mock):
        verify_mock.return_value = {
            "sub": "google-sub-new",
            "email": "new@google.com",
            "name": "New User",
        }
        new_customer = _make_customer(pk=10, google_sub="google-sub-new", email="new@google.com")
        # filter(google_sub=...).first() → None
        # filter(email=...).exclude(...).first() → None (no email match either)
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        filter_mock.exclude.return_value.first.return_value = None
        objects_mock.filter.return_value = filter_mock
        objects_mock.create.return_value = new_customer

        resp = self._post({"credential": "valid-token"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        objects_mock.create.assert_called_once()
        self.assertTrue(resp.data["customer"]["has_google"])

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views._verify_google_token")
    def test_returns_existing_customer_for_known_google_sub(self, verify_mock, objects_mock):
        verify_mock.return_value = {
            "sub": "google-sub-existing",
            "email": "existing@google.com",
            "name": "Existing",
        }
        existing = _make_customer(pk=7, google_sub="google-sub-existing")
        objects_mock.filter.return_value.first.return_value = existing

        resp = self._post({"credential": "valid-token"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        objects_mock.create.assert_not_called()
        self.assertEqual(resp.data["customer"]["id"], 7)

    @patch("accounts.views.Customer.objects")
    @patch("accounts.views._verify_google_token")
    def test_links_google_sub_to_existing_email_customer(self, verify_mock, objects_mock):
        """Customer who signed up via email now signs in with Google for the first time."""
        verify_mock.return_value = {
            "sub": "google-sub-link",
            "email": "email-user@example.com",
            "name": "Email User",
        }
        email_customer = _make_customer(pk=3, google_sub=None, email="email-user@example.com")

        call_count = [0]

        def filter_side_effect(**kwargs):
            m = MagicMock()
            call_count[0] += 1
            if "google_sub" in kwargs:
                # First call: look up by google_sub → not found
                m.first.return_value = None
            elif "email" in kwargs:
                # Second call: look up by email → found (after .exclude())
                m.exclude.return_value.first.return_value = email_customer
            return m

        objects_mock.filter.side_effect = filter_side_effect

        resp = self._post({"credential": "valid-token"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # google_sub should have been linked
        self.assertEqual(email_customer.google_sub, "google-sub-link")
        email_customer.save.assert_called_once()
        objects_mock.create.assert_not_called()


# ── CustomerProfileUpdateView ─────────────────────────────────────────────────

class CustomerProfileUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _patch(self, data, session=None):
        req = self.factory.patch("/api/customer/profile/", data, format="json")
        req.session = session or _session()
        return CustomerProfileUpdateView.as_view()(req)

    def test_returns_401_when_not_authenticated(self):
        resp = self._patch({"name": "Alice"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.views.Customer.objects")
    def test_returns_404_on_stale_session(self, objects_mock):
        from accounts.models import Customer
        objects_mock.get.side_effect = Customer.DoesNotExist
        resp = self._patch({"name": "Alice"}, session=_session(customer_id=99))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.views.Customer.objects")
    def test_updates_name_successfully(self, objects_mock):
        customer = _make_customer(name="Old")
        objects_mock.get.return_value = customer
        resp = self._patch({"name": "New Name"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.name, "New Name")
        customer.save.assert_called_once()

    @patch("accounts.views.Customer.objects")
    def test_ignores_blank_name_and_does_not_save(self, objects_mock):
        customer = _make_customer(name="Existing")
        objects_mock.get.return_value = customer
        resp = self._patch({"name": "   "}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        customer.save.assert_not_called()

    @patch("accounts.views.Customer.objects")
    def test_truncates_name_to_80_chars(self, objects_mock):
        customer = _make_customer(name="Old")
        objects_mock.get.return_value = customer
        resp = self._patch({"name": "A" * 120}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(customer.name), 80)

    @patch("accounts.views.Customer.objects")
    def test_returns_serialized_customer_after_update(self, objects_mock):
        customer = _make_customer(name="Old")
        objects_mock.get.return_value = customer
        resp = self._patch({"name": "Updated"}, session=_session(customer_id=1))
        self.assertIn("customer", resp.data)
        for field in ("id", "name", "email", "phone", "phone_verified", "email_verified", "has_google"):
            self.assertIn(field, resp.data["customer"])


# ── CustomerOrdersView ────────────────────────────────────────────────────────

class CustomerOrdersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self, session=None, schema_name="demo"):
        req = self.factory.get("/api/customer/orders/")
        req.session = session or _session()
        # Patch django.db.connection since it's imported inside the method
        with patch("django.db.connection") as conn_mock:
            conn_mock.schema_name = schema_name
            return CustomerOrdersView.as_view()(req)

    def test_returns_empty_for_public_schema(self):
        resp = self._get(schema_name="public")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])
        self.assertEqual(resp.data["count"], 0)

    def test_returns_empty_when_not_authenticated(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])

    @patch("accounts.views.Customer.objects")
    def test_returns_empty_when_customer_deleted(self, objects_mock):
        from accounts.models import Customer
        objects_mock.get.side_effect = Customer.DoesNotExist
        resp = self._get(session=_session(customer_id=42))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])

    @patch("accounts.views.Customer.objects")
    def test_returns_orders_for_authenticated_customer(self, objects_mock):
        customer = _make_customer()
        objects_mock.get.return_value = customer

        fake_orders = [
            {
                "order_number": "ABC123",
                "status": "completed",
                "fulfillment_type": "pickup",
                "table_label": "",
                "total": "25.00",
                "currency": "USD",
                "created_at": "2025-01-01T10:00:00Z",
                "customer_name": "Alice",
            }
        ]

        qs_mock = MagicMock()
        qs_mock.__iter__ = MagicMock(return_value=iter(fake_orders))
        qs_mock.__len__ = MagicMock(return_value=1)

        order_manager = MagicMock()
        order_manager.filter.return_value.order_by.return_value.values.return_value.__getitem__ = (
            MagicMock(return_value=fake_orders)
        )

        order_cls = MagicMock()
        order_cls.objects = order_manager

        req = self.factory.get("/api/customer/orders/")
        req.session = _session(customer_id=1)

        import builtins
        real_import = builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name == "menu.models":
                mod = MagicMock()
                mod.Order = order_cls
                return mod
            return real_import(name, *args, **kwargs)

        with patch("django.db.connection") as conn_mock:
            conn_mock.schema_name = "demo"
            with patch("builtins.__import__", _mock_import):
                resp = CustomerOrdersView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("orders", resp.data)
