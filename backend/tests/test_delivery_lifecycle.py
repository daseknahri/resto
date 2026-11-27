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
    @patch("accounts.models.Customer")
    @patch("accounts.models.DeliveryJob")
    def test_picked_up_job_delivered_and_driver_credited(self, mock_dj, mock_customer, _atomic, mock_credit):
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.Status.DELIVERED = "delivered"
        mock_customer.objects.filter.return_value.exists.return_value = True  # OPS-5f: still approved
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
    def test_driverless_searching_job_is_cancelled(self, mock_dj, _atomic, mock_credit):
        # R6-04: a driverless (still-searching) job on a completed order is CANCELLED
        # so the sweep can't re-dispatch or auto-refund it — but never marked
        # delivered/credited (nobody to pay).
        from accounts.delivery_service import complete_delivery_job_for_order
        mock_dj.Status.SEARCHING = "searching"
        mock_dj.Status.CANCELLED = "cancelled"
        job = SimpleNamespace(is_terminal=False, driver_id=None, status="searching",
                              cancelled_at=None, save=MagicMock())
        mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
        complete_delivery_job_for_order(1, "ORD-1")
        self.assertEqual(job.status, "cancelled")
        self.assertIsNotNone(job.cancelled_at)
        job.save.assert_called_once_with(update_fields=["status", "cancelled_at"])
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


class SetFoodReadyAnchorTests(SimpleTestCase):
    """Wave M M-05: set_delivery_job_food_ready must not re-anchor the ready
    clock on a routine status tap / note edit (previous == new)."""

    def _job(self, *, ready_at):
        job = SimpleNamespace(is_terminal=False, food_ready_at=ready_at, save=MagicMock())
        return job

    def _run(self, job, minutes, previous):
        with patch("django.db.transaction.atomic", return_value=_noop_atomic()), \
                patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.select_for_update.return_value.filter.return_value.first.return_value = job
            from accounts.delivery_service import set_delivery_job_food_ready
            return set_delivery_job_food_ready(1, "ORD-1", minutes, previous_minutes=previous)

    def test_same_minutes_keeps_anchor(self):
        from django.utils import timezone
        stamp = timezone.now()
        job = self._job(ready_at=stamp)
        self._run(job, 20, previous=20)
        job.save.assert_not_called()
        self.assertEqual(job.food_ready_at, stamp)

    def test_changed_minutes_restamps(self):
        from django.utils import timezone
        stamp = timezone.now() - timezone.timedelta(minutes=10)
        job = self._job(ready_at=stamp)
        self._run(job, 30, previous=20)
        job.save.assert_called_once()
        self.assertNotEqual(job.food_ready_at, stamp)

    def test_no_anchor_stamps_even_when_minutes_unchanged(self):
        job = self._job(ready_at=None)
        self._run(job, 20, previous=20)
        job.save.assert_called_once()
        self.assertIsNotNone(job.food_ready_at)

    def test_none_to_none_with_anchor_keeps_anchor(self):
        from django.utils import timezone
        stamp = timezone.now()
        job = self._job(ready_at=stamp)
        self._run(job, None, previous=None)
        job.save.assert_not_called()
        self.assertEqual(job.food_ready_at, stamp)


class ShouldRestampOnRedispatchTests(SimpleTestCase):
    """Wave M M-14(b): redispatch re-stamps the ready clock only when the ETA
    actually changed (or no ready time exists yet)."""

    def _order(self, *, eta=None, anchor=None):
        return SimpleNamespace(estimated_ready_minutes=eta, estimated_ready_at=anchor)

    def _job(self, *, ready_at):
        return SimpleNamespace(food_ready_at=ready_at)

    def test_no_ready_time_restamps(self):
        from accounts.delivery_service import should_restamp_food_ready_on_redispatch
        self.assertTrue(should_restamp_food_ready_on_redispatch(
            self._order(eta=20), self._job(ready_at=None)))

    def test_matching_anchors_do_not_restamp(self):
        from django.utils import timezone
        from accounts.delivery_service import should_restamp_food_ready_on_redispatch
        stamp = timezone.now()
        self.assertFalse(should_restamp_food_ready_on_redispatch(
            self._order(eta=20, anchor=stamp),
            self._job(ready_at=stamp + timezone.timedelta(seconds=5))))

    def test_edited_eta_restamps(self):
        from django.utils import timezone
        from accounts.delivery_service import should_restamp_food_ready_on_redispatch
        stamp = timezone.now()
        self.assertTrue(should_restamp_food_ready_on_redispatch(
            self._order(eta=45, anchor=stamp + timezone.timedelta(minutes=25)),
            self._job(ready_at=stamp)))

    def test_eta_set_but_no_order_anchor_restamps(self):
        from django.utils import timezone
        from accounts.delivery_service import should_restamp_food_ready_on_redispatch
        self.assertTrue(should_restamp_food_ready_on_redispatch(
            self._order(eta=20, anchor=None),
            self._job(ready_at=timezone.now())))

    def test_no_explicit_eta_does_not_restamp(self):
        from django.utils import timezone
        from accounts.delivery_service import should_restamp_food_ready_on_redispatch
        self.assertFalse(should_restamp_food_ready_on_redispatch(
            self._order(eta=None, anchor=None),
            self._job(ready_at=timezone.now())))


