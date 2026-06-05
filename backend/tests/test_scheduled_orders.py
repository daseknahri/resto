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


class ScheduledTransitionTests(SimpleTestCase):
    def test_scheduled_releases_to_pending_or_cancel(self):
        o = Order(status=Order.Status.SCHEDULED, fulfillment_type=PICKUP)
        allowed = {s.value for s in OwnerOrderStatusUpdateView._allowed_transitions(o)}
        self.assertEqual(allowed, {Order.Status.PENDING.value, Order.Status.CANCELLED.value})
