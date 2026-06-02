"""Unit tests for VAT breakdown helpers (menu/tax.py).

Prices are VAT-inclusive, so these verify the VAT portion is correctly *extracted*
from an already-inclusive amount (the charged total never changes).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.tax import order_vat_fields, vat_breakdown


class VatBreakdownTests(SimpleTestCase):
    def test_zero_rate_returns_gross_and_no_vat(self):
        net, vat = vat_breakdown(120, 0)
        self.assertEqual(net, Decimal("120.00"))
        self.assertEqual(vat, Decimal("0.00"))

    def test_20pct_inclusive(self):
        # 120 incl. @20% → vat = 120*20/120 = 20.00, net = 100.00
        net, vat = vat_breakdown(120, 20)
        self.assertEqual(vat, Decimal("20.00"))
        self.assertEqual(net, Decimal("100.00"))

    def test_10pct_inclusive_rounds_half_up(self):
        # 100 incl. @10% → vat = 100*10/110 = 9.0909… → 9.09, net = 90.91
        net, vat = vat_breakdown(100, 10)
        self.assertEqual(vat, Decimal("9.09"))
        self.assertEqual(net, Decimal("90.91"))

    def test_non_positive_gross_is_safe(self):
        for gross in (0, -5, "-1.00"):
            net, vat = vat_breakdown(gross, 20)
            self.assertEqual(vat, Decimal("0.00"))

    def test_tolerates_strings_and_none(self):
        net, vat = vat_breakdown("120.00", "20")
        self.assertEqual(vat, Decimal("20.00"))
        net, vat = vat_breakdown(None, None)
        self.assertEqual(net, Decimal("0.00"))
        self.assertEqual(vat, Decimal("0.00"))


class OrderVatFieldsTests(SimpleTestCase):
    @staticmethod
    def _order(total, delivery=0, tip=0):
        return SimpleNamespace(total=total, delivery_fee=delivery, tip_amount=tip)

    def test_base_excludes_delivery_and_tip(self):
        # total 150 = food 120 + delivery 20 + tip 10; @20% → base 120, vat 20
        fields = order_vat_fields(self._order(150, delivery=20, tip=10), 20, "TVA")
        self.assertEqual(fields["vat_taxable_base"], "120.00")
        self.assertEqual(fields["vat_amount"], "20.00")
        self.assertEqual(fields["vat_net_amount"], "100.00")
        self.assertEqual(fields["vat_label"], "TVA")
        self.assertEqual(fields["vat_rate"], "20.00")

    def test_disabled_when_rate_zero(self):
        fields = order_vat_fields(self._order(120), 0)
        self.assertEqual(fields["vat_amount"], "0.00")
        self.assertEqual(fields["vat_label"], "")
        self.assertEqual(fields["vat_rate"], "0.00")

    def test_label_defaults_to_vat(self):
        fields = order_vat_fields(self._order(120), 20)
        self.assertEqual(fields["vat_label"], "VAT")

    def test_taxable_base_never_negative(self):
        fields = order_vat_fields(self._order(10, delivery=20, tip=10), 20)
        self.assertEqual(fields["vat_taxable_base"], "0.00")
        self.assertEqual(fields["vat_amount"], "0.00")