class BulkConfirmMirrorTests(SimpleTestCase):
    """Wave M M-04: bulk confirm stamps food_ready_at on the new delivery job."""

    def setUp(self):
        from menu.views import OwnerOrderBulkStatusView
        self.factory = APIRequestFactory()
        self.view = OwnerOrderBulkStatusView.as_view()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    def test_bulk_confirm_delivery_mirrors_ready_minutes(self, _mock_atomic):
        import contextlib
        from decimal import Decimal
        order = SimpleNamespace(
            order_number="ORD-B1", status="confirmed", fulfillment_type="delivery",
            estimated_ready_minutes=None, customer=None, customer_name="A",
            total=Decimal("50"), currency="MAD", wallet_amount_paid=Decimal("0"),
            handled_by_user_id=None,
            save=MagicMock(), refresh_from_db=MagicMock(),
        )
        req = self.factory.post("/api/owner/orders/bulk-status/",
                                {"order_ids": [1], "status": "confirmed"}, format="json")
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R")
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
                patch("menu.views.Order.objects") as om, \
                patch("menu.views._broadcast_order_change") as bc, \
                patch("accounts.tasks.enqueue"), \
                patch("accounts.tasks.order_status_email"), \
                patch("accounts.delivery_service.set_delivery_job_food_ready") as mirror:
            om.select_for_update.return_value = om
            om.filter.return_value = om
            om.select_related.return_value = om
            om.__getitem__.return_value = [order]
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mirror.assert_called_once_with(1, "ORD-B1", 20)


