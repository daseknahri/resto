"""
Unit tests for the smaller helper functions in sales/sla.py that are not
covered by the higher-level reservation_sla_snapshot tests:

  reservation_sla_minutes()        — reads RESERVATION_SLA_NEW_MINUTES setting
  reservation_due_soon_minutes()   — reads RESERVATION_SLA_DUE_SOON_MINUTES setting
  is_reservation_source(source)    — checks the source string against known values
  reservation_follow_up_due_at(created_at)  — None-safe timedelta addition
  reservation_due_soon_cutoff(now) — computes the "due soon" window start

All tests are unit-level (SimpleTestCase — no real DB, no network).
"""
from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from sales.sla import (
    is_reservation_source,
    reservation_due_soon_cutoff,
    reservation_due_soon_minutes,
    reservation_follow_up_due_at,
    reservation_sla_minutes,
)


# ══════════════════════════════════════════════════════════════════════════════
# reservation_sla_minutes
# ══════════════════════════════════════════════════════════════════════════════

class ReservationSlaMintuesTests(SimpleTestCase):
    """Reads RESERVATION_SLA_NEW_MINUTES; defaults to 30; minimum 1."""

    def test_default_when_setting_absent(self):
        with self.settings():
            # Remove the attribute if present
            from django.conf import settings as s
            had = hasattr(s, "RESERVATION_SLA_NEW_MINUTES")
            if had:
                original = s.RESERVATION_SLA_NEW_MINUTES
                del s.RESERVATION_SLA_NEW_MINUTES
            try:
                self.assertEqual(reservation_sla_minutes(), 30)
            finally:
                if had:
                    s.RESERVATION_SLA_NEW_MINUTES = original

    @override_settings(RESERVATION_SLA_NEW_MINUTES=45)
    def test_configured_integer_returned(self):
        self.assertEqual(reservation_sla_minutes(), 45)

    @override_settings(RESERVATION_SLA_NEW_MINUTES="60")
    def test_string_integer_accepted(self):
        self.assertEqual(reservation_sla_minutes(), 60)

    @override_settings(RESERVATION_SLA_NEW_MINUTES=0)
    def test_zero_clamped_to_one(self):
        self.assertEqual(reservation_sla_minutes(), 1)

    @override_settings(RESERVATION_SLA_NEW_MINUTES=-10)
    def test_negative_clamped_to_one(self):
        self.assertEqual(reservation_sla_minutes(), 1)

    @override_settings(RESERVATION_SLA_NEW_MINUTES="bad")
    def test_non_numeric_falls_back_to_30(self):
        self.assertEqual(reservation_sla_minutes(), 30)

    @override_settings(RESERVATION_SLA_NEW_MINUTES=None)
    def test_none_falls_back_to_30(self):
        self.assertEqual(reservation_sla_minutes(), 30)


# ══════════════════════════════════════════════════════════════════════════════
# reservation_due_soon_minutes
# ══════════════════════════════════════════════════════════════════════════════

class ReservationDueSoonMinutesTests(SimpleTestCase):
    """Reads RESERVATION_SLA_DUE_SOON_MINUTES; defaults to 10; minimum 1."""

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES=15)
    def test_configured_value_returned(self):
        self.assertEqual(reservation_due_soon_minutes(), 15)

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES="5")
    def test_string_integer_accepted(self):
        self.assertEqual(reservation_due_soon_minutes(), 5)

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES=0)
    def test_zero_clamped_to_one(self):
        self.assertEqual(reservation_due_soon_minutes(), 1)

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES=-3)
    def test_negative_clamped_to_one(self):
        self.assertEqual(reservation_due_soon_minutes(), 1)

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES="invalid")
    def test_non_numeric_falls_back_to_10(self):
        self.assertEqual(reservation_due_soon_minutes(), 10)

    @override_settings(RESERVATION_SLA_DUE_SOON_MINUTES=None)
    def test_none_falls_back_to_10(self):
        self.assertEqual(reservation_due_soon_minutes(), 10)


# ══════════════════════════════════════════════════════════════════════════════
# is_reservation_source
# ══════════════════════════════════════════════════════════════════════════════

class IsReservationSourceTests(SimpleTestCase):
    """Recognises the three canonical reservation-source strings."""

    def test_table_reservation_is_recognised(self):
        self.assertTrue(is_reservation_source("table_reservation"))

    def test_reservation_is_recognised(self):
        self.assertTrue(is_reservation_source("reservation"))

    def test_reserve_table_is_recognised(self):
        self.assertTrue(is_reservation_source("reserve_table"))

    def test_uppercase_is_normalised(self):
        self.assertTrue(is_reservation_source("TABLE_RESERVATION"))

    def test_leading_trailing_whitespace_stripped(self):
        self.assertTrue(is_reservation_source("  reservation  "))

    def test_unknown_source_returns_false(self):
        self.assertFalse(is_reservation_source("landing_contact"))

    def test_empty_string_returns_false(self):
        self.assertFalse(is_reservation_source(""))

    def test_none_returns_false(self):
        self.assertFalse(is_reservation_source(None))


# ══════════════════════════════════════════════════════════════════════════════
# reservation_follow_up_due_at
# ══════════════════════════════════════════════════════════════════════════════

class ReservationFollowUpDueAtTests(SimpleTestCase):
    """None → None; datetime → created_at + SLA minutes."""

    def test_none_created_at_returns_none(self):
        self.assertIsNone(reservation_follow_up_due_at(None))

    @override_settings(RESERVATION_SLA_NEW_MINUTES=30)
    def test_datetime_adds_sla_minutes(self):
        now = timezone.now()
        result = reservation_follow_up_due_at(now)
        self.assertEqual(result, now + timedelta(minutes=30))

    @override_settings(RESERVATION_SLA_NEW_MINUTES=60)
    def test_custom_sla_minutes_applied(self):
        now = timezone.now()
        result = reservation_follow_up_due_at(now)
        self.assertEqual(result, now + timedelta(minutes=60))


# ══════════════════════════════════════════════════════════════════════════════
# reservation_due_soon_cutoff
# ══════════════════════════════════════════════════════════════════════════════

class ReservationDueSoonCutoffTests(SimpleTestCase):
    """Returns now - max(0, sla_minutes - due_soon_minutes)."""

    @override_settings(RESERVATION_SLA_NEW_MINUTES=30, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_cutoff_is_sla_minus_due_soon_minutes_before_now(self):
        """sla=30, due_soon=10 → window start = now - 20 min."""
        now = timezone.now()
        cutoff = reservation_due_soon_cutoff(now=now)
        self.assertEqual(cutoff, now - timedelta(minutes=20))

    @override_settings(RESERVATION_SLA_NEW_MINUTES=15, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_small_sla_window(self):
        """sla=15, due_soon=10 → window start = now - 5 min."""
        now = timezone.now()
        cutoff = reservation_due_soon_cutoff(now=now)
        self.assertEqual(cutoff, now - timedelta(minutes=5))

    @override_settings(RESERVATION_SLA_NEW_MINUTES=5, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_due_soon_larger_than_sla_clamps_to_zero(self):
        """max(0, 5 - 10) = 0 → cutoff == now."""
        now = timezone.now()
        cutoff = reservation_due_soon_cutoff(now=now)
        self.assertEqual(cutoff, now)
