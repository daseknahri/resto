"""Tests for DishSerializer.validate_attributes — Kepoli Phase 1 retail attributes seam.

Validates the spec:
  - Allowed keys: sku (max 64), barcode (max 64), brand (max 80), unit (max 40)
  - Unknown keys are silently dropped
  - Empty / whitespace values are dropped
  - Non-dict input raises ValidationError
  - Over-length values raise ValidationError (no silent truncation)
  - Non-string scalars: numbers coerced via str(); lists/dicts rejected

Run with: DJANGO_DEBUG=True python -m pytest tests/test_dish_attributes.py -q --tb=short
"""

from django.test import SimpleTestCase
from rest_framework import serializers as drf_serializers

from menu.serializers import DishSerializer


def _validate(value):
    """Invoke validate_attributes directly, no DB needed."""
    return DishSerializer().validate_attributes(value)


class ValidAttributesTests(SimpleTestCase):
    """Happy-path: valid inputs return the cleaned dict."""

    def test_full_valid_dict_passes(self):
        result = _validate({"sku": "ABC-123", "barcode": "5901234123457", "brand": "Acme", "unit": "500 g"})
        self.assertEqual(result, {"sku": "ABC-123", "barcode": "5901234123457", "brand": "Acme", "unit": "500 g"})

    def test_empty_dict_returns_empty(self):
        self.assertEqual(_validate({}), {})

    def test_none_returns_empty(self):
        self.assertEqual(_validate(None), {})

    def test_partial_dict_only_present_keys_returned(self):
        result = _validate({"sku": "SKU1"})
        self.assertEqual(result, {"sku": "SKU1"})

    def test_values_are_trimmed(self):
        result = _validate({"sku": "  SKU-1  ", "brand": "  Acme  "})
        self.assertEqual(result["sku"], "SKU-1")
        self.assertEqual(result["brand"], "Acme")

    def test_max_length_sku_exactly_64_passes(self):
        val = "x" * 64
        result = _validate({"sku": val})
        self.assertEqual(result["sku"], val)

    def test_max_length_barcode_exactly_64_passes(self):
        val = "1" * 64
        result = _validate({"barcode": val})
        self.assertEqual(result["barcode"], val)

    def test_max_length_brand_exactly_80_passes(self):
        val = "B" * 80
        result = _validate({"brand": val})
        self.assertEqual(result["brand"], val)

    def test_max_length_unit_exactly_40_passes(self):
        val = "u" * 40
        result = _validate({"unit": val})
        self.assertEqual(result["unit"], val)


class UnknownKeysDroppedTests(SimpleTestCase):
    """Unknown keys are silently dropped."""

    def test_unknown_key_dropped(self):
        result = _validate({"sku": "SKU1", "color": "red", "weight": "100g"})
        self.assertNotIn("color", result)
        self.assertNotIn("weight", result)
        self.assertIn("sku", result)

    def test_only_unknown_keys_returns_empty(self):
        result = _validate({"foo": "bar", "baz": "qux"})
        self.assertEqual(result, {})


class EmptyValueDroppedTests(SimpleTestCase):
    """Empty or whitespace-only values are dropped."""

    def test_empty_string_dropped(self):
        result = _validate({"sku": "", "brand": "Acme"})
        self.assertNotIn("sku", result)
        self.assertIn("brand", result)

    def test_whitespace_only_dropped(self):
        result = _validate({"sku": "   ", "unit": "500 g"})
        self.assertNotIn("sku", result)
        self.assertIn("unit", result)

    def test_none_value_dropped(self):
        result = _validate({"sku": None, "barcode": "123"})
        self.assertNotIn("sku", result)
        self.assertIn("barcode", result)


class NonDictInputTests(SimpleTestCase):
    """Non-dict input raises ValidationError."""

    def test_list_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate(["sku", "ABC"])
        self.assertIn("object", str(cm.exception.detail))

    def test_string_raises(self):
        with self.assertRaises(drf_serializers.ValidationError):
            _validate("sku=ABC")

    def test_integer_raises(self):
        with self.assertRaises(drf_serializers.ValidationError):
            _validate(42)

    def test_boolean_raises(self):
        with self.assertRaises(drf_serializers.ValidationError):
            _validate(True)


class OverLengthTests(SimpleTestCase):
    """Over-length values raise ValidationError — no silent truncation."""

    def test_sku_65_chars_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"sku": "x" * 65})
        self.assertIn("sku", str(cm.exception.detail))

    def test_barcode_65_chars_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"barcode": "1" * 65})
        self.assertIn("barcode", str(cm.exception.detail))

    def test_brand_81_chars_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"brand": "B" * 81})
        self.assertIn("brand", str(cm.exception.detail))

    def test_unit_41_chars_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"unit": "u" * 41})
        self.assertIn("unit", str(cm.exception.detail))


class NonStringValueCoercionTests(SimpleTestCase):
    """Numbers are coerced to str; lists/dicts are rejected."""

    def test_integer_value_coerced_to_str(self):
        result = _validate({"sku": 12345})
        self.assertEqual(result["sku"], "12345")

    def test_float_value_coerced_to_str(self):
        result = _validate({"unit": 1.5})
        self.assertIn("unit", result)
        self.assertIsInstance(result["unit"], str)

    def test_list_value_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"sku": ["a", "b"]})
        self.assertIn("sku", str(cm.exception.detail))

    def test_dict_value_raises(self):
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            _validate({"brand": {"name": "Acme"}})
        self.assertIn("brand", str(cm.exception.detail))
