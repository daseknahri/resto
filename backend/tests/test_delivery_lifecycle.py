"""
Unit tests for the delivery unhappy-path lifecycle:
  - accounts.delivery_service.cancel_delivery_job_for_order (cancel cancels the job)
  - menu.views.OwnerDeliveryJobActionView guardrails (auth + action validation)

SimpleTestCase + mocks (no DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class CancelDeliveryJobTests(SimpleTestCase):
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_terminal_job_is_noop(self, mock_dj, _atomic):
        from accounts.delivery_service import cancel_delivery_job_for_order
        job = SimpleNamespace(is_terminal=True, driver_id=5, status="delivered", save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        with patch("accounts.tasks.enqueue") as enq:
            cancel_delivery_job_for_order(1, "ORD-1")
        job.save.assert_not_called()
        enq.assert_not_called()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_active_job_cancelled_and_driver_notified(self, mock_dj, _atomic):
        from accounts.delivery_service import cancel_delivery_job_for_order
        mock_dj.Status.CANCELLED = "cancelled"
        job = SimpleNamespace(is_terminal=False, driver_id=5, status="assigned",
                              cancelled_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        with patch("accounts.tasks.enqueue") as enq:
            cancel_delivery_job_for_order(1, "ORD-1")
        self.assertEqual(job.status, "cancelled")
        job.save.assert_called_once()
        enq.assert_called_once()  # driver told to stand down

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_no_job_is_noop(self, mock_dj, _atomic):
        from accounts.delivery_service import cancel_delivery_job_for_order
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = None
        with patch("accounts.tasks.enqueue") as enq:
            out = cancel_delivery_job_for_order(1, "ORD-NONE")
        self.assertIsNone(out)
        enq.assert_not_called()


class OwnerDeliveryActionGuardTests(SimpleTestCase):
    def setUp(self):
        from menu.views import OwnerDeliveryJobActionView
        self.factory = APIRequestFactory()
        self.view = OwnerDeliveryJobActionView.as_view()

    def _post(self, order_id, data, can_edit=True, tenant=True):
        req = self.factory.post(f"/api/owner/orders/{order_id}/delivery-action/", data, format="json")
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R") if tenant else None
        with patch("menu.views._can_edit_tenant_order", return_value=can_edit):
            return self.view(req, order_id=order_id)

    def test_access_denied_when_not_owner(self):
        resp = self._post(1, {"action": "redispatch"}, can_edit=False)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_action_rejected(self):
        resp = self._post(1, {"action": "frobnicate"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "bad_action")
