"""
Tests for advance/scheduled orders (Phase 3.1).

Covers the pure decision logic — no DB:
  - _validate_scheduled_for: ASAP passthrough, dine-in refusal, lead/horizon
    bounds, business-hours enforcement, and the happy path.
  - _within_business_hours: schedule-aware open/closed checks.
  - _customer_can_cancel: a SCHEDULED pickup/delivery order is cancellable.
  - OwnerOrderStatusUpdateView._allowed_transitions: SCHEDULED → {PENDING, CANCELLED}.

All unit-level (SimpleTestCase + lightweight stand-ins).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _sc_cm():
    """No-op schema_context for command tests."""
    import contextlib
    return contextlib.nullcontext()

from django.test import SimpleTestCase
from django.utils import timezone

from menu.models import Order
from menu.views import (
    _validate_scheduled_for,
    _within_business_hours,
    _customer_can_cancel,
    OwnerOrderStatusUpdateView,
)

PICKUP = Order.FulfillmentType.PICKUP
DELIVERY = Order.FulfillmentType.DELIVERY
TABLE = Order.FulfillmentType.TABLE

_ALWAYS_OPEN = {d: {"enabled": True, "open": "00:00", "close": "23:59"}
                for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
_ALWAYS_CLOSED = {d: {"enabled": True, "open": "00:00", "close": "00:00"}
                  for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _profile(schedule=None, tz="UTC"):
    # No schedule configured → scheduling is unconstrained by hours.
    return SimpleNamespace(business_hours_schedule=schedule or {}, timezone=tz)


class ValidateScheduledForTests(SimpleTestCase):
    def setUp(self):
        # Hold the ClosureDate lookup neutral (no DB) — default "not a closure date".
        p = patch("menu.views.is_closure_date", return_value=False)
        self.closure = p.start()
        self.addCleanup(p.stop)

    def test_none_passes_through_as_asap(self):
        self.assertEqual(_validate_scheduled_for(_profile(), PICKUP, None), (None, None))

    def test_dine_in_is_refused(self):
        when = timezone.now() + timedelta(hours=2)
        dt, err = _validate_scheduled_for(_profile(), TABLE, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_not_supported")

    def test_too_soon_is_refused(self):
        when = timezone.now() + timedelta(minutes=10)  # < 30 min lead
        dt, err = _validate_scheduled_for(_profile(), PICKUP, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_too_soon")

    def test_too_far_is_refused(self):
        when = timezone.now() + timedelta(days=20)  # > 14 day horizon
        dt, err = _validate_scheduled_for(_profile(), DELIVERY, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_too_far")

    def test_valid_when_no_schedule_configured(self):
        when = timezone.now() + timedelta(hours=3)
        dt, err = _validate_scheduled_for(_profile(), PICKUP, when)
        self.assertIsNone(err)
        self.assertEqual(dt, when)

    def test_refused_when_outside_business_hours(self):
        when = timezone.now() + timedelta(days=1)
        dt, err = _validate_scheduled_for(_profile(_ALWAYS_CLOSED), PICKUP, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_closed")

    def test_valid_inside_business_hours(self):
        # Pick a midday instant so the always-open window safely contains it.
        when = (timezone.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        dt, err = _validate_scheduled_for(_profile(_ALWAYS_OPEN), DELIVERY, when)
        self.assertIsNone(err)
        self.assertEqual(dt, when)

    # ── Holiday / closure dates ────────────────────────────────────────────────
    # The closed storefront steers customers to "Schedule for later"; a requested time on
    # an owner-declared closure day must be refused, or it would be accepted, prepaid, and
    # released to the kitchen on the holiday. Shared by the direct AND marketplace flows
    # (both call _validate_scheduled_for), so this is the single seam under test.

    def test_refused_on_a_closure_date_when_no_schedule_configured(self):
        self.closure.return_value = True
        when = timezone.now() + timedelta(days=2)
        dt, err = _validate_scheduled_for(_profile(), PICKUP, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_closed")

    def test_refused_on_a_closure_date_even_inside_the_schedule_window(self):
        self.closure.return_value = True
        when = (timezone.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        dt, err = _validate_scheduled_for(_profile(_ALWAYS_OPEN), DELIVERY, when)
        self.assertIsNone(dt)
        self.assertEqual(err, "schedule_closed")

    def test_closure_lookup_receives_the_scheduled_instants_tenant_local_date(self):
        # 23:30 UTC two days out is already the NEXT calendar day in Tokyo (UTC+9): the
        # closure lookup must use the tenant-local date of the SCHEDULED instant, not the
        # server/UTC date and not "today".
        when = (timezone.now() + timedelta(days=2)).replace(hour=23, minute=30, second=0, microsecond=0)
        dt, err = _validate_scheduled_for(_profile(tz="Asia/Tokyo"), PICKUP, when)
        self.assertIsNone(err)
        self.closure.assert_called_once_with(when.date() + timedelta(days=1))

    def test_open_day_with_no_closure_is_accepted(self):
        self.closure.return_value = False
        when = timezone.now() + timedelta(days=2)
        dt, err = _validate_scheduled_for(_profile(), PICKUP, when)
        self.assertIsNone(err)
        self.assertEqual(dt, when)

    def test_closure_lookup_skipped_when_an_earlier_check_already_refused(self):
        when = timezone.now() + timedelta(minutes=10)  # too soon
        dt, err = _validate_scheduled_for(_profile(), PICKUP, when)
        self.assertEqual(err, "schedule_too_soon")
        self.closure.assert_not_called()


class WithinBusinessHoursTests(SimpleTestCase):
    def test_no_schedule_is_always_within(self):
        self.assertTrue(_within_business_hours(_profile(), timezone.now() + timedelta(days=1)))

    def test_all_days_disabled_is_unconstrained(self):
        sched = {d: {"enabled": False, "open": "09:00", "close": "17:00"} for d in _ALWAYS_OPEN}
        self.assertTrue(_within_business_hours(_profile(sched), timezone.now() + timedelta(days=1)))

    def test_closed_window_rejects(self):
        when = (timezone.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        self.assertFalse(_within_business_hours(_profile(_ALWAYS_CLOSED), when))


class CustomerCanCancelScheduledTests(SimpleTestCase):
    def test_scheduled_pickup_is_cancellable(self):
        o = Order(status=Order.Status.SCHEDULED, fulfillment_type=PICKUP)
        self.assertTrue(_customer_can_cancel(o))

    def test_scheduled_delivery_is_cancellable(self):
        o = Order(status=Order.Status.SCHEDULED, fulfillment_type=DELIVERY)
        self.assertTrue(_customer_can_cancel(o))

    def test_scheduled_dine_in_is_not_cancellable(self):
        o = Order(status=Order.Status.SCHEDULED, fulfillment_type=TABLE)
        self.assertFalse(_customer_can_cancel(o))


class ReleaseScheduledMirrorTests(SimpleTestCase):
    """Wave M M-04: scheduled release stamps food_ready_at on the job it
    creates for a released delivery order. R6-13: release honours the
    restaurant's auto-accept flag."""

    def _run(self, auto_accept):
        """Run the release command over one due delivery order; return the
        claim update kwargs, the ETA call kwargs, the food-ready mirror mock
        and the order mock."""
        from decimal import Decimal
        from django.utils import timezone
        from menu.management.commands.release_scheduled_orders import Command

        tenant = MagicMock()
        tenant.id = 7
        tenant.schema_name = "resto7"
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.profile = MagicMock()
        tenant.profile.auto_accept_orders = auto_accept
        tenant.profile.whatsapp = ""
        tenant.profile.phone = ""

        order = MagicMock()
        order.pk = 11
        order.order_number = "ORD-S1"
        order.scheduled_for = timezone.now()
        order.status = "scheduled"
        order.fulfillment_type = "delivery"
        order.customer_name = "A"
        order.total = Decimal("50")
        order.currency = "MAD"
        order.delivery_address = "2 Ave"
        order.delivery_lat = 35.71
        order.delivery_lng = -5.81
        order.delivery_fee = Decimal("15")

        with patch("menu.management.commands.release_scheduled_orders.Tenant") as TenantM, \
                patch("menu.models.Order") as OrderM, \
                patch("menu.management.commands.release_scheduled_orders.schema_context", side_effect=lambda *a, **k: _sc_cm()), \
                patch("menu.views._placement_eta_minutes", return_value=25) as eta_mock, \
                patch("menu.views._delivery_job_ready_minutes", return_value=25), \
                patch("menu.views._broadcast_order_change"), \
                patch("menu.push.push_new_order"), \
                patch("accounts.models.DeliveryJob") as DJ, \
                patch("tenancy.delivery_pricing.split_delivery_fee", return_value={
                    "driver_payout": Decimal("10"), "platform_commission": Decimal("0"),
                    "commission_pct": Decimal("0")}), \
                patch("accounts.dispatch.start_dispatch"), \
                patch("accounts.delivery_service.set_delivery_job_food_ready") as mirror:
            TenantM.LifecycleStatus.ACTIVE = "active"
            (TenantM.objects.filter.return_value.exclude.return_value
                .select_related.return_value) = [tenant]
            OrderM.Status.SCHEDULED = "scheduled"
            OrderM.Status.PENDING = "pending"
            OrderM.Status.CONFIRMED = "confirmed"
            OrderM.FulfillmentType.DELIVERY = "delivery"
            OrderM.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [order]
            OrderM.objects.filter.return_value.update.return_value = 1
            DJ.Status.SEARCHING = "searching"
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.style = MagicMock()
            cmd.handle(dry_run=False)
            return {
                "update_kwargs": OrderM.objects.filter.return_value.update.call_args[1],
                "eta_kwargs": eta_mock.call_args[1],
                "mirror": mirror,
                "order": order,
            }

    def test_release_delivery_stamps_food_ready(self):
        out = self._run(auto_accept=False)
        out["mirror"].assert_called_once_with(7, "ORD-S1", 25)

    def test_release_auto_accepts_when_flag_on(self):
        """R6-13: auto-accept restaurant → SCHEDULED releases straight to
        CONFIRMED with the ETA quoted up front (default_prep_minutes)."""
        out = self._run(auto_accept=True)
        self.assertEqual(out["update_kwargs"]["status"], "confirmed")
        self.assertEqual(out["update_kwargs"]["estimated_ready_minutes"], 25)
        self.assertEqual(out["eta_kwargs"], {"auto_accept": True})
        self.assertEqual(out["order"].status, "confirmed")

    def test_release_stays_pending_when_flag_off(self):
        """R6-13: flag off → exact current behaviour: PENDING, ETA quoted the
        placement way (no auto-accept bump)."""
        out = self._run(auto_accept=False)
        self.assertEqual(out["update_kwargs"]["status"], "pending")
        self.assertEqual(out["eta_kwargs"], {"auto_accept": False})
        self.assertEqual(out["order"].status, "pending")


class ScheduledTransitionTests(SimpleTestCase):
    def test_scheduled_releases_to_pending_or_cancel(self):
        o = Order(status=Order.Status.SCHEDULED, fulfillment_type=PICKUP)
        allowed = {s.value for s in OwnerOrderStatusUpdateView._allowed_transitions(o)}
        self.assertEqual(allowed, {Order.Status.PENDING.value, Order.Status.CANCELLED.value})
