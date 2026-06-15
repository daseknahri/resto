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
import logging
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction

from .models import Customer, TenantFloatTransaction, WalletTransaction

_CENT = Decimal("0.01")

# R15: dedicated money-failure channel. Every failure on a money mutation (insufficient
# funds, idempotency-key collision, unexpected DB error) is emitted here so it can be
# alerted on as its own rate. Messages carry the tenant schema + the relevant id only —
# never balances/PII beyond ids — so a failure is attributable without leaking money data.
payments_logger = logging.getLogger("payments")


def _schema() -> str:
    """Best-effort current tenant schema for log attribution (never raises)."""
    try:
        return connection.schema_name
    except Exception:
        return "?"


def _ref_kind(reference) -> str:
    """The non-secret category of a wallet reference, safe to put in logs/Sentry.

    References are namespaced as ``kind:value`` (e.g. ``order_number``, ``ride:42``,
    ``loyalty:30``, ``cashout:123456``). The value half can be a live secret — the
    driver cash-out reference carries the 6-digit bearer cash-out code, which the
    insufficient-funds branch could otherwise leak into the dedicated ``payments``
    logger (and onward to Sentry) while the code is still PENDING/re-usable. Emit only
    the namespace so the event stays attributable without exposing any code digits.
    """
    ref = (reference or "").strip()
    if not ref:
        return ""
    return ref.split(":", 1)[0]


class WalletError(Exception):
    """Generic wallet failure (bad input)."""


class InsufficientFunds(WalletError):
    """Raised when a debit exceeds the available balance (and partial not allowed)."""


class UnverifiedWallet(WalletError):
    """Raised when a customer without a verified phone tries to receive wallet funds.

    Platform rule: no verified phone → no wallet. Funds may only land in a wallet whose
    owner has a verified phone number.
    """


class InactiveTenant(WalletError):
    """Raised when float is funded into / distributed from a non-active restaurant.

    A restaurant's identity is its tenant + owner account; the analog of a customer's
    verified phone is an *active* tenant. Suspended/canceled restaurants can't move float.
    """


