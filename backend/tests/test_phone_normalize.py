"""Tests for accounts.phone.normalize_e164 (pure — runs without a DB)."""
from django.test import SimpleTestCase

from accounts.phone import normalize_e164


class NormalizeE164Tests(SimpleTestCase):
    def test_keeps_international_and_strips_formatting(self):
        self.assertEqual(normalize_e164("+212612345678"), "+212612345678")
        self.assertEqual(normalize_e164("+212 6 12 34 56 78"), "+212612345678")
        self.assertEqual(normalize_e164("+212-612-345-678"), "+212612345678")

    def test_double_zero_prefix_becomes_plus(self):
        self.assertEqual(normalize_e164("00212612345678"), "+212612345678")

    def test_local_number_uses_default_dial_code(self):
        self.assertEqual(normalize_e164("0612345678", "212"), "+212612345678")
        self.assertEqual(normalize_e164("06 12 34 56 78", "212"), "+212612345678")

    def test_local_number_without_default_refuses(self):
        # No country context → don't guess.
        self.assertEqual(normalize_e164("0612345678"), "")

    def test_bare_national_number_refuses(self):
        self.assertEqual(normalize_e164("612345678"), "")

    def test_garbage_and_empty_return_empty(self):
        self.assertEqual(normalize_e164(""), "")
        self.assertEqual(normalize_e164(None), "")
        self.assertEqual(normalize_e164("not-a-phone"), "")
        self.assertEqual(normalize_e164("+12"), "")  # too short
