"""Driver earnings & payouts.

Drivers earn `driver_payout` on each delivered DeliveryJob. Earnings are therefore
computed from delivered jobs; this module summarises them and records settlements
(DriverPayout). Reuses the wallet service's money helpers and error type.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .wallet_service import _money, WalletError  # reuse quantize + error semantics


def driver_earnings_summary(driver_id) -> dict:
    """Return {earned, paid, owed} for a driver, as quantised Decimals."""
    from .models import DeliveryJob, DriverPayout

    earned = (
        DeliveryJob.objects
        .filter(driver_id=driver_id, status=DeliveryJob.Status.DELIVERED)
        .aggregate(s=Sum("driver_payout"))["s"]
    ) or Decimal("0")
    paid = (
        DriverPayout.objects.filter(driver_id=driver_id).aggregate(s=Sum("amount"))["s"]
    ) or Decimal("0")

    earned = _money(earned)
    paid = _money(paid)
    return {"earned": earned, "paid": paid, "owed": _money(earned - paid)}


@transaction.atomic
def record_driver_payout(driver_id, amount, *, method="cash", reference="", note="",
                         actor_user_id=None, idempotency_key=None, currency="MAD"):
    """Record a settlement paid to a driver. Idempotent; never pays more than owed."""
    from .models import DriverPayout

    amount = _money(amount)
    if amount <= 0:
        raise WalletError("payout amount must be positive")

    if idempotency_key:
        existing = DriverPayout.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    owed = driver_earnings_summary(driver_id)["owed"]
    if amount > owed:
        raise WalletError("payout exceeds the amount owed to this driver")

    return DriverPayout.objects.create(
        driver_id=driver_id,
        amount=amount,
        method=(method if method in dict(DriverPayout.Method.choices) else DriverPayout.Method.CASH),
        reference=reference or "",
        note=note or "",
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key or None,
        currency=currency,
    )
