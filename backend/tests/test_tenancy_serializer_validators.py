"""
Direct unit tests for ProfileSerializer field validators in tenancy/serializers.py:
  - validate_phone / validate_whatsapp
  - validate_primary_color / validate_secondary_color
  - validate_language
  - validate_receipt_message
  - validate_business_hours_schedule

All tests are unit-level (SimpleTestCase — no real DB).  We call each
validator directly on a ProfileSerializer instance; no full serializer
round-trip is required so no DB is needed.
"""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from tenancy.serializers import ProfileSerializer


def _s():
    """Return a bare ProfileSerializer instance (no data, no instance)."""
    return ProfileSerializer()


# ══════════════════════════════════════════════════════════════════════════════
# validate_phone / validate_whatsapp
# ══════════════════════════════════════════════════════════════════════════════

class ValidatePhoneTests(SimpleTestCase):
    def test_valid_international_number(self):
        result = _s().validate_phone("+33 6 00 00 00 01")
        self.assertEqual(result, "+33 6 00 00 00 01")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_s().validate_phone(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_s().validate_phone(None), "")

    def test_too_short_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_phone("123")

    def test_invalid_characters_raise(self):
        with self.assertRaises(ValidationError):
            _s().validate_phone("+33 abc xyz")

    def test_parentheses_and_dashes_allowed(self):
        result = _s().validate_phone("+1 (800) 555-1234")
        self.assertEqual(result, "+1 (800) 555-1234")


class ValidateWhatsappTests(SimpleTestCase):
    def test_valid_whatsapp_number(self):
        result = _s().validate_whatsapp("+212 600 000 001")
        self.assertEqual(result, "+212 600 000 001")

    def test_empty_returns_empty(self):
        self.assertEqual(_s().validate_whatsapp(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_s().validate_whatsapp(None), "")

    def test_too_short_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_whatsapp("12")

    def test_invalid_characters_raise(self):
        with self.assertRaises(ValidationError):
            _s().validate_whatsapp("+212abc")


# ══════════════════════════════════════════════════════════════════════════════
# validate_primary_color / validate_secondary_color
# ══════════════════════════════════════════════════════════════════════════════

class ValidatePrimaryColorTests(SimpleTestCase):
    def test_valid_hex_color(self):
        result = _s().validate_primary_color("#0F766E")
        self.assertEqual(result, "#0F766E")

    def test_lowercased_input_uppercased(self):
        result = _s().validate_primary_color("#0f766e")
        self.assertEqual(result, "#0F766E")

    def test_missing_hash_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_primary_color("0F766E")

    def test_too_short_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_primary_color("#ABC")

    def test_invalid_hex_chars_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_primary_color("#ZZZZZZ")

    def test_whitespace_stripped_before_validation(self):
        result = _s().validate_primary_color("  #FFFFFF  ")
        self.assertEqual(result, "#FFFFFF")


class ValidateSecondaryColorTests(SimpleTestCase):
    def test_valid_hex(self):
        result = _s().validate_secondary_color("#F59E0B")
        self.assertEqual(result, "#F59E0B")

    def test_wrong_length_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_secondary_color("#FFFF")

    def test_invalid_chars_raise(self):
        with self.assertRaises(ValidationError):
            _s().validate_secondary_color("#XYZXYZ")


# ══════════════════════════════════════════════════════════════════════════════
# validate_language
# ══════════════════════════════════════════════════════════════════════════════

class ValidateLanguageTests(SimpleTestCase):
    def test_english_accepted(self):
        self.assertEqual(_s().validate_language("en"), "en")

    def test_french_accepted(self):
        self.assertEqual(_s().validate_language("fr"), "fr")

    def test_arabic_accepted(self):
        self.assertEqual(_s().validate_language("ar"), "ar")

    def test_empty_returns_default_en(self):
        self.assertEqual(_s().validate_language(""), "en")

    def test_none_returns_default_en(self):
        self.assertEqual(_s().validate_language(None), "en")

    def test_uppercase_accepted(self):
        self.assertEqual(_s().validate_language("EN"), "en")

    def test_locale_tag_uses_primary(self):
        # "en-US" → "en"
        self.assertEqual(_s().validate_language("en-US"), "en")

    def test_unsupported_language_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_language("de")

    def test_unsupported_language_es_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_language("es")


# ══════════════════════════════════════════════════════════════════════════════
# validate_receipt_message
# ══════════════════════════════════════════════════════════════════════════════

class ValidateReceiptMessageTests(SimpleTestCase):
    def test_plain_string_returned(self):
        self.assertEqual(_s().validate_receipt_message("Thank you!"), "Thank you!")

    def test_none_returns_empty(self):
        self.assertEqual(_s().validate_receipt_message(None), "")

    def test_whitespace_stripped(self):
        self.assertEqual(_s().validate_receipt_message("  hi  "), "hi")

    def test_truncated_to_300(self):
        long_msg = "a" * 400
        result = _s().validate_receipt_message(long_msg)
        self.assertEqual(len(result), 300)


# ══════════════════════════════════════════════════════════════════════════════
# validate_business_hours_schedule
# ══════════════════════════════════════════════════════════════════════════════

class ValidateBusinessHoursScheduleTests(SimpleTestCase):
    def _valid_entry(self, day="mon"):
        return {day: {"enabled": True, "open": "09:00", "close": "22:00"}}

    def test_none_returns_empty_dict(self):
        self.assertEqual(_s().validate_business_hours_schedule(None), {})

    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(_s().validate_business_hours_schedule(""), {})

    def test_non_dict_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule("open all day")

    def test_valid_single_day_accepted(self):
        result = _s().validate_business_hours_schedule(self._valid_entry())
        self.assertIn("mon", result)
        self.assertTrue(result["mon"]["enabled"])

    def test_all_seven_days_accepted(self):
        schedule = {}
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            schedule[day] = {"enabled": True, "open": "08:00", "close": "23:00"}
        result = _s().validate_business_hours_schedule(schedule)
        self.assertEqual(len(result), 7)

    def test_invalid_day_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule({"funday": {"enabled": True, "open": "09:00", "close": "22:00"}})

    def test_non_dict_entry_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule({"mon": "open"})

    def test_bad_open_time_format_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule({"mon": {"enabled": True, "open": "9am", "close": "22:00"}})

    def test_bad_close_time_format_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule({"mon": {"enabled": True, "open": "09:00", "close": "10pm"}})

    def test_same_open_close_raises(self):
        with self.assertRaises(ValidationError):
            _s().validate_business_hours_schedule({"mon": {"enabled": True, "open": "09:00", "close": "09:00"}})

    def test_disabled_entry_no_time_required(self):
        result = _s().validate_business_hours_schedule({"mon": {"enabled": False}})
        self.assertFalse(result["mon"]["enabled"])
        self.assertEqual(result["mon"]["open"], "")
        self.assertEqual(result["mon"]["close"], "")

    def test_time_cleared_when_disabled(self):
        result = _s().validate_business_hours_schedule(
            {"tue": {"enabled": False, "open": "09:00", "close": "22:00"}}
        )
        self.assertEqual(result["tue"]["open"], "")
        self.assertEqual(result["tue"]["close"], "")

    def test_uppercase_day_lowercased(self):
        result = _s().validate_business_hours_schedule(
            {"MON": {"enabled": True, "open": "09:00", "close": "18:00"}}
        )
        self.assertIn("mon", result)

    def test_midnight_boundary_time_valid(self):
        result = _s().validate_business_hours_schedule(
            {"fri": {"enabled": True, "open": "00:00", "close": "23:59"}}
        )
        self.assertEqual(result["fri"]["open"], "00:00")