class MirrorReadyMinutesTests(SimpleTestCase):
    """menu.views._delivery_job_ready_minutes (Wave L L-03)."""

    def _order(self, *, eta=None, status="confirmed"):
        return SimpleNamespace(estimated_ready_minutes=eta, status=status)

    def _tenant(self, *, default_prep=None, profile=True):
        if not profile:
            return SimpleNamespace(profile=None)
        return SimpleNamespace(profile=SimpleNamespace(default_prep_minutes=default_prep))

    def test_explicit_eta_wins(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=25), self._tenant(default_prep=30)), 25)

    def test_confirm_without_eta_uses_tenant_default(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=None), self._tenant(default_prep=30)), 30)

    def test_confirm_without_eta_no_profile_uses_platform_default(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=None), self._tenant(profile=False)), 20)
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=None), self._tenant(default_prep=None)), 20)

    def test_preparing_without_eta_uses_tenant_default(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=None, status="preparing"), self._tenant(default_prep=45)), 45)

    def test_ready_without_eta_is_now(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=None, status="ready"), self._tenant()), 0)

    def test_pending_without_eta_is_none(self):
        from menu.views import _delivery_job_ready_minutes
        self.assertIsNone(_delivery_job_ready_minutes(
            self._order(eta=None, status="pending"), self._tenant()))

    def test_ready_with_eta_is_now(self):
        """Wave M M-05(a): READY with a stale explicit ETA is 0, not the ETA —
        the status beats the stale number."""
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=25, status="ready"), self._tenant()), 0)

    def test_out_for_delivery_with_eta_is_now(self):
        """Wave M M-05(a): same for OUT_FOR_DELIVERY."""
        from menu.views import _delivery_job_ready_minutes
        self.assertEqual(_delivery_job_ready_minutes(
            self._order(eta=40, status="out_for_delivery"), self._tenant()), 0)



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

    # ── No-show-paid job must not re-enter dispatch (double-pay guard) ────────────

    def _redispatch(self, *, job_resolution, ledger_exists, redispatch_count=0,
                    order_status="ready"):
        """Drive a `redispatch` action on a FAILED job with the DB collaborators mocked."""
        import contextlib
        order = SimpleNamespace(order_number="ORD-1", status=order_status, pk=1)
        job = MagicMock()
        job.id = 55
        job.status = "failed"
        job.redispatch_count = redispatch_count
        job.resolution = job_resolution
        req = self.factory.post("/api/owner/orders/1/delivery-action/", {"action": "redispatch"}, format="json")
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R")
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views.Order.objects") as om, \
             patch("django.db.transaction.atomic", lambda *a, **k: contextlib.nullcontext()), \
             patch("accounts.models.DeliveryJob") as DJ, \
             patch("accounts.models.WalletTransaction") as WT:
            om.filter.return_value.first.return_value = order
            DJ.Status.FAILED = "failed"
            DJ.Resolution.NOSHOW_PAID = "noshow_paid"
            DJ.objects.select_for_update.return_value.filter.return_value.first.return_value = job
            WT.objects.filter.return_value.exists.return_value = ledger_exists
            return self.view(req, order_id=1)

    def test_redispatch_after_noshow_paid_is_rejected(self):
        """A no-show that was already paid (resolution=NOSHOW_PAID) cannot be re-dispatched —
        otherwise a second driver would deliver and be credited too (two payouts, one fee)."""
        resp = self._redispatch(job_resolution="noshow_paid", ledger_exists=False)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "already_paid")

    def test_redispatch_on_completed_order_returns_409(self):
        """R6-05: a FAILED job whose order is already COMPLETED can't be re-dispatched —
        a second driver would be paid for a phantom delivery."""
        from menu.models import Order
        resp = self._redispatch(job_resolution="", ledger_exists=False,
                                order_status=Order.Status.COMPLETED)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "order_completed")

    def test_redispatch_on_cancelled_order_returns_409(self):
        """R6-05: same guard for a CANCELLED order."""
        from menu.models import Order
        resp = self._redispatch(job_resolution="", ledger_exists=False,
                                order_status=Order.Status.CANCELLED)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "order_cancelled")

    def test_refund_cancel_on_completed_order_returns_409(self):
        """R6-04: manual refund & cancel on a COMPLETED order → 409; the shared
        helper is never called (its COMPLETED guard is defence-in-depth)."""
        from menu.models import Order
        order = SimpleNamespace(order_number="ORD-1", status=Order.Status.COMPLETED, pk=1)
        req = self.factory.post("/api/owner/orders/1/delivery-action/",
                                {"action": "refund_cancel"}, format="json")
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R")
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views.Order.objects") as om, \
             patch("menu.views.refund_and_cancel_delivery_order") as helper:
            om.filter.return_value.first.return_value = order
            resp = self.view(req, order_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "order_completed")
        helper.assert_not_called()

    def test_redispatch_blocked_by_noshow_ledger_backstop(self):
        """Even if resolution was overwritten, a wallet noshow:{job.id} credit on the ledger
        blocks redispatch — money already left, so refund/cancel is the only safe path."""
        resp = self._redispatch(job_resolution="redispatched", ledger_exists=True)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "already_paid")

    # ── confirm_noshow must re-check driver approval before paying (OPS-5f) ───────

    def _confirm_noshow(self, *, driver_approved, driver_id=7, driver_payout=20,
                        order_status="failed"):
        """Drive a `confirm_noshow` action on a FAILED + CUSTOMER_NO_SHOW job with the DB
        collaborators mocked. `driver_approved` drives the Customer.exists() re-check."""
        import contextlib
        order = SimpleNamespace(order_number="ORD-1", status=order_status, pk=1)
        job = MagicMock()
        job.id = 55
        job.status = "failed"
        job.failure_reason = "customer_no_show"
        job.driver_id = driver_id
        job.driver_payout = driver_payout
        req = self.factory.post(
            "/api/owner/orders/1/delivery-action/", {"action": "confirm_noshow"}, format="json"
        )
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R")
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views.Order.objects") as om, \
             patch("django.db.transaction.atomic", lambda *a, **k: contextlib.nullcontext()), \
             patch("accounts.models.DeliveryJob") as DJ, \
             patch("accounts.models.WalletTransaction"), \
             patch("accounts.models.Customer") as Cust, \
             patch("accounts.wallet_service.credit_wallet") as cw:
            om.filter.return_value.first.return_value = order
            DJ.Status.FAILED = "failed"
            DJ.FailureReason.CUSTOMER_NO_SHOW = "customer_no_show"
            DJ.Resolution.NOSHOW_PAID = "noshow_paid"
            DJ.objects.select_for_update.return_value.filter.return_value.first.return_value = job
            Cust.objects.filter.return_value.exists.return_value = driver_approved
            resp = self.view(req, order_id=1)
            return resp, cw, Cust, job

    def test_confirm_noshow_revoked_driver_rejected_and_not_credited(self):
        """Bug 3 regression: a driver approved when the job was created but SINCE revoked
        must not bank a no-show payout. The credit path re-checks driver_approved (like the
        two DELIVERED paths) and returns 409 driver_not_approved without crediting."""
        resp, cw, Cust, job = self._confirm_noshow(driver_approved=False)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "driver_not_approved")
        # The approval re-check is scoped to this driver AND driver_approved=True.
        Cust.objects.filter.assert_called_once_with(pk=7, driver_approved=True)
        # No money moved and the job was NOT stamped paid.
        cw.assert_not_called()
        job.save.assert_not_called()

    def test_confirm_noshow_on_completed_order_returns_409(self):
        """R6-05: paying a no-show on an already-COMPLETED order → 409; no money moves."""
        from menu.models import Order
        resp, cw, Cust, job = self._confirm_noshow(
            driver_approved=True, order_status=Order.Status.COMPLETED)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "order_completed")
        cw.assert_not_called()
        job.save.assert_not_called()

    def test_confirm_noshow_approved_driver_is_paid(self):
        """Control: an approved driver IS credited and the job is stamped NOSHOW_PAID."""
        resp, cw, Cust, job = self._confirm_noshow(driver_approved=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("resolution"), "noshow_paid")
        cw.assert_called_once()
        self.assertEqual(job.resolution, "noshow_paid")
        job.save.assert_called_once_with(update_fields=["resolution"])

    # ── unassign: owner stands down an assigned-but-idle driver (D G5) ─────────

    def _unassign(self, *, job_status="assigned", driver_id=7, redispatch_count=0):
        """Drive an `unassign` action on a job with the DB collaborators mocked."""
        import contextlib
        order = SimpleNamespace(order_number="ORD-1", status="ready", pk=1)
        job = MagicMock()
        job.id = 55
        job.status = job_status
        job.driver_id = driver_id
        job.redispatch_count = redispatch_count
        req = self.factory.post("/api/owner/orders/1/delivery-action/", {"action": "unassign"}, format="json")
        force_authenticate(req, user=MagicMock(is_authenticated=True))
        req.tenant = SimpleNamespace(id=1, name="R")
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views.Order.objects") as om, \
             patch("django.db.transaction.atomic", lambda *a, **k: contextlib.nullcontext()), \
             patch("accounts.models.DeliveryJob") as DJ, \
             patch("accounts.dispatch.offer_to_next_driver") as offer:
            om.filter.return_value.first.return_value = order
            DJ.Status.ASSIGNED = "assigned"
            DJ.Status.AT_RESTAURANT = "at_restaurant"
            DJ.Status.SEARCHING = "searching"
            DJ.Resolution.REDISPATCHED = "redispatched"
            DJ.objects.select_for_update.return_value.filter.return_value.first.return_value = job
            resp = self.view(req, order_id=1)
            return resp, offer, job

    def test_unassign_assigned_job_reoffers(self):
        """D G5: an ASSIGNED job's driver is stood down, the job re-enters the pool
        (SEARCHING, fresh offer cascade) and the redispatch count increments."""
        resp, offer, job = self._unassign(job_status="assigned", driver_id=7, redispatch_count=0)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("resolution"), "unassigned")
        self.assertIsNone(job.driver)
        self.assertEqual(job.status, "searching")
        self.assertEqual(job.redispatch_count, 1)
        self.assertIsNone(job.assigned_at)
        job.save.assert_called_once()
        offer.assert_called_once_with(55)

    def test_unassign_at_restaurant_job_reoffers(self):
        resp, offer, job = self._unassign(job_status="at_restaurant", driver_id=7)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(job.status, "searching")
        offer.assert_called_once_with(55)

    def test_unassign_picked_up_job_is_rejected(self):
        """Once the driver has the food, unassigning would strand the order."""
        resp, offer, job = self._unassign(job_status="picked_up", driver_id=7)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "job_changed")
        offer.assert_not_called()
        job.save.assert_not_called()

    def test_unassign_searching_job_is_rejected(self):
        resp, offer, job = self._unassign(job_status="searching", driver_id=None)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "job_changed")
        offer.assert_not_called()

    def test_unassign_job_without_driver_is_rejected(self):
        resp, offer, job = self._unassign(job_status="assigned", driver_id=None)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "no_driver")
        offer.assert_not_called()
