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
    """Return {earned, paid, owed, ride_earned, rides_completed} for a driver, as quantised Decimals."""
    from .models import DeliveryJob, DriverPayout, RideRequest, WalletTransaction

    earned = (
        DeliveryJob.objects
        .filter(driver_id=driver_id, status=DeliveryJob.Status.DELIVERED)
        .aggregate(s=Sum("driver_payout"))["s"]
    ) or Decimal("0")
    paid = (
        DriverPayout.objects.filter(driver_id=driver_id).aggregate(s=Sum("amount"))["s"]
    ) or Decimal("0")

    ride_earned_raw = (
        WalletTransaction.objects
        .filter(customer_id=driver_id, type=WalletTransaction.Type.EARNING, reference__startswith="ride:")
        .aggregate(s=Sum("amount"))["s"]
    ) or Decimal("0")

    rides_completed = RideRequest.objects.filter(
        driver_id=driver_id, status=RideRequest.Status.COMPLETED
    ).count()

    earned = _money(earned)
    paid = _money(paid)
    return {
        "earned": earned,
        "paid": paid,
        "owed": _money(earned - paid),
        "ride_earned": _money(ride_earned_raw),
        "rides_completed": rides_completed,
    }


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

# Brute-force lockout for confirm_cashout: the 6-digit code lives in a ~1e6 space, so
# without a per-actor failed-attempt cap a scanner could iterate it. A legitimate
# confirm has the right code on the first try (0 failures); a scanner racks up failures
# and is locked fast, which is what makes the space infeasible to brute-force. The
# counter is keyed per confirming actor (user, falling back to tenant) in the cache and
# reset on a successful confirm.
CASHOUT_CONFIRM_MAX_FAILURES = 5      # failed confirms before the actor is locked out
CASHOUT_CONFIRM_LOCK_SECONDS = 900    # lockout / counting window (15 min)


def _cashout_fail_cache_key(*, actor_user_id, tenant_id) -> str:
    """Per-actor key for failed confirm attempts (prefer user, fall back to tenant)."""
    ident = f"u{actor_user_id}" if actor_user_id else f"t{tenant_id}"
    return f"cashout_confirm_fail:{ident}"


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
    # Only approved drivers may extract cash (defense-in-depth; earning already requires approval).
    if not getattr(cust, "driver_approved", False):
        raise CashoutError("Your driver account isn't approved yet", code="not_approved")
    balance = _money(cust.wallet_balance)
    if balance < CASHOUT_MIN:
        raise CashoutError(f"You need at least {CASHOUT_MIN} to cash out", code="below_min")
    if amount <= 0 or amount > balance:
        raise CashoutError("Enter an amount up to your balance", code="bad_amount")
    # One live request at a time, so a driver can't hand out several codes against one balance.
    if DriverCashoutRequest.objects.filter(
        driver_id=driver_id,
        status=DriverCashoutRequest.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).exists():
        raise CashoutError("You already have a pending cash-out — show or cancel it first",
                           code="already_pending")

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
    from django.core.cache import cache
    from django.utils import timezone
    from .models import DriverCashoutRequest, WalletTransaction
    from .wallet_service import debit_wallet, credit_tenant_float

    code = (code or "").strip()
    now = timezone.now()

    # Per-actor brute-force lockout: a scanner iterating the 6-digit code racks up
    # failures fast and is locked out; a legit confirm (right code first try) never
    # increments the counter, so this is transparent to honest callers.
    fail_key = _cashout_fail_cache_key(actor_user_id=actor_user_id, tenant_id=tenant_id)
    if (cache.get(fail_key) or 0) >= CASHOUT_CONFIRM_MAX_FAILURES:
        raise CashoutError(
            "Too many incorrect cash-out codes — try again shortly.", code="locked"
        )

    def _record_failure():
        try:
            cache.set(fail_key, (cache.get(fail_key) or 0) + 1, CASHOUT_CONFIRM_LOCK_SECONDS)
        except Exception:
            pass

    with transaction.atomic():
        req = (
            DriverCashoutRequest.objects.select_for_update()
            .filter(code=code, status=DriverCashoutRequest.Status.PENDING)
            .first()
        )
        if req is None:
            _record_failure()
            raise CashoutError("No pending cash-out for that code", code="not_found")
        if req.expires_at <= now:
            _record_failure()
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
    # A successful confirm clears the actor's failed-attempt counter.
    try:
        cache.delete(fail_key)
    except Exception:
        pass
    return req
