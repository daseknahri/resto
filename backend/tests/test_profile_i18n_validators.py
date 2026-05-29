"""
Unit tests for three ProfileSerializer i18n field validators in
tenancy/serializers.py that were not yet directly tested:

  - validate_address_i18n      (max_length=255)
  - validate_description_i18n  (max_length=2000)
  - validate_business_hours_i18n (max_length=1000)

Each is a thin wrapper around LocalizedProfileContentMixin._validate_i18n_map.
Tests confirm the delegation and ensure the max_length constraints are wired
correctly for each field.

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from tenancy.serializers import ProfileSerializer


def _ser(max_languages=5):
    """ProfileSerializer with an in-memory request context."""
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False),
        tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=max_languages)),
        query_params={},
        headers={},
        META={},
    )
    return ProfileSerializer(context={"request": request})


# ══════════════════════════════════════════════════════════════════════════════
# validate_address_i18n  (max_length=255)
# ══════════════════════════════════════════════════════════════════════════════

class ValidateAddressI18nTests(SimpleTestCase):

    def test_none_returns_empty_dict(self):
        self.assertEqual(_ser().validate_address_i18n(None), {})

    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(_ser().validate_address_i18n(""), {})

    def test_valid_translation_passes_through(self):
        result = _ser().validate_address_i18n({"fr": "12 Rue de la Paix, Paris"})
        self.assertEqual(result, {"fr": "12 Rue de la Paix, Paris"})

    def test_value_at_max_length_passes(self):
        result = _ser().validate_address_i18n({"fr": "a" * 255})
        self.assertEqual(result["fr"], "a" * 255)

    def test_value_exceeding_max_length_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_address_i18n({"fr": "a" * 256})
        self.assertIn("Address", str(ctx.exception))
        self.assertIn("255", str(ctx.exception))

    def test_invalid_locale_raises_with_field_label(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_address_i18n({"xx-YY-ZZ": "Some address"})
        self.assertIn("Address", str(ctx.exception))

    def test_non_dict_raises(self):
        with self.assertRaises(ValidationError):
            _ser().validate_address_i18n("not a dict")

    def test_empty_text_entry_skipped(self):
        result = _ser().validate_address_i18n({"fr": "  ", "ar": "شارع"})
        self.assertNotIn("fr", result)
        self.assertIn("ar", result)


# ══════════════════════════════════════════════════════════════════════════════
# validate_description_i18n  (max_length=2000)
# ══════════════════════════════════════════════════════════════════════════════

class ValidateDescriptionI18nTests(SimpleTestCase):

    def test_none_returns_empty_dict(self):
        self.assertEqual(_ser().validate_description_i18n(None), {})

    def test_valid_translation_passes_through(self):
        result = _ser().validate_description_i18n({"en": "A fine dining experience."})
        self.assertEqual(result, {"en": "A fine dining experience."})

    def test_value_at_max_length_passes(self):
        result = _ser().validate_description_i18n({"en": "x" * 2000})
        self.assertEqual(len(result["en"]), 2000)

    def test_value_exceeding_max_length_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_description_i18n({"en": "x" * 2001})
        self.assertIn("Description", str(ctx.exception))
        self.assertIn("2000", str(ctx.exception))

    def test_invalid_locale_raises_with_field_label(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_description_i18n({"notlocale": "text"})
        self.assertIn("Description", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════════════════
# validate_business_hours_i18n  (max_length=1000)
# ══════════════════════════════════════════════════════════════════════════════

class ValidateBusinessHoursI18nTests(SimpleTestCase):

    def test_none_returns_empty_dict(self):
        self.assertEqual(_ser().validate_business_hours_i18n(None), {})

    def test_valid_translation_passes_through(self):
        result = _ser().validate_business_hours_i18n({"fr": "Lun–Sam 09h–22h"})
        self.assertEqual(result, {"fr": "Lun–Sam 09h–22h"})

    def test_value_at_max_length_passes(self):
        result = _ser().validate_business_hours_i18n({"fr": "y" * 1000})
        self.assertEqual(len(result["fr"]), 1000)

    def test_value_exceeding_max_length_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_business_hours_i18n({"fr": "y" * 1001})
        self.assertIn("Business hours", str(ctx.exception))
        self.assertIn("1000", str(ctx.exception))

    def test_invalid_locale_raises_with_field_label(self):
        with self.assertRaises(ValidationError) as ctx:
            _ser().validate_business_hours_i18n({"zzzz": "All day"})
        self.assertIn("Business hours", str(ctx.exception))
