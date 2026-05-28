"""
Unit tests for private helper functions in sales/views.py:
  - _parse_iso_date
  - _parse_positive_int
  - _next_unique_slug
  - _coerce_payload_list
  - _coerce_i18n_dict
  - _reservation_phone_digits
  - _build_whatsapp_reservation_reminder

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from sales.views import (
    _parse_iso_date,
    _parse_positive_int,
    _next_unique_slug,
    _coerce_payload_list,
    _coerce_i18n_dict,
    _reservation_phone_digits,
    _build_whatsapp_reservation_reminder,
)


# ══════════════════════════════════════════════════════════════════════════════
# _parse_iso_date
# ══════════════════════════════════════════════════════════════════════════════

class ParseIsoDateTests(SimpleTestCase):
    def test_valid_iso_date(self):
        from datetime import date
        result = _parse_iso_date("2024-03-15")
        self.assertEqual(result, date(2024, 3, 15))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_iso_date(""))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_iso_date(None))

    def test_invalid_format_returns_none(self):
        self.assertIsNone(_parse_iso_date("15/03/2024"))

    def test_garbage_string_returns_none(self):
        self.assertIsNone(_parse_iso_date("not-a-date"))

    def test_whitespace_stripped_before_parse(self):
        from datetime import date
        result = _parse_iso_date("  2024-06-01  ")
        self.assertEqual(result, date(2024, 6, 1))


# ══════════════════════════════════════════════════════════════════════════════
# _parse_positive_int
# ══════════════════════════════════════════════════════════════════════════════

class ParsePositiveIntTests(SimpleTestCase):
    def test_valid_integer_returned(self):
        self.assertEqual(_parse_positive_int("50", default=10), 50)

    def test_empty_returns_default(self):
        self.assertEqual(_parse_positive_int("", default=25), 25)

    def test_none_returns_default(self):
        self.assertEqual(_parse_positive_int(None, default=7), 7)

    def test_non_numeric_returns_default(self):
        self.assertEqual(_parse_positive_int("abc", default=5), 5)

    def test_below_min_clamped_to_min(self):
        self.assertEqual(_parse_positive_int("0", default=10, min_value=1), 1)

    def test_above_max_clamped_to_max(self):
        self.assertEqual(_parse_positive_int("1000", default=10, max_value=500), 500)

    def test_exactly_at_max_accepted(self):
        self.assertEqual(_parse_positive_int("500", default=10, max_value=500), 500)

    def test_exactly_at_min_accepted(self):
        self.assertEqual(_parse_positive_int("1", default=10, min_value=1), 1)

    def test_whitespace_stripped(self):
        self.assertEqual(_parse_positive_int("  42  ", default=10), 42)


# ══════════════════════════════════════════════════════════════════════════════
# _next_unique_slug
# ══════════════════════════════════════════════════════════════════════════════

class NextUniqueSlugTests(SimpleTestCase):
    def test_returns_slugified_value(self):
        used: set = set()
        result = _next_unique_slug("My Bistro", fallback="item", max_length=50, used=used)
        self.assertEqual(result, "my-bistro")

    def test_returns_fallback_when_value_empty(self):
        used: set = set()
        result = _next_unique_slug("", fallback="item", max_length=50, used=used)
        self.assertEqual(result, "item")

    def test_increments_when_slug_taken(self):
        used = {"my-bistro"}
        result = _next_unique_slug("My Bistro", fallback="item", max_length=50, used=used)
        self.assertEqual(result, "my-bistro-2")

    def test_increments_again_when_both_taken(self):
        used = {"my-bistro", "my-bistro-2"}
        result = _next_unique_slug("My Bistro", fallback="item", max_length=50, used=used)
        self.assertEqual(result, "my-bistro-3")

    def test_added_to_used_set(self):
        used: set = set()
        _next_unique_slug("café", fallback="item", max_length=50, used=used)
        self.assertIn("cafe", used)

    def test_respects_max_length(self):
        used: set = set()
        long_value = "a" * 100
        result = _next_unique_slug(long_value, fallback="item", max_length=20, used=used)
        self.assertLessEqual(len(result), 20)

    def test_suffix_does_not_exceed_max_length(self):
        used = {"a" * 20}
        result = _next_unique_slug("a" * 100, fallback="item", max_length=20, used=used)
        self.assertLessEqual(len(result), 20)
        self.assertNotEqual(result, "a" * 20)


# ══════════════════════════════════════════════════════════════════════════════
# _coerce_payload_list
# ══════════════════════════════════════════════════════════════════════════════

class CoercePayloadListTests(SimpleTestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_coerce_payload_list(None, field_name="items"))

    def test_list_returned_as_is(self):
        data = [1, 2, 3]
        result = _coerce_payload_list(data, field_name="items")
        self.assertEqual(result, [1, 2, 3])

    def test_empty_list_returned(self):
        self.assertEqual(_coerce_payload_list([], field_name="items"), [])

    def test_non_list_raises_value_error(self):
        with self.assertRaises(ValueError):
            _coerce_payload_list({"key": "val"}, field_name="items")

    def test_error_message_includes_field_name(self):
        try:
            _coerce_payload_list("bad", field_name="categories")
        except ValueError as e:
            self.assertIn("categories", str(e))


# ══════════════════════════════════════════════════════════════════════════════
# _coerce_i18n_dict
# ══════════════════════════════════════════════════════════════════════════════

class CoerceI18nDictTests(SimpleTestCase):
    def test_none_returns_empty(self):
        self.assertEqual(_coerce_i18n_dict(None, field_name="name_i18n", max_length=100), {})

    def test_empty_string_returns_empty(self):
        self.assertEqual(_coerce_i18n_dict("", field_name="name_i18n", max_length=100), {})

    def test_valid_dict_returned(self):
        result = _coerce_i18n_dict({"fr": "Bonjour"}, field_name="name_i18n", max_length=100)
        self.assertEqual(result, {"fr": "Bonjour"})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            _coerce_i18n_dict("plain text", field_name="name_i18n", max_length=100)

    def test_invalid_locale_raises(self):
        with self.assertRaises(ValueError):
            _coerce_i18n_dict({"english": "Hello"}, field_name="name_i18n", max_length=100)

    def test_empty_text_skipped(self):
        result = _coerce_i18n_dict({"fr": "  "}, field_name="name_i18n", max_length=100)
        self.assertEqual(result, {})

    def test_text_truncated_to_max_length(self):
        result = _coerce_i18n_dict({"fr": "a" * 200}, field_name="name_i18n", max_length=50)
        self.assertEqual(len(result["fr"]), 50)

    def test_underscore_locale_normalised(self):
        result = _coerce_i18n_dict({"fr_FR": "Bonjour"}, field_name="name_i18n", max_length=100)
        self.assertIn("fr-fr", result)

    def test_two_two_hyphen_locale_accepted(self):
        result = _coerce_i18n_dict({"ar-MA": "مرحبا"}, field_name="name_i18n", max_length=100)
        self.assertIn("ar-ma", result)


# ══════════════════════════════════════════════════════════════════════════════
# _reservation_phone_digits
# ══════════════════════════════════════════════════════════════════════════════

class ReservationPhoneDigitsTests(SimpleTestCase):
    def test_extracts_digits_only(self):
        self.assertEqual(_reservation_phone_digits("+33 6-00 00 00 01"), "33600000001")

    def test_empty_returns_empty(self):
        self.assertEqual(_reservation_phone_digits(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_reservation_phone_digits(None), "")

    def test_already_digits_unchanged(self):
        self.assertEqual(_reservation_phone_digits("0600000001"), "0600000001")

    def test_letters_stripped(self):
        self.assertEqual(_reservation_phone_digits("Phone: 0600"), "0600")


# ══════════════════════════════════════════════════════════════════════════════
# _build_whatsapp_reservation_reminder
# ══════════════════════════════════════════════════════════════════════════════

class BuildWhatsappReservationReminderTests(SimpleTestCase):
    def _lead(self, name="Alice", phone="+33600000001"):
        return SimpleNamespace(name=name, phone=phone)

    def _tenant(self, name="Le Bistro"):
        return SimpleNamespace(name=name)

    def test_returns_none_when_no_phone(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(phone=""),
            tenant=self._tenant(),
        )
        self.assertIsNone(result)

    def test_returns_none_when_phone_has_no_digits(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(phone="N/A"),
            tenant=self._tenant(),
        )
        self.assertIsNone(result)

    def test_result_has_required_keys(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(),
            tenant=self._tenant(),
        )
        self.assertIn("phone", result)
        self.assertIn("message", result)
        self.assertIn("whatsapp_link", result)

    def test_phone_is_digits_only(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(phone="+33 6-00-00-00-01"),
            tenant=self._tenant(),
        )
        self.assertTrue(result["phone"].isdigit())

    def test_message_contains_guest_name(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(name="Bob"),
            tenant=self._tenant(),
        )
        self.assertIn("Bob", result["message"])

    def test_message_contains_restaurant_name(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(),
            tenant=self._tenant(name="La Maison"),
        )
        self.assertIn("La Maison", result["message"])

    def test_whatsapp_link_starts_with_wa_me(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(),
            tenant=self._tenant(),
        )
        self.assertTrue(result["whatsapp_link"].startswith("https://wa.me/"))

    def test_empty_name_falls_back_to_there(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(name=""),
            tenant=self._tenant(),
        )
        self.assertIn("there", result["message"])

    def test_empty_restaurant_name_falls_back(self):
        result = _build_whatsapp_reservation_reminder(
            lead=self._lead(),
            tenant=self._tenant(name=""),
        )
        self.assertIn("our restaurant", result["message"])
