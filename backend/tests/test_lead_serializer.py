from django.test import SimpleTestCase

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
