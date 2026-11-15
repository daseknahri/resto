"""Run 8 / S1-I (B-15): server-side WhatsApp reminder links use normalize_e164.

`_build_whatsapp_reservation_reminder` (backend/sales/views.py) used to strip a
reservation lead's phone to raw digits, so a national-format "06…" lead produced
a dead wa.me/0612345678 link. It now goes through accounts.phone.normalize_e164
with the tenant default dial code 212 (MAD) — the same rule as the wallet
transfers. No DB access: lead/tenant are plain namespaces.

Run with the repo's backend suite (Django test runner, e.g. the sales app
tests); SimpleTestCase needs no database.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from accounts.phone import normalize_e164
from sales.views import _build_whatsapp_reservation_reminder


def _lead(phone, name="Sara Bennani"):
    return SimpleNamespace(phone=phone, name=name)


def _tenant(name="Testaurant"):
    return SimpleNamespace(name=name)


class BuildWhatsappReservationReminderTests(SimpleTestCase):
    def test_national_format_gets_212_country_code(self):
        payload = _build_whatsapp_reservation_reminder(lead=_lead("0612345678"), tenant=_tenant())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["phone"], "212612345678")
        self.assertTrue(payload["whatsapp_link"].startswith("https://wa.me/212612345678?text="))
        self.assertNotIn("wa.me/0612345678", payload["whatsapp_link"])

    def test_national_format_with_spaces_and_dashes(self):
        payload = _build_whatsapp_reservation_reminder(lead=_lead("06 12-34 56 78"), tenant=_tenant())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["phone"], "212612345678")

    def test_e164_kept(self):
        payload = _build_whatsapp_reservation_reminder(lead=_lead("+212612345678"), tenant=_tenant())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["phone"], "212612345678")

    def test_double_zero_prefix(self):
        payload = _build_whatsapp_reservation_reminder(lead=_lead("00212612345678"), tenant=_tenant())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["phone"], "212612345678")

    def test_bare_digits_refused_not_guessed(self):
        # normalize_e164 refuses bare digits with no leading 0 / + / 00, so the
        # reminder is skipped (None) rather than linked to a guessed number.
        # NOTE: this deliberately differs from the frontend toWaPhone(), which
        # keeps a bare "212…" (international, "+" omitted) — the backend follows
        # the wallet normalizer exactly.
        self.assertIsNone(_build_whatsapp_reservation_reminder(lead=_lead("612345678"), tenant=_tenant()))
        self.assertIsNone(_build_whatsapp_reservation_reminder(lead=_lead("212612345678"), tenant=_tenant()))

    def test_empty_and_garbage_phone_returns_none(self):
        self.assertIsNone(_build_whatsapp_reservation_reminder(lead=_lead(""), tenant=_tenant()))
        self.assertIsNone(_build_whatsapp_reservation_reminder(lead=_lead(None), tenant=_tenant()))
        self.assertIsNone(_build_whatsapp_reservation_reminder(lead=_lead("abc"), tenant=_tenant()))

    def test_message_names_guest_and_restaurant(self):
        payload = _build_whatsapp_reservation_reminder(lead=_lead("0612345678"), tenant=_tenant())
        self.assertIn("Sara Bennani", payload["message"])
        self.assertIn("Testaurant", payload["message"])


class NormalizeE164DirectTests(SimpleTestCase):
    """Direct parity checks on the normalizer the reminder builder relies on."""

    def test_national_needs_default_dial_code(self):
        self.assertEqual(normalize_e164("0612345678", "212"), "+212612345678")
        # No country context configured -> refuse, never guess.
        self.assertEqual(normalize_e164("0612345678", ""), "")

    def test_international_forms(self):
        self.assertEqual(normalize_e164("+212612345678", "212"), "+212612345678")
        self.assertEqual(normalize_e164("00212612345678", "212"), "+212612345678")

    def test_bare_digits_refused(self):
        self.assertEqual(normalize_e164("612345678", "212"), "")
        self.assertEqual(normalize_e164("212612345678", "212"), "")
