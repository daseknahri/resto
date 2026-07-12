"""RISK SER-1: QuantizedMoneyField behavior-preservation contract.

The field exists to migrate hand-rolled `Decimal(str(x)).quantize(Decimal("0.01"))` money reads
onto serializers WITHOUT changing which inputs are accepted. These tests pin that contract:
over-precision is ROUNDED (not rejected) exactly like the legacy quantize, while non-numeric,
non-finite, below-minimum, and beyond-column-width values are rejected — the last of which is the
only genuinely new rejection (it used to be an uncaught DB-overflow 500).
"""
from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework import serializers

from config.drf_fields import QuantizedMoneyField


class _AmountSerializer(serializers.Serializer):
    # max_digits=10 mirrors a destination column (e.g. DrawerTransaction.amount)
    amount = QuantizedMoneyField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))


class QuantizedMoneyFieldTests(SimpleTestCase):
    def _valid(self, value, expected):
        s = _AmountSerializer(data={"amount": value})
        self.assertTrue(s.is_valid(), f"{value!r} should be valid, errors={s.errors}")
        self.assertEqual(s.validated_data["amount"], expected)

    def _invalid(self, value):
        s = _AmountSerializer(data={"amount": value})
        self.assertFalse(s.is_valid(), f"{value!r} should be rejected")

    def test_plain_values_accepted(self):
        self._valid("25.00", Decimal("25.00"))
        self._valid("25", Decimal("25.00"))
        self._valid(25.5, Decimal("25.50"))
        self._valid(Decimal("7.30"), Decimal("7.30"))

    def test_over_precision_is_rounded_not_rejected(self):
        # Matches legacy Decimal(str(x)).quantize(Decimal("0.01")) — ambient ROUND_HALF_EVEN.
        self._valid("25.017", Decimal("25.02"))   # 3rd dp = 7 → up
        self._valid("25.005", Decimal("25.00"))   # half-even → down (preceding digit even)
        self._valid("0.009", Decimal("0.01"))     # rounds up, over the min_value floor

    def test_non_numeric_rejected(self):
        for bad in ("abc", "5,00", [1, 2], {"x": 1}):
            self._invalid(bad)

    def test_non_finite_rejected(self):
        # Decimal parses these, but quantize refuses them → legacy hit its bare except → 400.
        for bad in ("NaN", "Infinity", "-Infinity"):
            self._invalid(bad)

    def test_below_min_value_rejected(self):
        self._invalid("0.00")
        self._invalid("0.004")   # quantizes to 0.00
        self._invalid("-5.00")

    def test_beyond_max_digits_rejected(self):
        # The ONLY new rejection vs legacy: an out-of-column-range magnitude that previously
        # sailed past quantize and 500'd on DB insert is now a clean validation failure.
        self._invalid("999999999999.99")
        self._invalid("100000000.00")   # 9 int + 2 dp = 11 digits > max_digits=10
