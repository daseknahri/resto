"""
Unit tests for the three validator methods in sales/serializers.py:

  AdminPlanFeatureFlagItemSerializer
    - validate_key   — normalises, rejects empty/unknown keys
    - validate_config — None-safe; accepts dict/list; rejects scalars

  AdminPlanFeatureFlagUpdateSerializer
    - validate_feature_flags — deduplicates by key; rejects empty result

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sales.serializers import (
    AdminPlanFeatureFlagItemSerializer,
    AdminPlanFeatureFlagUpdateSerializer,
)

# A real key guaranteed to be in the catalog
_VALID_KEY = "customer_reservations"
# Catalog keys (from tenancy/tiering.py PLAN_FEATURE_FLAG_CATALOG)
_ALL_CATALOG_KEYS = [
    "customer_reservations",
    "owner_reservation_inbox",
    "owner_table_management",
    "in_app_order_management",
    "checkout_payments",
    "multi_language_content",
    "advanced_analytics",
]


# ══════════════════════════════════════════════════════════════════════════════
# AdminPlanFeatureFlagItemSerializer — validate_key
# ══════════════════════════════════════════════════════════════════════════════

class ValidateKeyTests(SimpleTestCase):
    """validate_key: normalises, rejects empty or unknown keys."""

    def _s(self):
        return AdminPlanFeatureFlagItemSerializer()

    # ── empty / blank ─────────────────────────────────────────────────────────
    def test_empty_string_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_key("")
        self.assertIn("required", str(cm.exception).lower())

    def test_whitespace_only_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_key("   ")
        self.assertIn("required", str(cm.exception).lower())

    def test_none_raises_required(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_key(None)
        self.assertIn("required", str(cm.exception).lower())

    # ── unknown key ───────────────────────────────────────────────────────────
    def test_unknown_key_raises_unknown(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_key("totally_nonexistent_flag")
        self.assertIn("unknown", str(cm.exception).lower())

    def test_partially_matching_key_raises_unknown(self):
        """'customer' (prefix of a valid key) is not itself valid."""
        with self.assertRaises(ValidationError):
            self._s().validate_key("customer")

    # ── valid keys ────────────────────────────────────────────────────────────
    def test_valid_key_returned_as_is(self):
        result = self._s().validate_key(_VALID_KEY)
        self.assertEqual(result, _VALID_KEY)

    def test_all_catalog_keys_accepted(self):
        s = self._s()
        for key in _ALL_CATALOG_KEYS:
            result = s.validate_key(key)
            self.assertEqual(result, key)

    # ── normalisation ─────────────────────────────────────────────────────────
    def test_uppercase_key_normalised_and_accepted(self):
        result = self._s().validate_key("CUSTOMER_RESERVATIONS")
        self.assertEqual(result, "customer_reservations")

    def test_mixed_case_key_normalised(self):
        result = self._s().validate_key("Customer_Reservations")
        self.assertEqual(result, "customer_reservations")

    def test_leading_trailing_whitespace_stripped(self):
        result = self._s().validate_key("  customer_reservations  ")
        self.assertEqual(result, "customer_reservations")

    def test_normalised_key_returned_not_original(self):
        """Return value is the normalised form, not the raw input."""
        raw = "  CHECKOUT_PAYMENTS  "
        result = self._s().validate_key(raw)
        self.assertEqual(result, "checkout_payments")
        self.assertNotEqual(result, raw)


# ══════════════════════════════════════════════════════════════════════════════
# AdminPlanFeatureFlagItemSerializer — validate_config
# ══════════════════════════════════════════════════════════════════════════════

class ValidateConfigTests(SimpleTestCase):
    """validate_config: None passes; dict/list passes; scalars raise."""

    def _s(self):
        return AdminPlanFeatureFlagItemSerializer()

    # ── pass-through values ───────────────────────────────────────────────────
    def test_none_returns_none(self):
        self.assertIsNone(self._s().validate_config(None))

    def test_dict_returned_unchanged(self):
        cfg = {"limit": 100, "active": True}
        result = self._s().validate_config(cfg)
        self.assertEqual(result, cfg)

    def test_empty_dict_accepted(self):
        result = self._s().validate_config({})
        self.assertEqual(result, {})

    def test_list_returned_unchanged(self):
        cfg = [1, 2, 3]
        result = self._s().validate_config(cfg)
        self.assertEqual(result, cfg)

    def test_empty_list_accepted(self):
        result = self._s().validate_config([])
        self.assertEqual(result, [])

    def test_nested_dict_accepted(self):
        cfg = {"key": {"nested": True}}
        result = self._s().validate_config(cfg)
        self.assertEqual(result, cfg)

    # ── invalid scalars ───────────────────────────────────────────────────────
    def test_string_raises(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate_config("some-string")
        self.assertIn("object or array", str(cm.exception).lower())

    def test_integer_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_config(42)

    def test_boolean_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_config(True)

    def test_float_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_config(3.14)


# ══════════════════════════════════════════════════════════════════════════════
# AdminPlanFeatureFlagUpdateSerializer — validate_feature_flags
# ══════════════════════════════════════════════════════════════════════════════

class ValidateFeatureFlagsTests(SimpleTestCase):
    """validate_feature_flags: deduplicates; raises if result is empty."""

    def _s(self):
        return AdminPlanFeatureFlagUpdateSerializer()

    def _row(self, key, enabled=True, config=None):
        return {"key": key, "enabled": enabled, "config": config}

    # ── no duplicates ─────────────────────────────────────────────────────────
    def test_unique_list_returned_unchanged(self):
        rows = [
            self._row("customer_reservations"),
            self._row("checkout_payments"),
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual(len(result), 2)

    def test_single_item_passes(self):
        rows = [self._row("customer_reservations")]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "customer_reservations")

    # ── deduplication ─────────────────────────────────────────────────────────
    def test_duplicate_key_second_occurrence_removed(self):
        rows = [
            self._row("customer_reservations", enabled=True),
            self._row("customer_reservations", enabled=False),   # duplicate
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual(len(result), 1)

    def test_first_occurrence_kept_on_dedup(self):
        rows = [
            self._row("customer_reservations", enabled=True),
            self._row("customer_reservations", enabled=False),
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertTrue(result[0]["enabled"])  # first (True) kept

    def test_multiple_duplicates_all_collapsed(self):
        rows = [
            self._row("customer_reservations"),
            self._row("customer_reservations"),
            self._row("customer_reservations"),
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual(len(result), 1)

    def test_mixed_unique_and_duplicate_deduped_correctly(self):
        rows = [
            self._row("customer_reservations"),
            self._row("checkout_payments"),
            self._row("customer_reservations"),  # dup
            self._row("multi_language_content"),
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual(len(result), 3)
        keys = [r["key"] for r in result]
        self.assertEqual(keys, ["customer_reservations", "checkout_payments", "multi_language_content"])

    # ── order preserved ───────────────────────────────────────────────────────
    def test_order_of_unique_items_preserved(self):
        rows = [
            self._row("checkout_payments"),
            self._row("customer_reservations"),
            self._row("multi_language_content"),
        ]
        result = self._s().validate_feature_flags(rows)
        self.assertEqual([r["key"] for r in result],
                         ["checkout_payments", "customer_reservations", "multi_language_content"])
