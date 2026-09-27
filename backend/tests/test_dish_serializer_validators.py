"""
Unit tests for DishSerializer, CategorySerializer, and SuperCategorySerializer
field-level validators and computed fields in menu/serializers.py:

  DishSerializer
    - validate_name
    - validate_description
    - validate_price
    - validate_tags
    - validate_allergens
    - validate_currency
    - validate_stock_qty
    - get_is_schedule_available

  CategorySerializer
    - validate_name
    - validate_description

  SuperCategorySerializer
    - validate_name
    - validate_disabled_note

All tests are unit-level (SimpleTestCase + mocks — no real DB).
The schedule-availability tests inject a tenant-local "now" via serializer context
(the M7 fix evaluates the window in the restaurant's wall-clock, not server UTC).
"""
import datetime as dt_module
from datetime import timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from menu.serializers import CategorySerializer, DishSerializer, SuperCategorySerializer


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_name
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateNameTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_valid_name_returned(self):
        self.assertEqual(self._s().validate_name("My Dish"), "My Dish")

    def test_name_stripped(self):
        self.assertEqual(self._s().validate_name("  Pasta  "), "Pasta")

    def test_two_chars_accepted(self):
        self.assertEqual(self._s().validate_name("AB"), "AB")

    def test_one_char_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("A")

    def test_empty_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("")

    def test_none_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name(None)

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("   ")


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_description
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateDescriptionTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_empty_returns_empty(self):
        self.assertEqual(self._s().validate_description(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(self._s().validate_description(None), "")

    def test_text_stripped(self):
        self.assertEqual(self._s().validate_description("  Nice dish  "), "Nice dish")

    def test_exactly_1500_chars_accepted(self):
        text = "a" * 1500
        self.assertEqual(len(self._s().validate_description(text)), 1500)

    def test_over_1500_chars_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_description("a" * 1501)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_price
# ══════════════════════════════════════════════════════════════════════════════

class DishValidatePriceTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_zero_accepted(self):
        self.assertEqual(self._s().validate_price(Decimal("0")), Decimal("0"))

    def test_positive_accepted(self):
        self.assertEqual(self._s().validate_price(Decimal("12.50")), Decimal("12.50"))

    def test_negative_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_price(Decimal("-0.01"))

    def test_none_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_price(None)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_tags
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateTagsTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_none_returns_empty_list(self):
        self.assertEqual(self._s().validate_tags(None), [])

    def test_empty_list_returns_empty(self):
        self.assertEqual(self._s().validate_tags([]), [])

    def test_non_list_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_tags("vegan")

    def test_tags_lowercased(self):
        result = self._s().validate_tags(["BURGER", "Vegan"])
        self.assertIn("burger", result)
        self.assertIn("vegan", result)

    def test_duplicates_removed(self):
        result = self._s().validate_tags(["burger", "BURGER", "burger"])
        self.assertEqual(result, ["burger"])

    def test_empty_string_tags_filtered(self):
        result = self._s().validate_tags(["", "  ", "pizza"])
        self.assertEqual(result, ["pizza"])

    def test_tags_truncated_to_32_chars(self):
        long_tag = "a" * 50
        result = self._s().validate_tags([long_tag])
        self.assertEqual(len(result[0]), 32)

    def test_order_preserved_for_distinct_tags(self):
        result = self._s().validate_tags(["vegan", "spicy", "hot"])
        self.assertEqual(result, ["vegan", "spicy", "hot"])


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_allergens
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateAllergensTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_none_returns_empty_list(self):
        self.assertEqual(self._s().validate_allergens(None), [])

    def test_empty_list_returns_empty(self):
        self.assertEqual(self._s().validate_allergens([]), [])

    def test_non_list_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_allergens("gluten")

    def test_valid_allergen_accepted(self):
        result = self._s().validate_allergens(["gluten"])
        self.assertIn("gluten", result)

    def test_multiple_valid_allergens_accepted(self):
        result = self._s().validate_allergens(["gluten", "milk", "eggs"])
        self.assertEqual(len(result), 3)

    def test_unknown_allergen_filtered_out(self):
        result = self._s().validate_allergens(["gluten", "unicorn_dust"])
        self.assertEqual(result, ["gluten"])

    def test_all_unknown_returns_empty(self):
        result = self._s().validate_allergens(["unknown1", "unknown2"])
        self.assertEqual(result, [])

    def test_duplicates_removed(self):
        result = self._s().validate_allergens(["gluten", "GLUTEN"])
        self.assertEqual(result, ["gluten"])

    def test_all_14_allergens_accepted(self):
        all_allergens = [
            "gluten", "crustaceans", "eggs", "fish", "peanuts", "soy",
            "milk", "tree_nuts", "celery", "mustard", "sesame",
            "sulphites", "lupin", "molluscs",
        ]
        result = self._s().validate_allergens(all_allergens)
        self.assertEqual(len(result), 14)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_currency
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateCurrencyTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_uppercase_currency_accepted(self):
        self.assertEqual(self._s().validate_currency("USD"), "USD")

    def test_lowercase_uppercased(self):
        self.assertEqual(self._s().validate_currency("usd"), "USD")

    def test_mixed_case_uppercased(self):
        self.assertEqual(self._s().validate_currency("mAd"), "MAD")

    def test_too_short_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_currency("US")

    def test_too_long_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_currency("USDA")

    def test_non_alpha_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_currency("U$D")

    def test_empty_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_currency("")

    def test_none_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_currency(None)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.validate_stock_qty
# ══════════════════════════════════════════════════════════════════════════════

class DishValidateStockQtyTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def test_none_returns_none(self):
        self.assertIsNone(self._s().validate_stock_qty(None))

    def test_zero_accepted(self):
        self.assertEqual(self._s().validate_stock_qty(0), 0)

    def test_positive_accepted(self):
        self.assertEqual(self._s().validate_stock_qty(100), 100)

    def test_negative_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_stock_qty(-1)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.get_is_schedule_available
# ══════════════════════════════════════════════════════════════════════════════

# 2024-06-03 is a Monday (weekday 0) — verified: Jan 1 2024 is Monday. These are the
# tenant-local "now" the serializer evaluates the window against (M7), injected via
# serializer context rather than by patching the process clock.
_MONDAY_14H = dt_module.datetime(2024, 6, 3, 14, 30, 0)   # Mon 14:30
_MONDAY_8H  = dt_module.datetime(2024, 6, 3,  8,  0, 0)   # Mon 08:00
_MONDAY_22H = dt_module.datetime(2024, 6, 3, 22, 30, 0)   # Mon 22:30
_MONDAY_23H = dt_module.datetime(2024, 6, 3, 23,  0, 0)   # Mon 23:00
_MONDAY_10H = dt_module.datetime(2024, 6, 3, 10,  0, 0)   # Mon 10:00


def _tz_aware_mock_dt(fixed_utc: dt_module.datetime):
    """datetime stand-in whose .now(tz) converts a FIXED UTC instant into the asked tz —
    lets a test prove the window is read in the tenant's wall-clock, not the server's."""
    class _M(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)
    return _M


class DishGetIsScheduleAvailableTests(SimpleTestCase):
    def _s(self, now_local=None):
        # M7: the window is evaluated against a tenant-local "now" from serializer context.
        ctx = {"schedule_now_local": now_local} if now_local is not None else {}
        return DishSerializer(context=ctx)

    def _obj(self, schedule):
        return SimpleNamespace(availability_schedule=schedule)

    # ── schedule absent / invalid (None short-circuit — no clock needed) ────
    def test_no_schedule_returns_none(self):
        self.assertIsNone(self._s().get_is_schedule_available(self._obj(None)))

    def test_empty_schedule_none_returns_none(self):
        obj = SimpleNamespace()  # no availability_schedule attribute
        self.assertIsNone(self._s().get_is_schedule_available(obj))

    def test_non_dict_schedule_returns_none(self):
        self.assertIsNone(self._s().get_is_schedule_available(self._obj("09:00-22:00")))

    def test_empty_dict_returns_none(self):
        """Empty dict is falsy — same as no schedule → None."""
        self.assertIsNone(self._s().get_is_schedule_available(self._obj({})))

    # ── day restriction ───────────────────────────────────────────────────
    def test_matching_day_no_time_restriction_is_true(self):
        obj = self._obj({"days": ["mon"]})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    def test_non_matching_day_returns_false(self):
        """Monday but schedule only allows tue/wed."""
        obj = self._obj({"days": ["tue", "wed"]})
        self.assertFalse(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    def test_all_days_always_passes_day_check(self):
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        obj = self._obj({"days": all_days})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    def test_empty_days_list_no_day_restriction(self):
        obj = self._obj({"days": []})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    # ── time restriction ──────────────────────────────────────────────────
    def test_within_time_window_is_true(self):
        obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))  # 14:30

    def test_before_time_window_is_false(self):
        obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
        self.assertFalse(self._s(_MONDAY_8H).get_is_schedule_available(obj))  # 08:00

    def test_after_time_window_is_false(self):
        obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
        self.assertFalse(self._s(_MONDAY_22H).get_is_schedule_available(obj))  # 22:30

    # ── overnight window (time_start > time_end) ────────────────────────────
    def test_overnight_window_inside_is_true(self):
        """22:00-02:00, now 23:00 → inside (>= start)."""
        obj = self._obj({"time_start": "22:00", "time_end": "02:00"})
        self.assertTrue(self._s(_MONDAY_23H).get_is_schedule_available(obj))

    def test_overnight_window_outside_is_false(self):
        """22:00-02:00, now 10:00 → outside."""
        obj = self._obj({"time_start": "22:00", "time_end": "02:00"})
        self.assertFalse(self._s(_MONDAY_10H).get_is_schedule_available(obj))

    # ── malformed time → degrade to available, never raise ─────────────────
    def test_invalid_time_format_does_not_raise_returns_true(self):
        obj = self._obj({"time_start": "bad", "time_end": "also_bad"})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    # ── combined day + time restriction ───────────────────────────────────
    def test_correct_day_and_within_time_is_true(self):
        obj = self._obj({"days": ["mon"], "time_start": "09:00", "time_end": "22:00"})
        self.assertTrue(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    def test_wrong_day_even_with_valid_time_is_false(self):
        obj = self._obj({"days": ["tue"], "time_start": "09:00", "time_end": "22:00"})
        self.assertFalse(self._s(_MONDAY_14H).get_is_schedule_available(obj))

    # ── M7 regression: window read in the TENANT's wall-clock, not server UTC ──
    def test_evaluated_in_tenant_local_time_not_server_utc(self):
        """The SAME instant yields opposite verdicts for two tenants in different
        timezones — proving the weekday/HH:MM derive from the restaurant's local clock
        (a Profile in context → menu.views._profile_now), not the server's UTC."""
        schedule = {"days": ["mon"], "time_start": "09:00", "time_end": "22:00"}
        obj = self._obj(schedule)
        # 2024-06-03 23:30 UTC (Monday). America/New_York (EDT, UTC-4) = Mon 19:30 → inside
        # 09:00-22:00; UTC = Mon 23:30 → after 22:00.
        instant = dt_module.datetime(2024, 6, 3, 23, 30, 0, tzinfo=timezone.utc)
        with patch("datetime.datetime", _tz_aware_mock_dt(instant)):
            ny = DishSerializer(context={"profile": SimpleNamespace(timezone="America/New_York")})
            self.assertTrue(ny.get_is_schedule_available(obj))
            utc = DishSerializer(context={"profile": SimpleNamespace(timezone="UTC")})
            self.assertFalse(utc.get_is_schedule_available(obj))

    def test_no_context_falls_back_to_utc_without_crashing(self):
        """A context-less serializer must never crash — it falls back to UTC. An all-day
        window (no times) is tz-independent, so this stays deterministic."""
        obj = self._obj({"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]})
        self.assertTrue(DishSerializer().get_is_schedule_available(obj))


# ══════════════════════════════════════════════════════════════════════════════
# CategorySerializer.validate_name / validate_description
# ══════════════════════════════════════════════════════════════════════════════

class CategoryValidateNameTests(SimpleTestCase):
    def _s(self):
        return CategorySerializer()

    def test_valid_name_returned(self):
        self.assertEqual(self._s().validate_name("Main Dishes"), "Main Dishes")

    def test_stripped(self):
        self.assertEqual(self._s().validate_name("  Pasta  "), "Pasta")

    def test_two_chars_accepted(self):
        self.assertEqual(self._s().validate_name("AB"), "AB")

    def test_one_char_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("A")

    def test_empty_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("")

    def test_none_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name(None)


class CategoryValidateDescriptionTests(SimpleTestCase):
    def _s(self):
        return CategorySerializer()

    def test_empty_returns_empty(self):
        self.assertEqual(self._s().validate_description(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(self._s().validate_description(None), "")

    def test_text_stripped(self):
        self.assertEqual(self._s().validate_description("  desc  "), "desc")

    def test_exactly_1000_chars_accepted(self):
        text = "a" * 1000
        self.assertEqual(len(self._s().validate_description(text)), 1000)

    def test_over_1000_chars_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_description("a" * 1001)


# ══════════════════════════════════════════════════════════════════════════════
# SuperCategorySerializer.validate_name / validate_disabled_note
# ══════════════════════════════════════════════════════════════════════════════

class SuperCategoryValidateNameTests(SimpleTestCase):
    def _s(self):
        return SuperCategorySerializer()

    def test_valid_name_returned(self):
        self.assertEqual(self._s().validate_name("Starters"), "Starters")

    def test_stripped(self):
        self.assertEqual(self._s().validate_name("  Mains  "), "Mains")

    def test_two_chars_accepted(self):
        self.assertEqual(self._s().validate_name("AB"), "AB")

    def test_one_char_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("A")

    def test_empty_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("")

    def test_over_150_chars_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_name("a" * 151)

    def test_exactly_150_chars_accepted(self):
        name = "a" * 150
        self.assertEqual(len(self._s().validate_name(name)), 150)


class SuperCategoryValidateDisabledNoteTests(SimpleTestCase):
    def _s(self):
        return SuperCategorySerializer()

    def test_empty_returns_empty(self):
        self.assertEqual(self._s().validate_disabled_note(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(self._s().validate_disabled_note(None), "")

    def test_text_stripped(self):
        self.assertEqual(self._s().validate_disabled_note("  note  "), "note")

    def test_exactly_180_chars_accepted(self):
        text = "a" * 180
        self.assertEqual(len(self._s().validate_disabled_note(text)), 180)

    def test_over_180_chars_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_disabled_note("a" * 181)
