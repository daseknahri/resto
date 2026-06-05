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


# ── Driver cash-out (redeem wallet balance for cash at a restaurant) ─────────────

CASHOUT_MIN = Decimal("100")          # driver must hold at least this to cash out
CASHOUT_TTL_SECONDS = 900             # a request code is valid for 15 min


class CashoutError(WalletError):
    """Cash-out specific failure; carries a stable machine `code`."""
    def __init__(self, message, code="cashout_error"):
        super().__init__(message)
        self.code = code


def create_cashout_request(driver_id, amount, *, ttl_seconds=CASHOUT_TTL_SECONDS):
    """Driver requests a cash-out: validates wallet ≥ CASHOUT_MIN and amount ≤ balance,
    then creates a PENDING request with a short code. Returns the DriverCashoutRequest."""
    from datetime import timedelta
    from django.utils import timezone
    from django.utils.crypto import get_random_string
    from .models import Customer, DriverCashoutRequest

    amount = _money(amount)
    cust = Customer.objects.filter(pk=driver_id).first()
    if cust is None:
        raise CashoutError("driver not found", code="not_found")
    balance = _money(cust.wallet_balance)
    if balance < CASHOUT_MIN:
        raise CashoutError(f"You need at least {CASHOUT_MIN} to cash out", code="below_min")
    if amount <= 0 or amount > balance:
        raise CashoutError("Enter an amount up to your balance", code="bad_amount")

    code = ""
    for _ in range(12):
        candidate = get_random_string(6, allowed_chars="0123456789")
        if not DriverCashoutRequest.objects.filter(
            code=candidate, status=DriverCashoutRequest.Status.PENDING
        ).exists():
            code = candidate
            break
    if not code:
        raise CashoutError("could not allocate a code, try again", code="retry")

    return DriverCashoutRequest.objects.create(
        driver_id=driver_id,
        amount=amount,
        code=code,
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )


def confirm_cashout(code, *, tenant_id, actor_user_id=None):
    """A restaurant confirms a driver cash-out by code. Atomically debits the driver's
    wallet (CASHOUT) and credits the restaurant's float (FUND). Idempotent on the request
    id. Returns the resolved DriverCashoutRequest. Raises CashoutError / InsufficientFunds.
    """
    from django.utils import timezone
    from .models import DriverCashoutRequest, WalletTransaction
    from .wallet_service import debit_wallet, credit_tenant_float

    code = (code or "").strip()
    now = timezone.now()
    with transaction.atomic():
        req = (
            DriverCashoutRequest.objects.select_for_update()
            .filter(code=code, status=DriverCashoutRequest.Status.PENDING)
            .first()
        )
        if req is None:
            raise CashoutError("No pending cash-out for that code", code="not_found")
        if req.expires_at <= now:
            req.status = DriverCashoutRequest.Status.EXPIRED
            req.resolved_at = now
            req.save(update_fields=["status", "resolved_at"])
            raise CashoutError("That cash-out code has expired", code="expired")

        wtx = debit_wallet(
            req.driver_id, req.amount,
            tx_type=WalletTransaction.Type.CASHOUT,
            idempotency_key=f"cashout:{req.id}",
            reference=f"cashout:{code}",
            tenant_id=tenant_id,
            note="Driver cash-out",
        )
        credit_tenant_float(
            tenant_id, req.amount,
            actor_user_id=actor_user_id,
            idempotency_key=f"cashout:{req.id}:f",
            reference=f"cashout:{code}",
            note="Driver cash-out reimbursement",
        )
        req.status = DriverCashoutRequest.Status.PAID
        req.tenant_id = tenant_id
        req.actor_user_id = actor_user_id
        req.wallet_tx_id = getattr(wtx, "id", None)
        req.resolved_at = now
        req.save(update_fields=["status", "tenant_id", "actor_user_id", "wallet_tx_id", "resolved_at"])
    return req
