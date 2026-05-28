"""
Tests for reservation/tenant serializer validation logic in sales/serializers.py:
  - ReservationReminderStatsSerializerMixin._safe_count
  - OwnerReservationBulkUpdateSerializer.validate_ids
  - OwnerReservationBulkReminderSerializer.validate_ids
  - TenantLifecycleUpdateSerializer validation

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from sales.serializers import (
    ReservationReminderStatsSerializerMixin,
    OwnerReservationBulkUpdateSerializer,
    OwnerReservationBulkReminderSerializer,
    TenantLifecycleUpdateSerializer,
)


# ══════════════════════════════════════════════════════════════════════════════
# ReservationReminderStatsSerializerMixin._safe_count
# ══════════════════════════════════════════════════════════════════════════════

class SafeCountTests(SimpleTestCase):
    def setUp(self):
        self.mixin = ReservationReminderStatsSerializerMixin()

    def _obj(self, **kwargs):
        return SimpleNamespace(**kwargs)

    def test_returns_int_count(self):
        obj = self._obj(reminder_count=5)
        self.assertEqual(self.mixin.get_reminder_count(obj), 5)

    def test_returns_zero_when_attribute_missing(self):
        obj = self._obj()
        self.assertEqual(self.mixin.get_reminder_count(obj), 0)

    def test_returns_zero_when_none(self):
        obj = self._obj(reminder_count=None)
        self.assertEqual(self.mixin.get_reminder_count(obj), 0)

    def test_returns_zero_when_non_numeric(self):
        obj = self._obj(reminder_count="bad")
        self.assertEqual(self.mixin.get_reminder_count(obj), 0)

    def test_clamps_negative_to_zero(self):
        obj = self._obj(reminder_count=-3)
        self.assertEqual(self.mixin.get_reminder_count(obj), 0)

    def test_reminder_opened_count(self):
        obj = self._obj(reminder_opened_count=2)
        self.assertEqual(self.mixin.get_reminder_opened_count(obj), 2)

    def test_reminder_failed_count(self):
        obj = self._obj(reminder_failed_count=1)
        self.assertEqual(self.mixin.get_reminder_failed_count(obj), 1)

    def test_last_reminder_status_returns_empty_when_missing(self):
        obj = self._obj()
        self.assertEqual(self.mixin.get_last_reminder_status(obj), "")

    def test_last_reminder_status_returns_value(self):
        obj = self._obj(last_reminder_status="sent")
        self.assertEqual(self.mixin.get_last_reminder_status(obj), "sent")

    def test_last_reminder_at_returns_none_when_missing(self):
        obj = self._obj()
        self.assertIsNone(self.mixin.get_last_reminder_at(obj))


# ══════════════════════════════════════════════════════════════════════════════
# OwnerReservationBulkUpdateSerializer.validate_ids
# ══════════════════════════════════════════════════════════════════════════════

class BulkUpdateSerializerTests(SimpleTestCase):
    def test_valid_data_accepted(self):
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": [1, 2, 3], "status": "won"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_deduplicates_ids(self):
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": [1, 2, 1, 3, 2], "status": "won"})
        ser.is_valid()
        self.assertEqual(ser.validated_data["ids"], [1, 2, 3])

    def test_empty_ids_returns_400(self):
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": [], "status": "won"})
        self.assertFalse(ser.is_valid())
        self.assertIn("ids", ser.errors)

    def test_invalid_status_returns_400(self):
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": [1], "status": "invalid_status"})
        self.assertFalse(ser.is_valid())
        self.assertIn("status", ser.errors)

    def test_missing_ids_returns_400(self):
        ser = OwnerReservationBulkUpdateSerializer(data={"status": "won"})
        self.assertFalse(ser.is_valid())
        self.assertIn("ids", ser.errors)

    def test_max_ids_accepted(self):
        """Up to 200 ids allowed."""
        ids = list(range(1, 201))
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": ids, "status": "won"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_over_max_ids_rejected(self):
        ids = list(range(1, 202))  # 201 ids
        ser = OwnerReservationBulkUpdateSerializer(data={"ids": ids, "status": "won"})
        self.assertFalse(ser.is_valid())


# ══════════════════════════════════════════════════════════════════════════════
# OwnerReservationBulkReminderSerializer.validate_ids
# ══════════════════════════════════════════════════════════════════════════════

class BulkReminderSerializerTests(SimpleTestCase):
    def test_valid_data_accepted(self):
        ser = OwnerReservationBulkReminderSerializer(data={"ids": [1, 2]})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_deduplicates_ids(self):
        ser = OwnerReservationBulkReminderSerializer(data={"ids": [5, 5, 3]})
        ser.is_valid()
        self.assertEqual(ser.validated_data["ids"], [5, 3])

    def test_empty_ids_rejected(self):
        ser = OwnerReservationBulkReminderSerializer(data={"ids": []})
        self.assertFalse(ser.is_valid())

    def test_require_failed_last_reminder_defaults_false(self):
        ser = OwnerReservationBulkReminderSerializer(data={"ids": [1]})
        ser.is_valid()
        self.assertFalse(ser.validated_data["require_failed_last_reminder"])

    def test_require_failed_last_reminder_true(self):
        ser = OwnerReservationBulkReminderSerializer(data={"ids": [1], "require_failed_last_reminder": True})
        ser.is_valid()
        self.assertTrue(ser.validated_data["require_failed_last_reminder"])


# ══════════════════════════════════════════════════════════════════════════════
# TenantLifecycleUpdateSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TenantLifecycleUpdateSerializerTests(SimpleTestCase):
    def test_suspend_without_reason_valid(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "suspend"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_reactivate_without_reason_valid(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "reactivate"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_cancel_without_reason_invalid(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "cancel"})
        self.assertFalse(ser.is_valid())
        self.assertIn("reason", ser.errors)

    def test_cancel_with_reason_valid(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "cancel", "reason": "Closing down"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_reason_stripped(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "suspend", "reason": "  moving  "})
        ser.is_valid()
        self.assertEqual(ser.validated_data["reason"], "moving")

    def test_invalid_action_rejected(self):
        ser = TenantLifecycleUpdateSerializer(data={"action": "delete"})
        self.assertFalse(ser.is_valid())
        self.assertIn("action", ser.errors)
