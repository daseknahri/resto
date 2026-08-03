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


class CompleteDeliveryJobTests(SimpleTestCase):
    """complete_delivery_job_for_order: when the OWNER completes a delivery order, the job is closed
    (→ DELIVERED) and the driver is credited — closing the gap where owner-completion left the job
    dangling at picked_up (driver uncredited + soft-locked)."""

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_picked_up_job_delivered_and_driver_credited(self, mock_dj, _atomic, mock_credit):
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.Status.DELIVERED = "delivered"
        job = SimpleNamespace(is_terminal=False, driver_id=5, status="picked_up",
                              delivered_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        out = complete_delivery_job_for_order(1, "ORD-1")
        self.assertEqual(job.status, "delivered")
        self.assertIsNotNone(job.delivered_at)
        job.save.assert_called_once()
        mock_credit.assert_called_once_with(job)  # driver paid
        self.assertIs(out, job)

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_terminal_job_is_noop(self, mock_dj, _atomic, mock_credit):
        # Already delivered (e.g. the driver also tapped delivered) → no re-close, no re-credit.
        from accounts.delivery_service import complete_delivery_job_for_order
        job = SimpleNamespace(is_terminal=True, driver_id=5, status="delivered", save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        complete_delivery_job_for_order(1, "ORD-1")
        job.save.assert_not_called()
        mock_credit.assert_not_called()

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_no_driver_is_noop(self, mock_dj, _atomic, mock_credit):
        # A driverless (still-searching) job on a completed order isn't marked delivered/credited here.
        from accounts.delivery_service import complete_delivery_job_for_order
        job = SimpleNamespace(is_terminal=False, driver_id=None, status="searching", save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        complete_delivery_job_for_order(1, "ORD-1")
        job.save.assert_not_called()
        mock_credit.assert_not_called()

    @patch("accounts.views._credit_driver_earnings")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_no_job_is_noop(self, mock_dj, _atomic, mock_credit):
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = None
        out = complete_delivery_job_for_order(1, "ORD-NONE")
        self.assertIsNone(out)
        mock_credit.assert_not_called()


class SetFoodReadyTests(SimpleTestCase):
    """accounts.delivery_service.set_delivery_job_food_ready mirrors the prep ETA
    onto the active delivery job so the driver knows when to be at the restaurant."""

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_sets_food_ready_at_from_minutes(self, mock_dj, _atomic):
        from accounts.delivery_service import set_delivery_job_food_ready
        job = SimpleNamespace(is_terminal=False, food_ready_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        set_delivery_job_food_ready(1, "ORD-1", 15)
        self.assertIsNotNone(job.food_ready_at)
        job.save.assert_called_once()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_none_minutes_clears_eta(self, mock_dj, _atomic):
        from accounts.delivery_service import set_delivery_job_food_ready
        job = SimpleNamespace(is_terminal=False, food_ready_at="something", save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        set_delivery_job_food_ready(1, "ORD-1", None)
        self.assertIsNone(job.food_ready_at)
        job.save.assert_called_once()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("accounts.models.DeliveryJob")
    def test_terminal_job_is_noop(self, mock_dj, _atomic):
        from accounts.delivery_service import set_delivery_job_food_ready
        job = SimpleNamespace(is_terminal=True, food_ready_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        set_delivery_job_food_ready(1, "ORD-1", 15)
        job.save.assert_not_called()

    @patch("accounts.models.DeliveryJob")
    def test_invalid_minutes_is_noop(self, mock_dj):
        from accounts.delivery_service import set_delivery_job_food_ready
        out = set_delivery_job_food_ready(1, "ORD-1", "bad")
        self.assertIsNone(out)
        mock_dj.objects.select_for_update.assert_not_called()


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
