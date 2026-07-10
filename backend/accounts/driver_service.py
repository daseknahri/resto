"""Driver earnings & payouts.

Drivers earn `driver_payout` on each delivered DeliveryJob. Earnings are therefore
computed from delivered jobs; this module summarises them and records settlements
(DriverPayout). Reuses the wallet service's money helpers and error type.
"""
import logging
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Sum

from .wallet_service import _money, WalletError, _ref_kind  # reuse quantize + error semantics + safe ref kind

# R15b: the cash-out confirm is a money mutation (debit driver wallet → credit tenant
# float). The debit leg already logs via wallet_service; route the float-credit leg's
# failures to the same dedicated "payments" channel so the whole settlement is
# rate-trackable. Messages carry schema + driver/tenant/request ids and only the
# NON-secret namespace of any reference (never the raw 6-digit cash-out code).
payments_logger = logging.getLogger("payments")


def _schema() -> str:
    """Best-effort current tenant schema for log attribution (never raises)."""
    try:
        return connection.schema_name
    except Exception:
        return "?"


def driver_earnings_summary(driver_id) -> dict:
    """Return {earned, paid, owed, ride_earned, rides_completed, earned_today, deliveries_today}
    for a driver, as quantised Decimals."""
    from django.utils import timezone as _tz
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

    # Today stats — delivery jobs delivered since midnight (server date).
    today_start = _tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_qs = DeliveryJob.objects.filter(
        driver_id=driver_id,
        status=DeliveryJob.Status.DELIVERED,
        delivered_at__gte=today_start,
    )
    earned_today_raw = today_qs.aggregate(s=Sum("driver_payout"))["s"] or Decimal("0")
    deliveries_today = today_qs.count()

    earned = _money(earned)
    paid = _money(paid)
    return {
        "earned": earned,
        "paid": paid,
        "owed": _money(earned - paid),
        "ride_earned": _money(ride_earned_raw),
        "rides_completed": rides_completed,
        "earned_today": _money(earned_today_raw),
        "deliveries_today": deliveries_today,
    }


@transaction.atomic
def record_driver_payout(driver_id, amount, *, method="cash", reference="", note="",
                         actor_user_id=None, idempotency_key=None, currency="MAD"):
    """Record a settlement paid to a driver. Idempotent; never pays more than owed."""
    from .models import Customer, DriverPayout

    amount = _money(amount)
    if amount <= 0:
        raise WalletError("payout amount must be positive")

    def _replay_or_reject(existing):
        # DriverPayout.idempotency_key is a GLOBAL unique column on the shared schema and the
        # key is caller-supplied, so a key that resolves to ANOTHER driver's payout is a
        # collision/attack, not a legit replay — refuse rather than hand back (and falsely
        # acknowledge) someone else's settlement. Mirrors the wallet_service collision guards.
        if existing.driver_id != int(driver_id):
            payments_logger.error(
                "driver payout idempotency-key collision schema=%s driver_id=%s key=%s",
                _schema(), driver_id, idempotency_key,
            )
            raise WalletError("idempotency key collision: belongs to another driver")
        return existing

    if idempotency_key:
        existing = DriverPayout.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return _replay_or_reject(existing)

    # MONEY-2: serialize concurrent settlements for THIS driver. `owed` = earned − sum(
    # payouts); without a lock two payouts can both read the same owed and both write,
    # paying out MORE than is owed (double-pay). Lock the driver row so a racer must commit
    # + release before we (re)compute owed — then owed reflects every already-recorded
    # payout. Mirrors the wallet service's select_for_update discipline.
    _locked = Customer.objects.select_for_update().filter(pk=driver_id).first()
    if _locked is None:
        # No row locked ⇒ the serialization mutex would be a silent no-op. The only prod
        # caller pre-checks existence, but fail closed so the service is self-defending.
        raise WalletError("driver not found")

    # Re-check idempotency under the lock: a concurrent same-key request may have committed
    # its payout while we waited for the row lock — replay it instead of racing a second
    # insert that would 500 on the unique idempotency_key.
    if idempotency_key:
        existing = DriverPayout.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return _replay_or_reject(existing)

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
    # Lock the driver's row so the "one live cash-out at a time" check + create are
    # ATOMIC. Without the lock, two concurrent requests (double-tap / two tabs) can
    # each pass the duplicate-pending check and mint two live codes against one
    # balance (TOCTOU) — two tenants could then each redeem before the wallet debits.
    with transaction.atomic():
        cust = Customer.objects.select_for_update().filter(pk=driver_id).first()
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
    from .verticals import DRIVER

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
            cache.add(fail_key, 0, CASHOUT_CONFIRM_LOCK_SECONDS)
            cache.incr(fail_key)
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
            reference=f"cashout:{req.id}",
            tenant_id=tenant_id,
            note="Driver cash-out",
            # Cash-out is a driver wallet op, not spend at this tenant's vertical —
            # tag DRIVER explicitly so auto-derive (tenant_id) doesn't mislabel it.
            vertical=DRIVER,
        )
        try:
            credit_tenant_float(
                tenant_id, req.amount,
                actor_user_id=actor_user_id,
                idempotency_key=f"cashout:{req.id}:f",
                reference=f"cashout:{req.id}",
                note="Driver cash-out reimbursement",
            )
        except Exception:
            # R15b: the driver wallet was already debited (wallet_service logged that leg);
            # a failure crediting the tenant float here (e.g. InactiveTenant/WalletError)
            # rolls back the whole atomic block but emitted NOTHING on the payments channel.
            # Log the float-credit-leg failure with attributable ids — reuse _ref_kind so
            # only the "cashout" namespace is recorded, NEVER the raw cash-out code — then
            # re-raise so control flow / rollback is unchanged.
            payments_logger.exception(
                "cashout float-credit leg failed schema=%s driver_id=%s tenant_id=%s "
                "request_id=%s ref_kind=%s",
                _schema(), req.driver_id, tenant_id, req.id, _ref_kind(f"cashout:{code}"),
            )
            raise
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
