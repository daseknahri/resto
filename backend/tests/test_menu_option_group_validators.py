"""
Unit tests for validate_name on menu/serializers.py classes that are not
yet directly covered:

  DishOptionSerializer.validate_name
    (option name: min 1 char, max 150 chars)

  OptionGroupSerializer.validate_name
    (group name: min 1 char, max 150 chars)

All tests are unit-level (SimpleTestCase — no real DB).
"""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from menu.serializers import DishOptionSerializer, OptionGroupSerializer


# ══════════════════════════════════════════════════════════════════════════════
# DishOptionSerializer.validate_name
# ══════════════════════════════════════════════════════════════════════════════

class DishOptionValidateNameTests(SimpleTestCase):
    """validate_name: at least 1 char, max 150, strips whitespace."""

    def _s(self):
        return DishOptionSerializer()

    # ── valid ─────────────────────────────────────────────────────────────────
    def test_single_char_accepted(self):
        self.assertEqual(self._s().validate_name("A"), "A")

    def test_normal_name_returned(self):
        self.assertEqual(self._s().validate_name("Extra Cheese"), "Extra Cheese")

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(self._s().validate_name("  Sauce  "), "Sauce")

    def test_exactly_150_chars_accepted(self):
        name = "a" * 150
        self.assertEqual(self._s().validate_name(name), name)

    # ── empty / blank ─────────────────────────────────────────────────────────
    def test_empty_string_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("")
        self.assertIn("required", str(cm.exception).lower())

    def test_whitespace_only_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("   ")
        self.assertIn("required", str(cm.exception).lower())

    def test_none_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name(None)
        self.assertIn("required", str(cm.exception).lower())

    # ── too long ──────────────────────────────────────────────────────────────
    def test_151_chars_raises_too_long(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("a" * 151)
        self.assertIn("150", str(cm.exception))


# ══════════════════════════════════════════════════════════════════════════════
# OptionGroupSerializer.validate_name
# ══════════════════════════════════════════════════════════════════════════════

class OptionGroupValidateNameTests(SimpleTestCase):
    """validate_name: at least 1 char, max 150 chars, strips whitespace."""

    def _s(self):
        return OptionGroupSerializer()

    # ── valid ─────────────────────────────────────────────────────────────────
    def test_single_char_accepted(self):
        self.assertEqual(self._s().validate_name("X"), "X")

    def test_normal_name_returned(self):
        self.assertEqual(self._s().validate_name("Cooking Style"), "Cooking Style")

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(self._s().validate_name("  Size  "), "Size")

    def test_exactly_150_chars_accepted(self):
        name = "b" * 150
        self.assertEqual(self._s().validate_name(name), name)

    # ── empty / blank ─────────────────────────────────────────────────────────
    def test_empty_string_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("")
        self.assertIn("required", str(cm.exception).lower())

    def test_whitespace_only_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("   ")
        self.assertIn("required", str(cm.exception).lower())

    def test_none_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name(None)
        self.assertIn("required", str(cm.exception).lower())

    # ── too long ──────────────────────────────────────────────────────────────
    def test_151_chars_raises_too_long(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_name("c" * 151)
        self.assertIn("150", str(cm.exception))
