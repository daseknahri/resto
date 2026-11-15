"""
Run 8 G3b W6 — tests for AdminDeliveryJobActionView (A2-19):
  POST /api/admin/delivery-jobs/<job_id>/action/  {"action": "redispatch"|"cancel"}

Unit-level (SimpleTestCase + mocks — no real DB), following
test_admin_delivery_views.py / test_admin_wallet_views.py.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import AdminDeliveryJobActionView
from accounts.models import User


@contextmanager
def _noop_atomic(*args, **kwargs):
    """Stand-in for transaction.atomic() so mock-based tests don't open a real DB
    connection (the action runs its state change inside atomic())."""
    yield


class _DoesNotExist(Exception):
    pass


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _non_admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    return u


def _make_job(**overrides):
    job = MagicMock()
    job.id = 9001
    job.order_number = "1042"
    job.tenant_id = 3
    job.business_type = "restaurant"
    job.driver = MagicMock()
    job.driver_id = 7
    job.status = "failed"
    job.redispatch_count = 0
    job.resolution = ""
    job.failure_reason = "customer_no_show"
    job.failure_note = "No answer at the door"
    job.is_terminal = False
    job.cancelled_at = None
    job.driver_payout = 18.50
    for k, v in overrides.items():
        setattr(job, k, v)
    return job


class AdminDeliveryJobActionViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryJobActionView.as_view()
        # The action runs inside transaction.atomic(); neutralize it (no local DB).
        _p = patch("django.db.transaction.atomic", _noop_atomic)
        _p.start()
        self.addCleanup(_p.stop)

    def _post(self, job_id, data, user=None):
        req = self.factory.post(
            f"/api/admin/delivery-jobs/{job_id}/action/", data, format="json"
        )
        req.user = user or _admin()
        return self.view(req, job_id=job_id)

    def _mock_models(self, job, noshow_ledger=False):
        """Patch DeliveryJob/WalletTransaction enums + managers for one call.

        The view compares job.status/resolution against the model enums, so the
        mocked enums must carry the real string values, not MagicMocks.
        Returns (patchers) — caller uses as context managers via `with` nesting
        or start/stop; here we return the started patchers for `with` use.
        """
        p_dj = patch("accounts.models.DeliveryJob")
        mock_dj = p_dj.start()
        self.addCleanup(p_dj.stop)
        mock_dj.Status.FAILED = "failed"
        mock_dj.Status.SEARCHING = "searching"
        mock_dj.Status.CANCELLED = "cancelled"
        mock_dj.Resolution.NOSHOW_PAID = "noshow_paid"
        mock_dj.Resolution.REDISPATCHED = "redispatched"
        mock_dj.DoesNotExist = _DoesNotExist
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        p_wtx = patch("accounts.models.WalletTransaction")
        mock_wtx = p_wtx.start()
        self.addCleanup(p_wtx.stop)
        mock_wtx.objects.filter.return_value.exists.return_value = noshow_ledger
        return mock_dj, mock_wtx

    # ── Auth / validation ───────────────────────────────────────────────────

    def test_non_admin_returns_403(self):
        resp = self._post(9001, {"action": "cancel"}, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_action_returns_400(self):
        resp = self._post(9001, {"action": "explode"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_action")

    def test_missing_job_returns_404(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.DoesNotExist = _DoesNotExist
            mock_dj.objects.select_for_update.return_value.get.side_effect = _DoesNotExist
            with patch("accounts.models.WalletTransaction"):
                resp = self._post(9999, {"action": "cancel"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    # ── Redispatch ──────────────────────────────────────────────────────────

    @patch("sales.audit.log_admin_action")
    @patch("accounts.views._serialize_delivery_job", return_value={"id": 9001, "status": "searching"})
    def test_redispatch_failed_job_returns_200_and_resets(self, _mock_ser, mock_log):
        job = _make_job()
        self._mock_models(job)
        resp = self._post(9001, {"action": "redispatch"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["resolution"], "redispatched")
        self.assertEqual(resp.data["job"]["status"], "searching")
        # Owner-mirror reset: driver cleared, back to searching, count +1.
        self.assertIsNone(job.driver)
        self.assertEqual(job.status, "searching")
        self.assertEqual(job.redispatch_count, 1)
        self.assertEqual(job.resolution, "redispatched")
        self.assertEqual(job.failure_reason, "")
        self.assertEqual(job.failure_note, "")
        job.save.assert_called_once()
        saved_fields = job.save.call_args[1]["update_fields"]
        self.assertIn("status", saved_fields)
        self.assertIn("redispatch_count", saved_fields)
        # Audited with the plain-string action (no new enum member).
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args[1]["action"], "delivery_job_actioned")
        self.assertEqual(mock_log.call_args[1]["target_repr"], "job:9001:1042")

    def test_redispatch_non_failed_job_returns_409(self):
        job = _make_job(status="assigned", is_terminal=False)
        self._mock_models(job)
        with patch("sales.audit.log_admin_action") as mock_log:
            resp = self._post(9001, {"action": "redispatch"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "job_changed")
        mock_log.assert_not_called()

    def test_redispatch_at_limit_returns_409(self):
        job = _make_job(redispatch_count=3)
        self._mock_models(job)
        resp = self._post(9001, {"action": "redispatch"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "redispatch_limit")

    def test_redispatch_noshow_paid_resolution_returns_409(self):
        job = _make_job(resolution="noshow_paid")
        self._mock_models(job)
        resp = self._post(9001, {"action": "redispatch"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")

    def test_redispatch_noshow_paid_in_ledger_returns_409(self):
        job = _make_job(resolution="")
        self._mock_models(job, noshow_ledger=True)
        resp = self._post(9001, {"action": "redispatch"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")

    # ── Cancel ──────────────────────────────────────────────────────────────

    @patch("sales.audit.log_admin_action")
    @patch("accounts.views._serialize_delivery_job", return_value={"id": 9001, "status": "cancelled"})
    def test_cancel_active_job_returns_200(self, _mock_ser, mock_log):
        job = _make_job(status="searching", is_terminal=False)
        self._mock_models(job)
        resp = self._post(9001, {"action": "cancel"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["resolution"], "cancelled")
        self.assertEqual(job.status, "cancelled")
        self.assertIsNotNone(job.cancelled_at)
        # Cancel clears the offer but touches no money/order fields.
        self.assertIsNone(job.offered_to)
        job.save.assert_called_once()
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args[1]["action"], "delivery_job_actioned")

    def test_cancel_terminal_job_returns_409(self):
        job = _make_job(status="delivered", is_terminal=True)
        self._mock_models(job)
        resp = self._post(9001, {"action": "cancel"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "job_changed")
