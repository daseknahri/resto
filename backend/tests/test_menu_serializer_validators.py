"""
Unit tests for inline serializer validators in menu/views.py:

  TableBulkGenerateInputSerializer
    - validate_prefix

  AnalyticsEventInputSerializer
    - validate_metadata
    - validate (cross-field: category_view/dish_view slug requirements)

  OrderHandoffSerializer
    - validate_table_label
    - validate_customer_name
    - validate_customer_phone
    - validate_delivery_address
    - validate_delivery_lat
    - validate_delivery_lng

All tests are unit-level (SimpleTestCase — no real DB).
"""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from menu.views import (
    AnalyticsEventInputSerializer,
    OrderHandoffSerializer,
    TableBulkGenerateInputSerializer,
)


# ══════════════════════════════════════════════════════════════════════════════
# TableBulkGenerateInputSerializer — validate_prefix
# ══════════════════════════════════════════════════════════════════════════════

class ValidatePrefixTests(SimpleTestCase):
    """validate_prefix: strips, rejects empty, validates char set."""

    def _s(self):
        return TableBulkGenerateInputSerializer()

    # ── valid prefixes ────────────────────────────────────────────────────────
    def test_simple_word_accepted(self):
        self.assertEqual(self._s().validate_prefix("Table"), "Table")

    def test_alphanumeric_accepted(self):
        self.assertEqual(self._s().validate_prefix("Table1"), "Table1")

    def test_with_hash_accepted(self):
        self.assertEqual(self._s().validate_prefix("Table #"), "Table #")

    def test_with_hyphen_accepted(self):
        self.assertEqual(self._s().validate_prefix("Table-A"), "Table-A")

    def test_with_underscore_accepted(self):
        self.assertEqual(self._s().validate_prefix("My_Table"), "My_Table")

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(self._s().validate_prefix("  Table  "), "Table")

    # ── empty / blank ─────────────────────────────────────────────────────────
    def test_empty_string_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_prefix("")
        self.assertIn("required", str(cm.exception).lower())

    def test_whitespace_only_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_prefix("   ")
        self.assertIn("required", str(cm.exception).lower())

    def test_none_raises_required(self):
        with self.assertRaises(ValidationError):
            self._s().validate_prefix(None)

    # ── invalid characters ────────────────────────────────────────────────────
    def test_at_sign_raises_invalid_chars(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_prefix("Table@")
        self.assertIn("only", str(cm.exception).lower())

    def test_dot_raises_invalid_chars(self):
        with self.assertRaises(ValidationError):
            self._s().validate_prefix("Table.1")

    def test_slash_raises_invalid_chars(self):
        with self.assertRaises(ValidationError):
            self._s().validate_prefix("Table/A")


# ══════════════════════════════════════════════════════════════════════════════
# AnalyticsEventInputSerializer — validate_metadata
# ══════════════════════════════════════════════════════════════════════════════

class ValidateMetadataTests(SimpleTestCase):
    """validate_metadata: sanitises nested values; non-dict → {}."""

    def _s(self):
        return AnalyticsEventInputSerializer()

    # ── non-dict ──────────────────────────────────────────────────────────────
    def test_non_dict_returns_empty_dict(self):
        self.assertEqual(self._s().validate_metadata("string"), {})
        self.assertEqual(self._s().validate_metadata(42), {})
        self.assertEqual(self._s().validate_metadata(None), {})
        self.assertEqual(self._s().validate_metadata([1, 2]), {})

    # ── scalar values ─────────────────────────────────────────────────────────
    def test_string_value_preserved(self):
        result = self._s().validate_metadata({"key": "value"})
        self.assertEqual(result["key"], "value")

    def test_int_value_preserved(self):
        result = self._s().validate_metadata({"count": 5})
        self.assertEqual(result["count"], 5)

    def test_float_value_preserved(self):
        result = self._s().validate_metadata({"ratio": 3.14})
        self.assertEqual(result["ratio"], 3.14)

    def test_bool_value_preserved(self):
        result = self._s().validate_metadata({"active": True})
        self.assertEqual(result["active"], True)

    def test_none_value_preserved(self):
        result = self._s().validate_metadata({"empty": None})
        self.assertIsNone(result["empty"])

    # ── key truncation ────────────────────────────────────────────────────────
    def test_long_key_truncated_to_48_chars(self):
        long_key = "k" * 100
        result = self._s().validate_metadata({long_key: "v"})
        keys = list(result.keys())
        self.assertEqual(len(keys), 1)
        self.assertEqual(len(keys[0]), 48)

    # ── list values ───────────────────────────────────────────────────────────
    def test_list_value_stringified(self):
        result = self._s().validate_metadata({"items": [1, 2, 3]})
        self.assertIsInstance(result["items"], list)
        self.assertEqual(result["items"], ["1", "2", "3"])

    def test_list_value_capped_at_10_items(self):
        result = self._s().validate_metadata({"items": list(range(20))})
        self.assertEqual(len(result["items"]), 10)

    def test_tuple_treated_like_list(self):
        result = self._s().validate_metadata({"items": (1, 2)})
        self.assertIsInstance(result["items"], list)

    # ── nested dict values ────────────────────────────────────────────────────
    def test_nested_dict_stringified(self):
        result = self._s().validate_metadata({"nested": {"a": 1}})
        self.assertIsInstance(result["nested"], dict)
        self.assertEqual(result["nested"]["a"], "1")

    # ── unknown type ──────────────────────────────────────────────────────────
    def test_object_value_converted_to_str(self):
        class Obj:
            def __str__(self):
                return "obj-value"
        result = self._s().validate_metadata({"obj": Obj()})
        self.assertEqual(result["obj"], "obj-value")


# ══════════════════════════════════════════════════════════════════════════════
# AnalyticsEventInputSerializer — validate (cross-field)
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsEventValidateTests(SimpleTestCase):
    """validate: category_view/dish_view require their respective slug."""

    def _s(self):
        return AnalyticsEventInputSerializer()

    def test_category_view_without_slug_raises(self):
        attrs = {"event_type": "category_view"}
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        self.assertIn("category_slug", str(cm.exception))

    def test_category_view_with_slug_passes(self):
        attrs = {"event_type": "category_view", "category_slug": "starters"}
        result = self._s().validate(attrs)
        self.assertEqual(result["event_type"], "category_view")

    def test_dish_view_without_slug_raises(self):
        attrs = {"event_type": "dish_view"}
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        self.assertIn("dish_slug", str(cm.exception))

    def test_dish_view_with_slug_passes(self):
        attrs = {"event_type": "dish_view", "dish_slug": "pasta"}
        result = self._s().validate(attrs)
        self.assertEqual(result["event_type"], "dish_view")

    def test_other_event_type_passes_without_slug(self):
        attrs = {"event_type": "menu_view"}
        result = self._s().validate(attrs)
        self.assertEqual(result["event_type"], "menu_view")

    def test_cart_view_passes_without_slug(self):
        attrs = {"event_type": "cart_view"}
        result = self._s().validate(attrs)
        self.assertIn("event_type", result)


# ══════════════════════════════════════════════════════════════════════════════
# OrderHandoffSerializer — field validators
# ══════════════════════════════════════════════════════════════════════════════

class ValidateTableLabelTests(SimpleTestCase):
    """validate_table_label: empty allowed; valid chars; strips."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_empty_string(self):
        self.assertEqual(self._s().validate_table_label(None), "")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(self._s().validate_table_label(""), "")

    def test_whitespace_only_returns_empty_string(self):
        self.assertEqual(self._s().validate_table_label("   "), "")

    def test_valid_label_returned_stripped(self):
        self.assertEqual(self._s().validate_table_label("  Table 1  "), "Table 1")

    def test_alphanumeric_accepted(self):
        self.assertEqual(self._s().validate_table_label("VIP1"), "VIP1")

    def test_hash_accepted(self):
        self.assertEqual(self._s().validate_table_label("Table #5"), "Table #5")

    def test_hyphen_accepted(self):
        self.assertEqual(self._s().validate_table_label("Table-A"), "Table-A")

    def test_underscore_accepted(self):
        self.assertEqual(self._s().validate_table_label("Table_B"), "Table_B")

    def test_invalid_special_chars_raise(self):
        with self.assertRaises(ValidationError):
            self._s().validate_table_label("Table@!")

    def test_angle_bracket_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_table_label("Table<1>")


class ValidateCustomerNameTests(SimpleTestCase):
    """validate_customer_name: empty allowed; length 2-80; no control chars."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_empty_string(self):
        self.assertEqual(self._s().validate_customer_name(None), "")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(self._s().validate_customer_name(""), "")

    def test_valid_name_returned_stripped(self):
        self.assertEqual(self._s().validate_customer_name("  Ali  "), "Ali")

    def test_minimum_length_2_accepted(self):
        self.assertEqual(self._s().validate_customer_name("Jo"), "Jo")

    def test_length_1_raises_too_short(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_customer_name("J")
        self.assertIn("short", str(cm.exception).lower())

    def test_length_80_accepted(self):
        name = "A" * 80
        self.assertEqual(self._s().validate_customer_name(name), name)

    def test_length_81_raises_too_long(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_customer_name("A" * 81)
        self.assertIn("80", str(cm.exception))

    def test_less_than_sign_raises_invalid_chars(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_customer_name("Name<tag>")
        self.assertIn("unsupported", str(cm.exception).lower())

    def test_double_quote_raises_invalid_chars(self):
        with self.assertRaises(ValidationError):
            self._s().validate_customer_name('Name"')

    def test_null_byte_raises_invalid_chars(self):
        with self.assertRaises(ValidationError):
            self._s().validate_customer_name("Na\x00me")

    def test_regular_unicode_name_accepted(self):
        # Normal name with spaces and accented chars (no control chars)
        result = self._s().validate_customer_name("José María")
        self.assertEqual(result, "José María")


class ValidateCustomerPhoneTests(SimpleTestCase):
    """validate_customer_phone: empty allowed; digits/+/-/()/spaces; 6-30 chars."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_empty_string(self):
        self.assertEqual(self._s().validate_customer_phone(None), "")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(self._s().validate_customer_phone(""), "")

    def test_valid_phone_digits_only(self):
        self.assertEqual(self._s().validate_customer_phone("0661234567"), "0661234567")

    def test_valid_phone_with_plus(self):
        self.assertEqual(self._s().validate_customer_phone("+212661234567"), "+212661234567")

    def test_valid_phone_with_dashes(self):
        result = self._s().validate_customer_phone("06-61-23-45-67")
        self.assertEqual(result, "06-61-23-45-67")

    def test_valid_phone_with_parens(self):
        result = self._s().validate_customer_phone("(0212) 345678")
        self.assertEqual(result, "(0212) 345678")

    def test_too_short_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_customer_phone("12345")  # 5 chars < 6

    def test_too_long_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_customer_phone("1" * 31)

    def test_letters_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_customer_phone("06abc123")

    def test_leading_trailing_whitespace_stripped_before_validation(self):
        result = self._s().validate_customer_phone("  0661234567  ")
        self.assertEqual(result, "0661234567")


class ValidateDeliveryAddressTests(SimpleTestCase):
    """validate_delivery_address: strips whitespace, allows any content."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_empty_string(self):
        self.assertEqual(self._s().validate_delivery_address(None), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(self._s().validate_delivery_address(""), "")

    def test_value_returned_stripped(self):
        self.assertEqual(
            self._s().validate_delivery_address("  123 Main St  "),
            "123 Main St",
        )

    def test_plain_address_returned(self):
        self.assertEqual(
            self._s().validate_delivery_address("Rue Hassan II, Casablanca"),
            "Rue Hassan II, Casablanca",
        )


class ValidateDeliveryLatTests(SimpleTestCase):
    """validate_delivery_lat: None → None; -90 to 90 accepted; out of range raises."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_none(self):
        self.assertIsNone(self._s().validate_delivery_lat(None))

    def test_valid_positive_lat(self):
        self.assertEqual(self._s().validate_delivery_lat(33.5), 33.5)

    def test_valid_negative_lat(self):
        self.assertEqual(self._s().validate_delivery_lat(-33.5), -33.5)

    def test_lat_90_accepted(self):
        self.assertEqual(self._s().validate_delivery_lat(90), 90.0)

    def test_lat_minus_90_accepted(self):
        self.assertEqual(self._s().validate_delivery_lat(-90), -90.0)

    def test_lat_above_90_raises(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_delivery_lat(90.1)
        self.assertIn("90", str(cm.exception))

    def test_lat_below_minus_90_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_delivery_lat(-90.1)

    def test_returns_float(self):
        result = self._s().validate_delivery_lat(33)
        self.assertIsInstance(result, float)


class ValidateDeliveryLngTests(SimpleTestCase):
    """validate_delivery_lng: None → None; -180 to 180 accepted; out of range raises."""

    def _s(self):
        return OrderHandoffSerializer()

    def test_none_returns_none(self):
        self.assertIsNone(self._s().validate_delivery_lng(None))

    def test_valid_positive_lng(self):
        self.assertEqual(self._s().validate_delivery_lng(5.0), 5.0)

    def test_valid_negative_lng(self):
        self.assertEqual(self._s().validate_delivery_lng(-5.0), -5.0)

    def test_lng_180_accepted(self):
        self.assertEqual(self._s().validate_delivery_lng(180), 180.0)

    def test_lng_minus_180_accepted(self):
        self.assertEqual(self._s().validate_delivery_lng(-180), -180.0)

    def test_lng_above_180_raises(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_delivery_lng(180.1)
        self.assertIn("180", str(cm.exception))

    def test_lng_below_minus_180_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_delivery_lng(-180.1)

    def test_returns_float(self):
        result = self._s().validate_delivery_lng(10)
        self.assertIsInstance(result, float)
