from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from sales.serializers import LeadSerializer


class LeadSerializerTests(SimpleTestCase):
    def test_lead_serializer_fields_are_exposed(self):
        serializer = LeadSerializer()
        self.assertIn("tenant_slug", serializer.fields)
        self.assertIn("follow_up_due_at", serializer.fields)
        self.assertIn("sla_state", serializer.fields)
        self.assertIn("sla_minutes_overdue", serializer.fields)
        self.assertIn("last_reminder_status", serializer.fields)
        self.assertIn("last_reminder_at", serializer.fields)
        self.assertIn("reminder_count", serializer.fields)
        self.assertIn("reminder_opened_count", serializer.fields)
        self.assertIn("reminder_failed_count", serializer.fields)


class BookedForValidationTests(SimpleTestCase):
    """validate_booked_for guards reservations (acquisition leads send no booked_for)."""

    def _run(self, dt):
        return LeadSerializer().validate_booked_for(dt)

    def test_none_is_allowed(self):
        # Acquisition leads (no reservation time) must still validate.
        self.assertIsNone(self._run(None))

    def test_future_within_horizon_ok(self):
        dt = timezone.now() + timedelta(days=2)
        self.assertEqual(self._run(dt), dt)

    def test_past_rejected(self):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._run(timezone.now() - timedelta(hours=3))

    def test_beyond_horizon_rejected(self):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._run(timezone.now() + timedelta(days=400))
