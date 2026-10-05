"""DishSerializer.validate_availability_schedule — the shape the onboarding wizard sends.

The wizard's StepDishes "Restrict availability" editor (days + from/to times) was dead: the
client never sent ``availability_schedule``. Now that it does, the serializer validates and
normalizes it, because ``schedule_window.day_time_window_open`` compares zero-padded "HH:MM"
strings lexically and treats a malformed/half-set window as "no restriction" — a bad value
would silently never restrict instead of failing.

SimpleTestCase (no DB). Run with DJANGO_DEBUG=True.
"""
from datetime import datetime

from django.test import SimpleTestCase
from rest_framework import serializers

from menu.schedule_window import day_time_window_open
from menu.serializers import DishSerializer


def _v(value):
    return DishSerializer().validate_availability_schedule(value)


class AvailabilityScheduleValidationTests(SimpleTestCase):
    def test_null_and_blank_mean_always_available(self):
        self.assertIsNone(_v(None))
        self.assertIsNone(_v(""))

    def test_wizard_shape_is_normalized(self):
        out = _v({"days": ["FRI", "mon", " mon "], "time_start": "18:00", "time_end": "22:00", "x": 1})
        self.assertEqual(out, {"days": ["mon", "fri"], "time_start": "18:00", "time_end": "22:00"})

    def test_seconds_from_a_time_input_are_dropped(self):
        out = _v({"days": [], "time_start": "08:00:00", "time_end": "11:30:00"})
        self.assertEqual(out, {"days": [], "time_start": "08:00", "time_end": "11:30"})

    def test_restrict_ticked_with_nothing_set_collapses_to_null(self):
        # The wizard's toggle creates {days: [], time_start: "", time_end: ""} — restricts nothing.
        self.assertIsNone(_v({"days": [], "time_start": "", "time_end": ""}))

    def test_days_only_window_is_kept(self):
        self.assertEqual(_v({"days": ["sat", "sun"]}), {"days": ["sat", "sun"], "time_start": "", "time_end": ""})

    def test_overnight_window_is_accepted(self):
        out = _v({"days": ["fri"], "time_start": "22:00", "time_end": "02:00"})
        self.assertEqual(out["time_start"], "22:00")
        self.assertEqual(out["time_end"], "02:00")

    def test_rejects_unknown_day_token(self):
        with self.assertRaises(serializers.ValidationError):
            _v({"days": ["monday"], "time_start": "", "time_end": ""})

    def test_rejects_non_list_days_and_non_object(self):
        with self.assertRaises(serializers.ValidationError):
            _v({"days": "mon"})
        with self.assertRaises(serializers.ValidationError):
            _v(["mon"])

    def test_rejects_malformed_times(self):
        for bad in ("9:00", "24:00", "18:60", "18h30", "١٨:٠٠"):
            with self.subTest(bad=bad), self.assertRaises(serializers.ValidationError):
                _v({"days": [], "time_start": bad, "time_end": "23:00"})

    def test_rejects_half_set_window(self):
        with self.assertRaises(serializers.ValidationError):
            _v({"days": ["mon"], "time_start": "18:00", "time_end": ""})

    def test_normalized_value_actually_restricts_at_order_time(self):
        schedule = _v({"days": ["FRI"], "time_start": "18:00", "time_end": "22:00"})
        friday_evening = datetime(2026, 10, 9, 19, 0)   # a Friday
        monday_evening = datetime(2026, 10, 5, 19, 0)   # a Monday
        args = (schedule["days"], schedule["time_start"], schedule["time_end"])
        self.assertTrue(day_time_window_open(*args, now_local=friday_evening))
        self.assertFalse(day_time_window_open(*args, now_local=monday_evening))

    def test_validator_runs_through_the_serializer_field(self):
        s = DishSerializer(data={"availability_schedule": {"days": ["tue"], "time_start": "7:00", "time_end": "9:00"}},
                           partial=True)
        self.assertFalse(s.is_valid())
        self.assertIn("availability_schedule", s.errors)


class StockQtyWriteContractTests(SimpleTestCase):
    """Contract the wizard's live-stock guard relies on (not a regression test): a PUT that
    OMITS stock_qty must leave the stored (order-decremented) value untouched. That holds only
    while the field is optional with no serializer default — pin it."""

    def test_stock_qty_is_optional_with_no_default(self):
        field = DishSerializer().fields["stock_qty"]
        self.assertFalse(field.required)
        self.assertIs(field.default, serializers.empty)
