"""
Unit tests for:
  sales.audit
    - get_request_ip
  sales.serializers
    - AdminTenantSerializer.get_primary_domain
    - TierUpgradeRequestCreateSerializer.validate_payment_method
    - LeadSerializer.validate (no-DB parts: honeypot + contact requirement)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sales.audit import get_request_ip
from sales.serializers import (
    AdminTenantSerializer,
    LeadSerializer,
    TierUpgradeRequestCreateSerializer,
)


# ══════════════════════════════════════════════════════════════════════════════
# get_request_ip
# ══════════════════════════════════════════════════════════════════════════════

class GetRequestIpTests(SimpleTestCase):
    def _req(self, meta):
        return SimpleNamespace(META=meta)

    def test_forwarded_for_single_ip(self):
        req = self._req({"HTTP_X_FORWARDED_FOR": "1.2.3.4"})
        self.assertEqual(get_request_ip(req), "1.2.3.4")

    def test_forwarded_for_multiple_ips_returns_rightmost_trusted(self):
        """With TRUSTED_PROXY_COUNT=1 (default), return rightmost-trusted entry.

        XFF list = [client/spoofed..., proxy-appended].  One trusted proxy means
        we skip 1 from the right; with 3 IPs idx = 3-1 = 2, so the last entry.
        """
        req = self._req({"HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8, 9.10.11.12"})
        self.assertEqual(get_request_ip(req), "9.10.11.12")

    def test_forwarded_for_strips_whitespace(self):
        """Whitespace around each XFF entry is stripped; rightmost-trusted is returned."""
        req = self._req({"HTTP_X_FORWARDED_FOR": "  1.2.3.4  , 5.6.7.8"})
        self.assertEqual(get_request_ip(req), "5.6.7.8")

    def test_forwarded_for_takes_precedence_over_remote_addr(self):
        req = self._req({
            "HTTP_X_FORWARDED_FOR": "1.2.3.4",
            "REMOTE_ADDR": "10.0.0.1",
        })
        self.assertEqual(get_request_ip(req), "1.2.3.4")

    def test_falls_back_to_remote_addr_when_no_forwarded(self):
        req = self._req({"REMOTE_ADDR": "192.168.1.1"})
        self.assertEqual(get_request_ip(req), "192.168.1.1")

    def test_no_meta_keys_returns_none(self):
        req = self._req({})
        self.assertIsNone(get_request_ip(req))

    def test_empty_forwarded_for_falls_back_to_remote_addr(self):
        """Empty string is falsy — falls through to REMOTE_ADDR."""
        req = self._req({"HTTP_X_FORWARDED_FOR": "", "REMOTE_ADDR": "10.0.0.5"})
        self.assertEqual(get_request_ip(req), "10.0.0.5")


# ══════════════════════════════════════════════════════════════════════════════
# AdminTenantSerializer.get_primary_domain
# ══════════════════════════════════════════════════════════════════════════════

class AdminTenantSerializerGetPrimaryDomainTests(SimpleTestCase):
    def _s(self):
        return AdminTenantSerializer()

    def test_annotated_value_returned_directly(self):
        obj = SimpleNamespace(primary_domain_value="demo.example.com")
        self.assertEqual(self._s().get_primary_domain(obj), "demo.example.com")

    def test_annotated_empty_string_returns_empty(self):
        obj = SimpleNamespace(primary_domain_value="")
        self.assertEqual(self._s().get_primary_domain(obj), "")

    def test_annotated_none_falls_through_to_domains(self):
        """primary_domain_value=None → consults obj.domains."""
        domain = SimpleNamespace(domain="demo.example.com")
        domains = MagicMock()
        domains.filter.return_value.first.return_value = domain
        obj = SimpleNamespace(primary_domain_value=None, domains=domains)
        self.assertEqual(self._s().get_primary_domain(obj), "demo.example.com")

    def test_no_attribute_falls_through_to_domains(self):
        """No primary_domain_value attr at all → consults obj.domains."""
        domain = SimpleNamespace(domain="bistro.example.com")
        domains = MagicMock()
        domains.filter.return_value.first.return_value = domain
        obj = SimpleNamespace(domains=domains)  # no primary_domain_value attr
        self.assertEqual(self._s().get_primary_domain(obj), "bistro.example.com")

    def test_no_is_primary_domain_falls_back_to_first_domain(self):
        fallback = SimpleNamespace(domain="fallback.example.com")
        domains = MagicMock()
        domains.filter.return_value.first.return_value = None   # no is_primary
        domains.order_by.return_value.first.return_value = fallback
        obj = SimpleNamespace(primary_domain_value=None, domains=domains)
        self.assertEqual(self._s().get_primary_domain(obj), "fallback.example.com")

    def test_no_domains_at_all_returns_empty(self):
        domains = MagicMock()
        domains.filter.return_value.first.return_value = None
        domains.order_by.return_value.first.return_value = None
        obj = SimpleNamespace(primary_domain_value=None, domains=domains)
        self.assertEqual(self._s().get_primary_domain(obj), "")

    def test_domains_attribute_is_none_returns_empty(self):
        obj = SimpleNamespace(primary_domain_value=None, domains=None)
        self.assertEqual(self._s().get_primary_domain(obj), "")


# ══════════════════════════════════════════════════════════════════════════════
# TierUpgradeRequestCreateSerializer.validate_payment_method
# ══════════════════════════════════════════════════════════════════════════════

class TierUpgradeRequestValidatePaymentMethodTests(SimpleTestCase):
    def _s(self):
        return TierUpgradeRequestCreateSerializer()

    def test_cash_accepted(self):
        self.assertEqual(self._s().validate_payment_method("cash"), "cash")

    def test_bank_transfer_accepted(self):
        self.assertEqual(self._s().validate_payment_method("bank_transfer"), "bank_transfer")

    def test_other_accepted(self):
        self.assertEqual(self._s().validate_payment_method("other"), "other")

    def test_uppercase_cash_normalised_to_lowercase(self):
        self.assertEqual(self._s().validate_payment_method("CASH"), "cash")

    def test_mixed_case_normalised(self):
        self.assertEqual(self._s().validate_payment_method("Bank_Transfer"), "bank_transfer")

    def test_none_defaults_to_cash(self):
        self.assertEqual(self._s().validate_payment_method(None), "cash")

    def test_empty_defaults_to_cash(self):
        self.assertEqual(self._s().validate_payment_method(""), "cash")

    def test_whitespace_stripped_and_accepted(self):
        self.assertEqual(self._s().validate_payment_method("  cash  "), "cash")

    def test_unknown_method_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_payment_method("credit_card")

    def test_paypal_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate_payment_method("paypal")


# ══════════════════════════════════════════════════════════════════════════════
# LeadSerializer.validate — no-DB parts (honeypot + contact check)
# ══════════════════════════════════════════════════════════════════════════════

class LeadSerializerValidateTests(SimpleTestCase):
    """
    Tests for LeadSerializer.validate that do NOT require a database:
      - honeypot field blocks submission
      - email or phone is required
      - hp key is stripped from the returned attrs
    """

    def test_honeypot_truthy_raises(self):
        s = LeadSerializer()
        with self.assertRaises(ValidationError):
            s.validate({"hp": "filled-in", "name": "Alice", "email": "alice@example.com"})

    def test_neither_email_nor_phone_raises(self):
        s = LeadSerializer()
        with self.assertRaises(ValidationError):
            s.validate({"name": "Bob", "email": "", "phone": ""})

    def test_neither_email_nor_phone_when_both_missing_raises(self):
        s = LeadSerializer()
        with self.assertRaises(ValidationError):
            s.validate({"name": "Bob"})

    def test_email_alone_passes_contact_check(self):
        s = LeadSerializer()
        result = s.validate({"name": "Alice", "email": "alice@example.com"})
        self.assertIn("email", result)

    def test_phone_alone_passes_contact_check(self):
        s = LeadSerializer()
        result = s.validate({"name": "Bob", "phone": "+212600000000"})
        self.assertIn("phone", result)

    def test_hp_key_removed_from_output_when_falsy(self):
        """hp="" is falsy → no raise, but key must be absent from result."""
        s = LeadSerializer()
        result = s.validate({"name": "Alice", "email": "alice@example.com", "hp": ""})
        self.assertNotIn("hp", result)

    def test_plan_code_none_does_not_trigger_db(self):
        """plan_code=None or '' → skips Plan.objects.get; returns cleanly."""
        s = LeadSerializer()
        result = s.validate({"name": "Alice", "email": "alice@example.com", "plan_code": None})
        self.assertIn("email", result)
        self.assertNotIn("plan_code", result)

    def test_plan_code_empty_string_does_not_trigger_db(self):
        s = LeadSerializer()
        result = s.validate({"name": "Alice", "email": "alice@example.com", "plan_code": ""})
        self.assertIn("email", result)
