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
datetime.datetime is patched for schedule-availability tests.
"""
import datetime as dt_module
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

# 2024-06-03 is a Monday (weekday 0) — verified: Jan 1 2024 is Monday.
_MONDAY_14H = dt_module.datetime(2024, 6, 3, 14, 30, 0)   # Mon 14:30 UTC
_MONDAY_8H  = dt_module.datetime(2024, 6, 3,  8,  0, 0)   # Mon 08:00 UTC
_MONDAY_22H = dt_module.datetime(2024, 6, 3, 22, 30, 0)   # Mon 22:30 UTC
_MONDAY_23H = dt_module.datetime(2024, 6, 3, 23,  0, 0)   # Mon 23:00 UTC
_MONDAY_10H = dt_module.datetime(2024, 6, 3, 10,  0, 0)   # Mon 10:00 UTC
_TUESDAY_14H = dt_module.datetime(2024, 6, 4, 14, 30, 0)  # Tue 14:30 UTC


def _mock_dt(fixed_now: dt_module.datetime):
    """Return a datetime subclass whose utcnow() returns fixed_now."""
    class _M(dt_module.datetime):
        @classmethod
        def utcnow(cls):
            return fixed_now
    return _M


class DishGetIsScheduleAvailableTests(SimpleTestCase):
    def _s(self):
        return DishSerializer()

    def _obj(self, schedule):
        return SimpleNamespace(availability_schedule=schedule)

    # ── schedule absent / invalid ──────────────────────────────────────────
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
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"days": ["mon"]})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    def test_non_matching_day_returns_false(self):
        """Monday but schedule only allows tue/wed."""
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"days": ["tue", "wed"]})
            self.assertFalse(self._s().get_is_schedule_available(obj))

    def test_all_days_always_passes_day_check(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            obj = self._obj({"days": all_days})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    def test_empty_days_list_no_day_restriction(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"days": []})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    # ── time restriction ──────────────────────────────────────────────────
    def test_within_time_window_is_true(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):  # 14:30
            obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    def test_before_time_window_is_false(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_8H)):   # 08:00
            obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
            self.assertFalse(self._s().get_is_schedule_available(obj))

    def test_after_time_window_is_false(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_22H)):  # 22:30
            obj = self._obj({"time_start": "09:00", "time_end": "22:00"})
            self.assertFalse(self._s().get_is_schedule_available(obj))

    # ── overnight window (end_m < start_m) ───────────────────────────────
    def test_overnight_window_inside_is_true(self):
        """22:00–02:00, now 23:00 → inside (>= start)."""
        with patch("datetime.datetime", _mock_dt(_MONDAY_23H)):
            obj = self._obj({"time_start": "22:00", "time_end": "02:00"})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    def test_overnight_window_outside_is_false(self):
        """22:00–02:00, now 10:00 → outside."""
        with patch("datetime.datetime", _mock_dt(_MONDAY_10H)):
            obj = self._obj({"time_start": "22:00", "time_end": "02:00"})
            self.assertFalse(self._s().get_is_schedule_available(obj))

    # ── invalid time format ────────────────────────────────────────────────
    def test_invalid_time_format_does_not_raise_returns_true(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"time_start": "bad", "time_end": "also_bad"})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    # ── combined day + time restriction ───────────────────────────────────
    def test_correct_day_and_within_time_is_true(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"days": ["mon"], "time_start": "09:00", "time_end": "22:00"})
            self.assertTrue(self._s().get_is_schedule_available(obj))

    def test_wrong_day_even_with_valid_time_is_false(self):
        with patch("datetime.datetime", _mock_dt(_MONDAY_14H)):
            obj = self._obj({"days": ["tue"], "time_start": "09:00", "time_end": "22:00"})
            self.assertFalse(self._s().get_is_schedule_available(obj))


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
