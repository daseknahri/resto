"""Services-hardening regression tests (mock-based SimpleTestCase — no DB).

Two independent hardening fixes, one class each:

A. ``accounts.delivery_service.complete_delivery_job_for_order`` — OPS-5f approval
   re-check on the OWNER-completion money-emitting path. A driver whose ``driver_approved``
   was revoked after pickup must NOT be credited, and the job must NOT be marked DELIVERED
   (which would let ``reconcile_driver_earnings`` silently re-pay the revoked driver).
   Sibling of ``tests/test_ops5f_accounts.py`` which covers the driver's own DELIVERED tap.

B. ``accounts.mfa_views.MFADisableView`` — the MFA-disable audit call used the wrong
   kwarg (``detail=``) which raised ``TypeError`` inside ``log_admin_action`` and was
   silently swallowed by a bare ``except``, so disabling MFA (a security-control downgrade)
   produced no ``AdminAuditLog`` row. These tests let the REAL ``log_admin_action`` run and
   only mock it at the DB boundary, so a future signature drift is caught (a bad kwarg makes
   the real function raise before ``create()`` is ever reached → the assertion fails).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ═════════════════════════════════════════════════════════════════════════════
# A. Owner-completion OPS-5f approval gate (delivery_service)
# ═════════════════════════════════════════════════════════════════════════════

class OwnerCompletionApprovalGateTests(SimpleTestCase):
    """complete_delivery_job_for_order must re-check driver approval before crediting,
    mirroring the driver's own DELIVERED tap (OPS-5f)."""

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.Customer")
    @patch("accounts.models.DeliveryJob")
    def test_revoked_driver_not_credited_and_not_delivered(self, mock_dj, mock_customer, _atomic, mock_credit):
        """Revoked driver → no credit AND job left un-transitioned (so reconcile skips it)."""
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.Status.DELIVERED = "delivered"
        mock_customer.objects.filter.return_value.exists.return_value = False  # approval revoked
        job = SimpleNamespace(is_terminal=False, driver_id=5, status="picked_up",
                              delivered_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        out = complete_delivery_job_for_order(1, "ORD-1")

        self.assertEqual(job.status, "picked_up")   # NOT flipped to DELIVERED
        self.assertIsNone(job.delivered_at)
        job.save.assert_not_called()                 # nothing persisted → reconcile can't re-credit
        mock_credit.assert_not_called()              # revoked driver not paid
        mock_customer.objects.filter.assert_called_once_with(pk=5, driver_approved=True)
        self.assertIs(out, job)

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.Customer")
    @patch("accounts.models.DeliveryJob")
    def test_approved_driver_delivered_and_credited(self, mock_dj, mock_customer, _atomic, mock_credit):
        """Still-approved driver → job marked DELIVERED and driver credited (happy path)."""
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.Status.DELIVERED = "delivered"
        mock_customer.objects.filter.return_value.exists.return_value = True  # still approved
        job = SimpleNamespace(is_terminal=False, driver_id=5, status="picked_up",
                              delivered_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        out = complete_delivery_job_for_order(1, "ORD-1")

        self.assertEqual(job.status, "delivered")
        self.assertIsNotNone(job.delivered_at)
        job.save.assert_called_once()
        mock_credit.assert_called_once_with(job)
        mock_customer.objects.filter.assert_called_once_with(pk=5, driver_approved=True)
        self.assertIs(out, job)

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.Customer")
    @patch("accounts.models.DeliveryJob")
    def test_no_driver_skips_approval_check(self, mock_dj, mock_customer, _atomic, mock_credit):
        """A driverless job returns before the approval query even runs (no Customer hit)."""
        from accounts.delivery_service import complete_delivery_job_for_order
        job = SimpleNamespace(is_terminal=False, driver_id=None, status="searching", save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job

        complete_delivery_job_for_order(1, "ORD-1")

        job.save.assert_not_called()
        mock_credit.assert_not_called()
        mock_customer.objects.filter.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# B. MFA-disable audit logging (mfa_views)
# ═════════════════════════════════════════════════════════════════════════════

class MFADisableAuditLogTests(SimpleTestCase):
    """MFADisableView must write exactly one AdminAuditLog row (action='mfa_device_disabled')
    on a successful disable, capturing the request IP."""

    def _build_request(self, data):
        """A real DRF Request (so request.data + request.META work) with a mock user."""
        raw = APIRequestFactory().post("/api/mfa/disable/", data, format="json")
        request = Request(raw, parsers=[JSONParser()])
        return request

    @staticmethod
    def _mock_user(pk=4242, username="owner1", password_ok=True):
        user = MagicMock()
        user.pk = pk
        user.username = username
        user.check_password.return_value = password_ok
        device = MagicMock()
        device.confirmed = True
        user.totp_device = device
        return user, device

    def test_disable_writes_audit_log_and_captures_ip(self):
        from accounts.mfa_views import MFADisableView

        request = self._build_request({"password": "correct-horse"})
        user, device = self._mock_user()
        request.user = user

        # Let the REAL log_admin_action run, but stop it at the DB boundary by mocking the
        # model it writes. A future `detail=`-style signature drift would raise inside
        # log_admin_action BEFORE create() is reached → create is never called → this fails.
        with patch("sales.audit.AdminAuditLog") as mock_audit_model:
            view = MFADisableView()
            view.permission_classes = []  # bypass IsAuthenticated for the unit-level call
            resp = view.post(request)

        self.assertEqual(resp.status_code, 200)
        device.delete.assert_called_once()

        mock_audit_model.objects.create.assert_called_once()
        _, kwargs = mock_audit_model.objects.create.call_args
        self.assertEqual(kwargs["action"], "mfa_device_disabled")
        self.assertEqual(kwargs["metadata"], {"user_id": 4242, "username": "owner1"})
        self.assertEqual(kwargs["target_repr"], "User#4242")
        self.assertEqual(kwargs["actor"], user)
        # request was threaded through → client IP resolved from REMOTE_ADDR (127.0.0.1).
        self.assertEqual(kwargs["ip_address"], "127.0.0.1")

    def test_failed_reauth_writes_no_audit_log(self):
        """Wrong password → 403, no device removed, no audit row (only real disables log)."""
        from accounts.mfa_views import MFADisableView

        request = self._build_request({"password": "wrong"})
        user, device = self._mock_user(password_ok=False)
        request.user = user

        with patch("sales.audit.AdminAuditLog") as mock_audit_model:
            view = MFADisableView()
            view.permission_classes = []
            resp = view.post(request)

        self.assertEqual(resp.status_code, 403)
        device.delete.assert_not_called()
        mock_audit_model.objects.create.assert_not_called()
