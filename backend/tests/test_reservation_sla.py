from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from sales.sla import (
    SLA_STATE_DUE_SOON,
    SLA_STATE_NOT_APPLICABLE,
    SLA_STATE_ON_TRACK,
    SLA_STATE_OVERDUE,
    SLA_STATE_RESOLVED,
    reservation_overdue_cutoff,
    reservation_sla_snapshot,
)


class ReservationSlaTests(SimpleTestCase):
    @override_settings(RESERVATION_SLA_NEW_MINUTES=30, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_overdue_snapshot_for_new_reservation(self):
        now = timezone.now()
        created_at = now - timedelta(minutes=31)
        data = reservation_sla_snapshot(
            source="table_reservation",
            status="new",
            created_at=created_at,
            now=now,
        )
        self.assertEqual(data["sla_state"], SLA_STATE_OVERDUE)
        self.assertGreaterEqual(data["sla_minutes_overdue"], 1)
        self.assertEqual(data["sla_seconds_remaining"], 0)

    @override_settings(RESERVATION_SLA_NEW_MINUTES=30, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_due_soon_snapshot_for_new_reservation(self):
        now = timezone.now()
        created_at = now - timedelta(minutes=23)
        data = reservation_sla_snapshot(
            source="reservation",
            status="new",
            created_at=created_at,
            now=now,
        )
        self.assertEqual(data["sla_state"], SLA_STATE_DUE_SOON)
        self.assertEqual(data["sla_minutes_overdue"], 0)
        self.assertGreater(data["sla_seconds_remaining"], 0)

    @override_settings(RESERVATION_SLA_NEW_MINUTES=30, RESERVATION_SLA_DUE_SOON_MINUTES=10)
    def test_on_track_snapshot_for_new_reservation(self):
        now = timezone.now()
        created_at = now - timedelta(minutes=10)
        data = reservation_sla_snapshot(
            source="reserve_table",
            status="new",
            created_at=created_at,
            now=now,
        )
        self.assertEqual(data["sla_state"], SLA_STATE_ON_TRACK)
        self.assertEqual(data["sla_minutes_overdue"], 0)
        self.assertGreater(data["sla_seconds_remaining"], 0)

    def test_resolved_snapshot_for_non_new_status(self):
        now = timezone.now()
        created_at = now - timedelta(minutes=120)
        data = reservation_sla_snapshot(
            source="table_reservation",
            status="contacted",
            created_at=created_at,
            now=now,
        )
        self.assertEqual(data["sla_state"], SLA_STATE_RESOLVED)
        self.assertEqual(data["sla_minutes_overdue"], 0)
        self.assertEqual(data["sla_seconds_remaining"], 0)

    def test_not_applicable_snapshot_for_non_reservation_source(self):
        now = timezone.now()
        created_at = now - timedelta(minutes=20)
        data = reservation_sla_snapshot(
            source="landing_contact",
            status="new",
            created_at=created_at,
            now=now,
        )
        self.assertEqual(data["sla_state"], SLA_STATE_NOT_APPLICABLE)
        self.assertIsNone(data["follow_up_due_at"])

    @override_settings(RESERVATION_SLA_NEW_MINUTES=25)
    def test_overdue_cutoff_uses_configured_minutes(self):
        now = timezone.now()
        cutoff = reservation_overdue_cutoff(now=now)
        self.assertEqual(cutoff, now - timedelta(minutes=25))
