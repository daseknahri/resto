"""Bounded auto-refund for stuck PRE-PICKUP delivery jobs.

Two layers, both mock-based (SimpleTestCase, no DB):

  * refund_and_cancel_delivery_order — the ONE idempotent helper shared by the owner's
    manual "refund & cancel" and the sweep. Proven idempotent: a replay credits the
    wallet again (that credit is itself keyed/idempotent) but does NOT re-claw loyalty
    or re-restock.
  * Command._auto_refund_stuck_jobs — the sweep pass. Proven to refund a stuck
    pre-pickup job past the deadline, and to REFUSE to when: auto-refund is disabled
    (minutes=0), the deadline hasn't passed, a driver picked up / the job went terminal
    between the scan and the lock (the critical "never refund a picked-up job" guard),
    a driver was freshly assigned, or the order is gone.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase

from accounts.management.commands.sweep_delivery_jobs import Command
from menu.models import Order
from menu.views import refund_and_cancel_delivery_order


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


@contextmanager
def _noop_cm(*args, **kwargs):
    yield


# ── The shared helper is idempotent ───────────────────────────────────────────

@patch("menu.views.Order")
@patch("django.db.transaction.atomic", lambda *a, **k: _passthrough_cm())
@patch("accounts.models.DeliveryJob")
@patch("accounts.delivery_service.cancel_delivery_job_for_order")
@patch("menu.views._broadcast_order_change")
@patch("menu.views._restock_cancelled_order")
@patch("menu.views._reverse_loyalty_for_cancelled_order")
@patch("menu.views._refund_wallet_for_cancelled_order")
class RefundAndCancelHelperTests(SimpleTestCase):
    def _order(self, status):
        o = MagicMock()
        o.status = status
        o.order_number = "ORD-1"
        o.payment_status = "paid"
        return o

    def _wire_lock(self, order_m, locked_status):
        """Point the patched menu.views.Order at a row-lock returning a row that reports
        `locked_status`. The helper now re-reads the order UNDER select_for_update and its
        cancel/skip decision hinges on THAT row (not the passed, possibly-stale object), so
        every test wires it. Keep Order.Status.CANCELLED equal to the real enum value so the
        helper's comparison and the assertions below agree."""
        order_m.Status.CANCELLED = Order.Status.CANCELLED
        locked = MagicMock()
        locked.status = locked_status
        (order_m.objects.select_for_update.return_value
            .filter.return_value.first.return_value) = locked
        return locked

    def test_pending_order_is_cancelled_and_fully_reversed(
        self, refund_m, loyalty_m, restock_m, broadcast_m, cancel_job_m, dj_m, order_m
    ):
        """First call on a live order: flips it to CANCELLED and runs the full reversal
        (wallet refund + loyalty claw-back + restock + broadcast), returning True."""
        self._wire_lock(order_m, locked_status="pending")  # the locked row is still live
        order = self._order("pending")
        result = refund_and_cancel_delivery_order(order, tenant_id=1)

        self.assertTrue(result)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        refund_m.assert_called_once_with(order, tenant_id=1)
        loyalty_m.assert_called_once_with(order)
        restock_m.assert_called_once_with(order)
        broadcast_m.assert_called_once_with(order)

    def test_already_cancelled_order_replays_wallet_only(
        self, refund_m, loyalty_m, restock_m, broadcast_m, cancel_job_m, dj_m, order_m
    ):
        """Idempotent replay: an already-CANCELLED order (a second sweep, an owner
        double-tap) still calls the keyed/idempotent wallet credit but must NOT
        re-claw loyalty or re-restock (neither is internally idempotent). Returns
        False (this call did not perform the cancellation)."""
        self._wire_lock(order_m, locked_status=Order.Status.CANCELLED)
        order = self._order("cancelled")
        result = refund_and_cancel_delivery_order(order, tenant_id=1)

        self.assertFalse(result)
        refund_m.assert_called_once_with(order, tenant_id=1)  # keyed → safe to replay
        loyalty_m.assert_not_called()   # NOT re-clawed
        restock_m.assert_not_called()   # NOT re-restocked

    def test_concurrent_peer_cancelled_under_lock_skips_reversal(
        self, refund_m, loyalty_m, restock_m, broadcast_m, cancel_job_m, dj_m, order_m
    ):
        """Regression (concurrency): THIS caller loaded the order pre-cancel ('pending'), but
        a racing peer — a manual refund_cancel or the sweep — cancelled it first, so the row
        read UNDER the lock is already CANCELLED. The decision must follow the locked row, not
        the stale passed object: the keyed wallet credit still replays, but the non-idempotent
        loyalty claw-back and restock must NOT run a second time. Before the select_for_update
        fix the check read order.status ('pending') and double-applied both."""
        self._wire_lock(order_m, locked_status=Order.Status.CANCELLED)
        order = self._order("pending")  # stale: this caller hasn't seen the peer's cancel
        result = refund_and_cancel_delivery_order(order, tenant_id=1)

        self.assertFalse(result)                              # not the cancelling call
        refund_m.assert_called_once_with(order, tenant_id=1)  # keyed → safe to replay
        loyalty_m.assert_not_called()   # NOT double-clawed
        restock_m.assert_not_called()   # NOT double-restocked


# ── The sweep pass decides correctly ──────────────────────────────────────────

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _job(*, job_id=1, tenant_id=1, order="ORD-1", age_min=40,
         status="searching", driver_id=None, redispatch_count=0):
    j = MagicMock()
    j.id = job_id
    j.pk = job_id
    j.tenant_id = tenant_id
    j.order_number = order
    j.created_at = _NOW - timedelta(minutes=age_min)
    j.status = status
    j.driver_id = driver_id
    j.redispatch_count = redispatch_count
    return j


