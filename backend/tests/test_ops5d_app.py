"""OPS-5d Application-Logic Security — Contract Tests

Covers the HIGH-severity application-logic fixes in the OPS-5d batch:

  A. Celery run_management_command allowlist (accounts/tasks.py)
       - an allowlisted command name reaches call_command
       - a disallowed name is logged + dropped (call_command NOT invoked, no raise)

  B. Google One-Tap email_verified enforcement (_verify_google_token, accounts/views.py)
       - tokeninfo string "false" is rejected (returns None)
       - tokeninfo string "true" passes (returns payload)
       - missing email_verified is rejected

  C. AdminWalletBonusView double-credit mutex (accounts/views.py)
       - the 2nd concurrent POST with the same idempotency_key is rejected by the
         cache.add() mutex BEFORE the balance UPDATE runs

  D. Cross-persona session fixation (accounts/views.py)
       - an authenticated staff/owner User is refused (403) on every customer-login
         finalize path (phone OTP verify, Google, email OTP verify)
       - a real customer (AnonymousUser) is NOT blocked by the guard

  E. CustomerReservationsView throttle + cancel_token redaction (accounts/views.py)
       - throttle_classes includes CustomerReservationsThrottle (scope wired in settings)
       - the list payload no longer contains cancel_token

House style: SimpleTestCase + mocks, no real DB.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate


@contextmanager
def _fake_atomic():
    yield


def _anon():
    """A real customer: not a User row → AnonymousUser-like (is_authenticated False)."""
    from django.contrib.auth.models import AnonymousUser
    return AnonymousUser()


def _staff_user(pk=1):
    """A staff/owner authenticated via SessionAuthentication."""
    from accounts.models import User
    u = MagicMock(spec=User)
    u.pk = pk
    u.id = pk
    u.is_authenticated = True
    u.is_active = True
    return u


# ═════════════════════════════════════════════════════════════════════════════
# A. Celery run_management_command allowlist
# ═════════════════════════════════════════════════════════════════════════════

class TestRunManagementCommandAllowlist(SimpleTestCase):
    """Only allowlisted command names may reach django.core.management.call_command."""

    @patch("django.core.management.call_command")
    def test_allowlisted_command_runs(self, mock_call):
        from accounts.tasks import run_management_command
        run_management_command("prune_notification_logs")
        mock_call.assert_called_once_with("prune_notification_logs")

    @patch("django.core.management.call_command")
    def test_allowlisted_command_forwards_args_kwargs(self, mock_call):
        from accounts.tasks import run_management_command
        run_management_command("enforce_subscriptions", apply=True)
        mock_call.assert_called_once_with("enforce_subscriptions", apply=True)

    @patch("accounts.tasks.logger")
    @patch("django.core.management.call_command")
    def test_disallowed_command_is_skipped(self, mock_call, mock_logger):
        """A name outside the allowlist (e.g. 'flush') is logged + dropped, never run."""
        from accounts.tasks import run_management_command
        result = run_management_command("flush")
        self.assertIsNone(result)
        mock_call.assert_not_called()
        mock_logger.warning.assert_called_once()
        # the rejected name must appear in the warning args
        self.assertIn("flush", repr(mock_logger.warning.call_args))

    @patch("django.core.management.call_command")
    def test_shell_like_command_is_skipped(self, mock_call):
        from accounts.tasks import run_management_command
        for evil in ("shell", "dbshell", "migrate", "createsuperuser"):
            run_management_command(evil)
        mock_call.assert_not_called()

    def test_allowlist_matches_beat_schedule(self):
        """Every command scheduled in CELERY_BEAT_SCHEDULE must be allowlisted."""
        from django.conf import settings
        from accounts.tasks import _MANAGEMENT_COMMAND_ALLOWLIST
        scheduled = {
            entry["args"][0]
            for entry in settings.CELERY_BEAT_SCHEDULE.values()
            if entry.get("task") == "accounts.tasks.run_management_command" and entry.get("args")
        }
        missing = scheduled - _MANAGEMENT_COMMAND_ALLOWLIST
        self.assertEqual(missing, set(), f"Scheduled commands not allowlisted: {missing}")


# ═════════════════════════════════════════════════════════════════════════════
# B. Google One-Tap email_verified enforcement
# ═════════════════════════════════════════════════════════════════════════════

class TestGoogleEmailVerified(SimpleTestCase):
    """_verify_google_token must reject tokens whose email is not verified."""

    def _patch_tokeninfo(self, payload):
        """Patch urlopen so _verify_google_token decodes *payload*."""
        import json
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return patch("accounts.views.urllib.request.urlopen", return_value=cm)

    def test_string_false_rejected(self):
        from accounts.views import _verify_google_token
        payload = {"aud": "cid", "sub": "123", "email": "a@b.com", "email_verified": "false"}
        with self._patch_tokeninfo(payload):
            self.assertIsNone(_verify_google_token("tok", "cid"))

    def test_string_true_passes(self):
        from accounts.views import _verify_google_token
        payload = {"aud": "cid", "sub": "123", "email": "a@b.com", "email_verified": "true"}
        with self._patch_tokeninfo(payload):
            result = _verify_google_token("tok", "cid")
        self.assertIsNotNone(result)
        self.assertEqual(result["sub"], "123")

    def test_bool_true_passes(self):
        """The library-verified path returns a real bool — must also pass."""
        from accounts.views import _verify_google_token
        payload = {"aud": "cid", "sub": "123", "email": "a@b.com", "email_verified": True}
        with self._patch_tokeninfo(payload):
            self.assertIsNotNone(_verify_google_token("tok", "cid"))

    def test_missing_email_verified_rejected(self):
        from accounts.views import _verify_google_token
        payload = {"aud": "cid", "sub": "123", "email": "a@b.com"}
        with self._patch_tokeninfo(payload):
            self.assertIsNone(_verify_google_token("tok", "cid"))

    def test_bool_false_rejected(self):
        from accounts.views import _verify_google_token
        payload = {"aud": "cid", "sub": "123", "email": "a@b.com", "email_verified": False}
        with self._patch_tokeninfo(payload):
            self.assertIsNone(_verify_google_token("tok", "cid"))


# ═════════════════════════════════════════════════════════════════════════════
# C. AdminWalletBonusView double-credit mutex
# ═════════════════════════════════════════════════════════════════════════════

class TestWalletBonusMutex(SimpleTestCase):
    """The cache.add() mutex must block the 2nd concurrent same-key POST."""

    @patch("accounts.views.cache")
    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_second_concurrent_call_blocked(self, mock_cust, mock_tx, mock_cache):
        from accounts.views import AdminWalletBonusView

        # cache.add: first caller wins (True), second loses the race (False).
        mock_cache.add.side_effect = [True, False]

        def _vl_side(*args, **kwargs):
            if kwargs.get("flat"):
                return [1]
            return [(1, "15.00")]

        mock_cust.filter.return_value.values_list.side_effect = _vl_side
        mock_cust.filter.return_value.update.return_value = 1
        mock_tx.bulk_create.return_value = []
        mock_tx.filter.return_value.exists.return_value = False

        factory = APIRequestFactory()
        body = {"amount": "5.00", "customer_ids": [1], "idempotency_key": "k1"}

        def _call():
            req = factory.post("/api/admin/wallet/bonus/", body, format="json")
            force_authenticate(req, user=_staff_user())
            with patch("django.db.transaction.atomic", _fake_atomic):
                return AdminWalletBonusView.as_view()(req)

        resp1 = _call()
        resp2 = _call()

        # First call credits.
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["issued_to"], 1)
        # Second call is rejected as a duplicate WITHOUT crediting again.
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.data.get("duplicate"))
        self.assertEqual(resp2.data["issued_to"], 0)
        # The balance UPDATE must have run exactly once (only the first caller).
        self.assertEqual(mock_cust.filter.return_value.update.call_count, 1)

    @patch("accounts.views.cache")
    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_no_key_skips_mutex(self, mock_cust, mock_tx, mock_cache):
        """Without an idempotency_key the mutex is never engaged (cache.add not called)."""
        from accounts.views import AdminWalletBonusView

        def _vl_side(*args, **kwargs):
            if kwargs.get("flat"):
                return [1]
            return [(1, "15.00")]

        mock_cust.filter.return_value.values_list.side_effect = _vl_side
        mock_cust.filter.return_value.update.return_value = 1
        mock_tx.bulk_create.return_value = []
        mock_tx.filter.return_value.exists.return_value = False

        factory = APIRequestFactory()
        req = factory.post(
            "/api/admin/wallet/bonus/",
            {"amount": "5.00", "customer_ids": [1]},
            format="json",
        )
        force_authenticate(req, user=_staff_user())
        with patch("django.db.transaction.atomic", _fake_atomic):
            resp = AdminWalletBonusView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cache.add.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# D. Cross-persona session fixation guard
# ═════════════════════════════════════════════════════════════════════════════

class TestStaffSessionConflict(SimpleTestCase):
    """A staff/owner session must not be able to layer a customer identity."""

    def test_helper_blocks_authenticated_user(self):
        from accounts.views import _staff_session_conflict
        req = SimpleNamespace(user=_staff_user())
        resp = _staff_session_conflict(req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "staff_session_conflict")

    def test_helper_allows_anonymous_customer(self):
        from accounts.views import _staff_session_conflict
        req = SimpleNamespace(user=_anon())
        self.assertIsNone(_staff_session_conflict(req))

    def test_helper_allows_no_user(self):
        from accounts.views import _staff_session_conflict
        req = SimpleNamespace(user=None)
        self.assertIsNone(_staff_session_conflict(req))

    @patch("accounts.models.Customer.objects")
    def test_phone_verify_refuses_staff(self, mock_cust):
        from accounts.views import CustomerPhoneVerifyView
        factory = APIRequestFactory()
        req = factory.post(
            "/api/customer/phone/verify/",
            {"phone": "+212600000000", "code": "123456"},
            format="json",
        )
        force_authenticate(req, user=_staff_user())
        resp = CustomerPhoneVerifyView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # must refuse BEFORE touching the customer table
        mock_cust.get_or_create.assert_not_called()

    def test_google_verify_refuses_staff(self):
        from accounts.views import CustomerGoogleAuthView
        factory = APIRequestFactory()
        req = factory.post(
            "/api/customer/google/",
            {"credential": "tok"},
            format="json",
        )
        force_authenticate(req, user=_staff_user())
        with patch("accounts.views._verify_google_token") as mock_verify:
            resp = CustomerGoogleAuthView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # must refuse before verifying the Google token
        mock_verify.assert_not_called()

    @patch("accounts.views.cache")
    @patch("accounts.models.Customer.objects")
    def test_email_verify_refuses_staff(self, mock_cust, mock_cache):
        from accounts.views import CustomerEmailVerifyView
        factory = APIRequestFactory()
        req = factory.post(
            "/api/customer/email/verify/",
            {"email": "a@b.com", "code": "123456"},
            format="json",
        )
        force_authenticate(req, user=_staff_user())
        resp = CustomerEmailVerifyView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # must refuse before reading the OTP from cache
        mock_cache.get.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# E. CustomerReservationsView throttle + cancel_token redaction
# ═════════════════════════════════════════════════════════════════════════════

class TestCustomerReservationsHardening(SimpleTestCase):
    """Throttle wired + cancel_token no longer leaked in the list payload."""

    def test_throttle_class_wired(self):
        from accounts.views import CustomerReservationsView
        from accounts.throttles import CustomerReservationsThrottle
        self.assertIn(CustomerReservationsThrottle, CustomerReservationsView.throttle_classes)

    def test_throttle_scope_in_settings(self):
        from django.conf import settings
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertIn("customer_reservations", rates)
        self.assertEqual(rates["customer_reservations"], "60/hour")

    def test_throttle_scope_attribute(self):
        from accounts.throttles import CustomerReservationsThrottle
        self.assertEqual(CustomerReservationsThrottle.scope, "customer_reservations")

    def test_payload_omits_cancel_token(self):
        from accounts.views import CustomerReservationsView

        lead = SimpleNamespace(
            pk=7, tenant_id=3,
            tenant=SimpleNamespace(name="Resto", slug="resto"),
            booked_for=None, party_size=2, status="new", notes="",
            cancel_token="SECRET-UUID", created_at=None,
        )

        # Build the request with a customer session.
        factory = APIRequestFactory()
        req = factory.get("/api/customer/reservations/")
        req.user = _anon()
        # APIRequestFactory requests have no session by default — attach one.
        req.session = {"customer_id": 1}

        customer = SimpleNamespace(email="a@b.com", phone="+212600000000")

        # Patch the ORM hops: Customer.objects.get + Lead queryset chain.
        fake_qs = MagicMock()
        chain = fake_qs.filter.return_value.exclude.return_value.select_related.return_value
        chain.order_by.return_value.__getitem__.return_value = [lead]

        with patch("accounts.models.Customer.objects") as mock_cust, \
                patch("sales.models.Lead") as mock_lead:
            mock_cust.get.return_value = customer
            mock_lead.objects = fake_qs
            mock_lead.Status = SimpleNamespace(PROVISIONING="p", LIVE="l", PAID="paid")
            # Disable throttling for the unit assertion on payload shape.
            with patch.object(CustomerReservationsView, "throttle_classes", []):
                resp = CustomerReservationsView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        entry = resp.data["reservations"][0]
        self.assertNotIn("cancel_token", entry)
        # the rest of the payload is intact
        self.assertEqual(entry["id"], 7)
        self.assertEqual(entry["restaurant_name"], "Resto")
        self.assertEqual(entry["party_size"], 2)