def _money(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(_CENT)
    except (InvalidOperation, ValueError, TypeError):
        raise WalletError("invalid amount")


def _find_idempotent(idempotency_key):
    if not idempotency_key:
        return None
    return WalletTransaction.objects.filter(idempotency_key=idempotency_key).first()


def _find_idempotent_float(idempotency_key):
    if not idempotency_key:
        return None
    return TenantFloatTransaction.objects.filter(idempotency_key=idempotency_key).first()


def _require_verified(customer):
    """Enforce the 'no verified phone → no wallet' rule before crediting a wallet."""
    if not getattr(customer, "phone_verified", False):
        raise UnverifiedWallet("a verified phone number is required to use a wallet")


def _require_active_tenant(tenant):
    """A restaurant must be active to fund or distribute float (lifecycle is its 'verified')."""
    status_value = getattr(tenant, "lifecycle_status", "active")
    if status_value != "active" or not getattr(tenant, "is_active", True):
        raise InactiveTenant("restaurant is not active")


@transaction.atomic
def credit_wallet(customer_id, amount, *, tx_type=WalletTransaction.Type.TOPUP,
                  idempotency_key=None, reference="", tenant_id=None, note="", currency="MAD",
                  require_verified=True):
    """Add funds to a wallet. Returns the WalletTransaction (existing one on retry).

    ``require_verified`` enforces the no-verified-phone-no-wallet rule (default). Pass
    False for system-originated credits the owner didn't ask for, e.g. driver delivery
    earnings — the driver clearly exists and shouldn't lose pay over an unverified phone.
    """
    amount = _money(amount)
    if amount <= 0:
        raise WalletError("credit amount must be positive")

    existing = _find_idempotent(idempotency_key)
    if existing is not None:
        # Defense-in-depth: a legit retry always targets the same customer. A key that
        # resolves to a DIFFERENT customer's tx is a collision/attack on a caller-supplied
        # key, not a retry — refuse rather than return someone else's transaction.
        # (Assert customer only: a partial debit legitimately stores a different amount.)
        if existing.customer_id != int(customer_id):
            payments_logger.error(
                "wallet credit idempotency-key collision schema=%s customer_id=%s key=%s",
                _schema(), customer_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another customer")
        return existing

    cust = Customer.objects.select_for_update().get(pk=customer_id)
    if require_verified:
        _require_verified(cust)
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
        # Defense-in-depth: a legit retry always targets the same customer. A key that
        # resolves to a DIFFERENT customer's tx is a collision/attack on a caller-supplied
        # key, not a retry — refuse rather than return someone else's transaction.
        # (Assert customer only: allow_partial legitimately stores a PARTIAL amount that
        # differs from the requested one, so an amount assertion would false-positive.)
        if existing.customer_id != int(customer_id):
            payments_logger.error(
                "wallet debit idempotency-key collision schema=%s customer_id=%s key=%s",
                _schema(), customer_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another customer")
        return existing

    cust = Customer.objects.select_for_update().get(pk=customer_id)
    balance = _money(cust.wallet_balance)

    charge = min(amount, balance) if allow_partial else amount
    if charge > balance:
        payments_logger.warning(
            # NEVER log the raw reference here: the driver cash-out reference carries the
            # 6-digit bearer cash-out code, which is still live (request stays PENDING on
            # InsufficientFunds) and would otherwise leak into the payments logger / Sentry.
            # customer_id + tenant_id already make this attributable; log only the ref kind.
            "wallet debit insufficient funds schema=%s customer_id=%s tenant_id=%s ref_kind=%s",
            _schema(), customer_id, tenant_id, _ref_kind(reference),
        )
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


# ── Restaurant float (closed-loop money distribution) ───────────────────────────
#
# Two-tier model: the platform funds a restaurant's float, then the owner spends
# that float down by topping up customers. Cash is reconciled offline (collected
# daily). Owners can never distribute more than they hold — the float is a hard cap.


@transaction.atomic
def credit_tenant_float(tenant_id, amount, *, actor_user_id=None, idempotency_key=None,
                        reference="", note="", currency="MAD"):
    """Platform funds a restaurant's distributable float. Returns the TenantFloatTransaction.

    Idempotent on idempotency_key (a retried request reuses the original row).
    """
    from tenancy.models import Tenant

    amount = _money(amount)
    if amount <= 0:
        raise WalletError("funding amount must be positive")

    existing = _find_idempotent_float(idempotency_key)
    if existing is not None:
        # Defense-in-depth: a legit retry always targets the same tenant. A key that
        # resolves to a DIFFERENT tenant's float tx is a collision/attack on a
        # caller-supplied key, not a retry — refuse rather than reuse it.
        if existing.tenant_id != int(tenant_id):
            payments_logger.error(
                "float funding idempotency-key collision schema=%s tenant_id=%s key=%s",
                _schema(), tenant_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another tenant")
        return existing

    tenant = Tenant.objects.select_for_update().get(pk=tenant_id)
    _require_active_tenant(tenant)
    new_balance = (_money(tenant.float_balance) + amount).quantize(_CENT)
    tenant.float_balance = new_balance
    tenant.save(update_fields=["float_balance"])

    return TenantFloatTransaction.objects.create(
        tenant_id=tenant_id,
        type=TenantFloatTransaction.Type.FUND,
        amount=amount,
        balance_after=new_balance,
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key or None,
        reference=reference or "",
        note=note or "",
        currency=currency,
    )


@transaction.atomic
def transfer_to_customer(tenant_id, customer_id, amount, *, actor_user_id=None,
                         idempotency_key=None, reference="", note="", currency="MAD"):
    """Move funds from a restaurant's float into a customer's wallet (prepaid distribution).

    Atomic double-entry posting: debits the restaurant float and credits the customer
    wallet in one transaction. Raises InsufficientFunds if the float can't cover the
    amount (nothing moves). Returns (float_tx, wallet_tx). Idempotent on idempotency_key.
    """
    from tenancy.models import Tenant

    amount = _money(amount)
    if amount <= 0:
        raise WalletError("transfer amount must be positive")

    existing = _find_idempotent_float(idempotency_key)
    if existing is not None:
        # Defense-in-depth (OPS-5e): idempotency_key is a GLOBAL namespace on the
        # shared-schema ledger. A legit retry always targets the same tenant; a key
        # that resolves to a DIFFERENT tenant's float tx is a collision/attack on a
        # caller-supplied key, not a retry — refuse rather than silently no-op and
        # leak the other tenant's balance. (Mirrors credit_tenant_float; do NOT
        # assert amount on replay.)
        if existing.tenant_id != int(tenant_id):
            payments_logger.error(
                "float transfer idempotency-key collision schema=%s tenant_id=%s "
                "customer_id=%s key=%s",
                _schema(), tenant_id, customer_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another tenant")
        wallet_tx = None
        if idempotency_key:
            wallet_tx = WalletTransaction.objects.filter(
                idempotency_key=f"{idempotency_key}:w"
            ).first()
        return existing, wallet_tx

    # Lock both rows in a stable order (tenant, then customer) to avoid deadlocks.
    tenant = Tenant.objects.select_for_update().get(pk=tenant_id)
    cust = Customer.objects.select_for_update().get(pk=customer_id)
    _require_active_tenant(tenant)
    _require_verified(cust)

    float_balance = _money(tenant.float_balance)
    if amount > float_balance:
        payments_logger.warning(
            "float transfer insufficient float schema=%s tenant_id=%s customer_id=%s",
            _schema(), tenant_id, customer_id,
        )
        raise InsufficientFunds("restaurant float is insufficient")

    new_float = (float_balance - amount).quantize(_CENT)
    new_wallet = (_money(cust.wallet_balance) + amount).quantize(_CENT)

    tenant.float_balance = new_float
    tenant.save(update_fields=["float_balance"])
    cust.wallet_balance = new_wallet
    cust.save(update_fields=["wallet_balance", "updated_at"])

    float_tx = TenantFloatTransaction.objects.create(
        tenant_id=tenant_id,
        type=TenantFloatTransaction.Type.DISTRIBUTION,
        amount=amount,
        balance_after=new_float,
        customer=cust,
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key or None,
        reference=reference or "",
        note=note or "",
        currency=currency,
    )
    wallet_tx = WalletTransaction.objects.create(
        customer=cust,
        type=WalletTransaction.Type.TOPUP,
        amount=amount,
        balance_after=new_wallet,
        idempotency_key=(f"{idempotency_key}:w" if idempotency_key else None),
        reference=reference or "",
        tenant_id=tenant_id,
        note=note or "",
        currency=currency,
    )
    return float_tx, wallet_tx


# ── Peer-to-peer gifting (on-platform, no cash-out) ─────────────────────────────
#
# Regulated money transmission in most markets — gated behind settings.WALLET_P2P_ENABLED
# at the view layer. The service itself just moves the money atomically; it does NOT
# check the feature flag (callers must) so it stays unit-testable.


@transaction.atomic
def transfer_between_customers(sender_id, recipient_id, amount, *, idempotency_key=None,
                              note="", currency="MAD"):
    """Move wallet credit from one customer to another (a gift). Atomic + idempotent.

    Debits the sender and credits the recipient in one transaction. Raises
    InsufficientFunds if the sender can't cover it (nothing moves), or WalletError on
    bad input (non-positive amount, or sending to yourself). Returns (out_tx, in_tx).
    """
    amount = _money(amount)
    if amount <= 0:
        raise WalletError("transfer amount must be positive")
    if str(sender_id) == str(recipient_id):
        raise WalletError("cannot transfer to yourself")

    existing = _find_idempotent(idempotency_key)
    if existing is not None:
        # Defense-in-depth (OPS-5f, mirrors OPS-5e on the other ledger helpers):
        # idempotency_key is a GLOBAL namespace on the shared-schema ledger. A legit
        # retry always replays the SAME sender's out-tx; a key that resolves to a
        # DIFFERENT customer's tx is a collision/attack on a caller-supplied key, not a
        # retry — refuse rather than hand back someone else's transaction. (Assert the
        # sender IDENTITY only; never amount — partial charges store a different amount.)
        if existing.customer_id != int(sender_id):
            payments_logger.error(
                "p2p transfer idempotency-key collision schema=%s sender_id=%s "
                "recipient_id=%s key=%s",
                _schema(), sender_id, recipient_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another customer")
        in_tx = None
        if idempotency_key:
            in_tx = WalletTransaction.objects.filter(
                idempotency_key=f"{idempotency_key}:in"
            ).first()
        return existing, in_tx

    # Lock both rows in a stable order (lowest id first) to avoid deadlocks.
    first_id, second_id = sorted([int(sender_id), int(recipient_id)])
    locked = {
        c.id: c
        for c in Customer.objects.select_for_update().filter(pk__in=[first_id, second_id])
    }
    sender = locked.get(int(sender_id))
    recipient = locked.get(int(recipient_id))
    if sender is None or recipient is None:
        raise WalletError("sender or recipient not found")
    _require_verified(sender)
    _require_verified(recipient)

    sender_balance = _money(sender.wallet_balance)
    if amount > sender_balance:
        payments_logger.warning(
            "p2p transfer insufficient funds schema=%s sender_id=%s recipient_id=%s",
            _schema(), sender_id, recipient_id,
        )
        raise InsufficientFunds("wallet balance is insufficient")

    new_sender = (sender_balance - amount).quantize(_CENT)
    new_recipient = (_money(recipient.wallet_balance) + amount).quantize(_CENT)

    sender.wallet_balance = new_sender
    sender.save(update_fields=["wallet_balance", "updated_at"])
    recipient.wallet_balance = new_recipient
    recipient.save(update_fields=["wallet_balance", "updated_at"])

    out_tx = WalletTransaction.objects.create(
        customer=sender,
        type=WalletTransaction.Type.TRANSFER_OUT,
        amount=amount,
        balance_after=new_sender,
        idempotency_key=idempotency_key or None,
        reference=f"to:{recipient_id}",
        note=note or "",
        currency=currency,
    )
    in_tx = WalletTransaction.objects.create(
        customer=recipient,
        type=WalletTransaction.Type.TRANSFER_IN,
        amount=amount,
        balance_after=new_recipient,
        idempotency_key=(f"{idempotency_key}:in" if idempotency_key else None),
        reference=f"from:{sender_id}",
        note=note or "",
        currency=currency,
    )
    return out_tx, in_tx