class AutoRefundSweepPassTests(SimpleTestCase):
    def _run(self, *, candidate, locked_job, deadline=30, order="present", refund_result=True):
        """Drive Command._auto_refund_stuck_jobs with the DB collaborators mocked.

        candidate     : the job the (mocked) candidate scan yields (or None for none).
        locked_job    : what the under-lock re-check returns (None = picked up/terminal/gone).
        deadline      : Profile.delivery_auto_refund_minutes for the tenant (0 = disabled).
        order         : the tenant Order load result ("present" → a truthy mock, None → gone).
        refund_result : what the (mocked) shared helper returns — True = this call cancelled,
                        False = the order was already cancelled (a replay the sweep must not
                        re-count or re-alert).
        Returns (refunded_count, refund_helper_mock, alert_owner_mock, order_obj).
        """
        order_obj = MagicMock() if order == "present" else None
        alert_owner = MagicMock()
        tenant_info = lambda tid: ("Resto", "schema1")  # noqa: E731

        with patch("accounts.models.DeliveryJob") as DJ, \
                patch("tenancy.models.Profile") as Prof, \
                patch("menu.models.Order") as OrderM, \
                patch("menu.views.refund_and_cancel_delivery_order") as refund, \
                patch("django_tenants.utils.schema_context", _noop_cm), \
                patch("django.db.transaction.atomic", _noop_cm):
            refund.return_value = refund_result
            for name, val in [
                ("SEARCHING", "searching"), ("ASSIGNED", "assigned"),
                ("AT_RESTAURANT", "at_restaurant"), ("PICKED_UP", "picked_up"),
                ("DELIVERED", "delivered"), ("FAILED", "failed"), ("CANCELLED", "cancelled"),
            ]:
                setattr(DJ.Status, name, val)
            DJ.objects.filter.return_value.filter.return_value = [candidate] if candidate else []
            (DJ.objects.select_for_update.return_value
                .filter.return_value.exclude.return_value.first.return_value) = locked_job
            Prof.objects.filter.return_value.values_list.return_value.first.return_value = deadline
            OrderM.objects.filter.return_value.first.return_value = order_obj

            count = Command()._auto_refund_stuck_jobs(_NOW, tenant_info, alert_owner)
        return count, refund, alert_owner, order_obj

    def test_stuck_pre_pickup_past_deadline_is_refunded(self):
        job = _job(age_min=40, status="searching", driver_id=None)
        count, refund, alert_owner, order_obj = self._run(candidate=job, locked_job=job, deadline=30)
        self.assertEqual(count, 1)
        refund.assert_called_once_with(order_obj, 1)  # (order, tenant_id)
        alert_owner.assert_called_once()

    def test_cap_exhausted_pre_pickup_job_is_refunded(self):
        """Case (b): a job abandoned after the re-dispatch cap (not merely SEARCHING)
        is refunded once past the deadline."""
        job = _job(age_min=40, status="assigned", driver_id=99, redispatch_count=3)
        count, refund, alert_owner, order_obj = self._run(candidate=job, locked_job=job, deadline=30)
        self.assertEqual(count, 1)
        refund.assert_called_once_with(order_obj, 1)

    def test_disabled_when_minutes_zero(self):
        job = _job(age_min=40)
        count, refund, alert_owner, _ = self._run(candidate=job, locked_job=job, deadline=0)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_not_past_deadline_is_skipped(self):
        job = _job(age_min=10)  # only 10 min old, deadline 30
        count, refund, alert_owner, _ = self._run(candidate=job, locked_job=job, deadline=30)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_picked_up_between_scan_and_lock_is_never_refunded(self):
        """The critical guard: the under-lock re-check (which filters picked_up_at IS
        NULL and excludes PICKED_UP/terminal) returns None because a driver picked up
        after the scan → NO refund."""
        job = _job(age_min=40)
        count, refund, alert_owner, _ = self._run(candidate=job, locked_job=None, deadline=30)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_freshly_assigned_job_is_left_for_dispatch(self):
        """A driver was assigned after the scan (job now ASSIGNED, has a driver, under the
        re-dispatch cap): still_stuck is False → let dispatch play out, no refund."""
        scan_job = _job(age_min=40, status="searching", driver_id=None)
        locked = _job(age_min=40, status="assigned", driver_id=99, redispatch_count=0)
        count, refund, alert_owner, _ = self._run(candidate=scan_job, locked_job=locked, deadline=30)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_missing_order_is_skipped(self):
        """If the tenant Order no longer exists, the sweep refunds nothing (leaves the
        orphan job for reconcile_order_refs) rather than crashing."""
        job = _job(age_min=40)
        count, refund, alert_owner, _ = self._run(candidate=job, locked_job=job, deadline=30, order=None)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_no_candidates_is_noop(self):
        count, refund, alert_owner, _ = self._run(candidate=None, locked_job=None, deadline=30)
        self.assertEqual(count, 0)
        refund.assert_not_called()

    def test_already_refunded_by_owner_is_not_recounted(self):
        """Micro-fix: the sweep counts/alerts off the helper's RETURN value. If the owner
        already manually refunded this order (the helper reports False = 'was already
        cancelled'), the sweep must NOT re-count it or re-alert 'auto-refunded'. Before the
        fix did_refund was hard-set True — a later sweep double-counted and re-notified."""
        job = _job(age_min=40, status="searching", driver_id=None)
        count, refund, alert_owner, order_obj = self._run(
            candidate=job, locked_job=job, deadline=30, refund_result=False
        )
        self.assertEqual(count, 0)
        refund.assert_called_once_with(order_obj, 1)  # the helper WAS invoked...
        alert_owner.assert_not_called()               # ...but reported a replay → no alert
