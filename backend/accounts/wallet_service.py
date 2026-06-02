"""Central wallet ledger service.

The single, safe entry point for moving money in/out of a customer's wallet. Every
operation is:
  • atomic — the customer row is locked (select_for_update) so concurrent
    debits/credits can't race the balance,
  • idempotent — pass an idempotency_key and a retry (e.g. a re-delivered Stripe
    webhook, a double-tapped button) reuses the original transaction instead of
    moving money twice,
  • audited — a WalletTransaction is written with a balance_after snapshot.

`amount` is always a positive magnitude; the `type` records direction. Callers
across the platform (orders, top-ups, refunds, bonuses, loyalty) should funnel
through here so the ledger stays consistent and reconcilable.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import Customer, WalletTransaction

_CENT = Decimal("0.01")


class WalletError(Exception):
    """Generic wallet failure (bad input)."""


class InsufficientFunds(WalletError):
    """Raised when a debit exceeds the available balance (and partial not allowed)."""


def _money(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(_CENT)
    except (InvalidOperation, ValueError, TypeError):
        raise WalletError("invalid amount")


def _find_idempotent(idempotency_key):
    if not idempotency_key:
        return None
    return WalletTransaction.objects.filter(idempotency_key=idempotency_key).first()


@transaction.atomic
def credit_wallet(customer_id, amount, *, tx_type=WalletTransaction.Type.TOPUP,
                  idempotency_key=None, reference="", tenant_id=None, note="", currency="MAD"):
    """Add funds to a wallet. Returns the WalletTransaction (existing one on retry)."""
    amount = _money(amount)
    if amount <= 0:
        raise WalletError("credit amount must be positive")

    existing = _find_idempotent(idempotency_key)
    if existing is not None:
        return existing

    cust = Customer.objects.select_for_update().get(pk=customer_id)
    new_balance = (_money(cust.wallet_balance) + amount).quantize(_CENT)
    cust.wallet_balance = new_balance
    cust.save(update_fields=["wallet_balance", "updated_at"])

    return WalletTransaction.objects.create(
        customer=cust,
        type=tx_type,
        amount=amount,
        balance_after=new_balance,
        idempotency_key=idempotency_key or None,
        reference=reference or "",
        tenant_id=tenant_id,
        note=note or "",
        currency=currency,
    )


@transaction.atomic
def debit_wallet(customer_id, amount, *, tx_type=WalletTransaction.Type.PAYMENT,
                 idempotency_key=None, reference="", tenant_id=None, note="",
                 currency="MAD", allow_partial=False):
    """Remove funds from a wallet.

    With allow_partial=False (default) a debit larger than the balance raises
    InsufficientFunds. With allow_partial=True it charges whatever is available
    (returns None if the balance is zero). Returns the WalletTransaction (existing
    one on retry); the stored amount is the positive magnitude actually charged.
    """
    amount = _money(amount)
    if amount <= 0:
        raise WalletError("debit amount must be positive")

    existing = _find_idempotent(idempotency_key)
    if existing is not None:
        return existing

    cust = Customer.objects.select_for_update().get(pk=customer_id)
    balance = _money(cust.wallet_balance)

    charge = min(amount, balance) if allow_partial else amount
    if charge > balance:
        raise InsufficientFunds("wallet balance is insufficient")
    if charge <= 0:
        return None

    new_balance = (balance - charge).quantize(_CENT)
    cust.wallet_balance = new_balance
    cust.save(update_fields=["wallet_balance", "updated_at"])

    return WalletTransaction.objects.create(
        customer=cust,
        type=tx_type,
        amount=charge,
        balance_after=new_balance,
        idempotency_key=idempotency_key or None,
        reference=reference or "",
        tenant_id=tenant_id,
        note=note or "",
        currency=currency,
    )
