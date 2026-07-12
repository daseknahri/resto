"""Reusable DRF serializer fields (RISK SER-1).

`QuantizedMoneyField` is the migration primitive for moving the ~242 hand-rolled
`request.data` money reads onto serializers *without* changing which inputs are accepted.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import serializers


class QuantizedMoneyField(serializers.DecimalField):
    """A money `DecimalField` that mirrors the legacy hand-rolled parse

        amount = Decimal(str(request.data.get("amount"))).quantize(Decimal("0.01"))

    so a handler can migrate to a serializer with **zero change to accepted inputs**.

    Why not a plain `DecimalField`: DRF's stock field *rejects* any input with more than
    `decimal_places` fractional digits (e.g. ``"25.005"``), but the legacy code silently
    **rounds** it to 2 dp and proceeds. A naive swap would therefore start returning 400 for
    values the old code accepted. This field pre-quantizes to 2 dp (same rounding as the legacy
    `Decimal.quantize`, i.e. the ambient decimal context) *before* `DecimalField`'s own
    range/precision checks run. Net effect versus the legacy code:

    * non-numeric / NaN / Infinity  → 400  (legacy raised in its bare ``except`` → 400)  — same
    * over-precision (>2 dp)         → rounded, then validated                          — same
    * below ``min_value``            → 400                                              — same as a `<= 0` guard
    * magnitude beyond ``max_digits``→ 400  (legacy: silent DB NUMERIC overflow → **500**) — fixed

    So the only new rejection is a genuinely out-of-range magnitude, which was already broken
    (an uncaught 500) rather than a supported input. Set ``max_digits`` to the destination
    column's width so the clean 400 replaces the overflow crash.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        # Match the legacy `Decimal(str(x)).quantize(Decimal("0.01"))` exactly: coerce, then
        # round over-precision (never reject it). Anything Decimal can't parse — including the
        # non-finite NaN/Infinity that quantize refuses — becomes DRF's standard "invalid" 400.
        try:
            quantized = Decimal(str(data)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            self.fail("invalid")
        # DecimalField now enforces max_digits (→ clean 400 instead of a DB-overflow 500) and
        # min_value/max_value on the already-quantized value.
        return super().to_internal_value(quantized)
