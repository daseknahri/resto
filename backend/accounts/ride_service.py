"""Ride-hailing fare estimation and settlement.

Mirrors delivery_pricing.py conventions but for ride-hailing: uses the road-distance
seam (tenancy.routing.road_distance_km) for the effective distance, then applies
platform-wide fare config from PlatformConfig.

  estimate_ride(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
      -> {"distance_km": float, "fare": Decimal}
      raises ValueError for bad/implausible coordinates.

  settle_ride(ride)
      Called inside a completion transaction. Wallet rides: debit rider, credit driver.
      Insufficient-balance falls back to cash (driver collects). Cash rides: no movement.

Module-level imports of the seams we mock in tests (so @patch("accounts.ride_service.X") works).
"""
from decimal import Decimal, ROUND_HALF_UP

from tenancy.delivery_pricing import valid_coord, MAX_PLAUSIBLE_KM
from tenancy.routing import road_distance_km
from .models import PlatformConfig, WalletTransaction
from .wallet_service import debit_wallet, credit_wallet, InsufficientFunds

_CENT = Decimal("0.01")

AVG_CITY_SPEED_KMH = 24  # used to estimate trip duration for the per-minute fare component


def _dec(value) -> Decimal:
    try:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def estimate_ride(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng) -> dict:
    """Estimate ride fare.

    Returns {"distance_km": float, "fare": Decimal, "duration_min": int}.
    Raises ValueError for bad or implausible coordinates.

    UPFRONT/FIXED quote: the returned fare is locked in at ride creation.
    Completion never recomputes — settle_ride uses the stored ride.fare.

    Per-minute component:
        est_minutes = round(dist_km / AVG_CITY_SPEED_KMH * 60)
        When ride_per_minute == 0 the component is zero (fully backward compatible).
    """
    if not valid_coord(pickup_lat, pickup_lng):
        raise ValueError("invalid pickup coordinates")
    if not valid_coord(dropoff_lat, dropoff_lng):
        raise ValueError("invalid dropoff coordinates")

    dist_km = road_distance_km(
        float(pickup_lat), float(pickup_lng),
        float(dropoff_lat), float(dropoff_lng),
    )
    if dist_km <= 0 or dist_km > MAX_PLAUSIBLE_KM:
        raise ValueError(
            f"implausible ride distance ({dist_km:.1f} km); maximum is {MAX_PLAUSIBLE_KM} km"
        )

    cfg = PlatformConfig.get_solo()
    base = _dec(cfg.ride_base_fare)
    per_km = _dec(cfg.ride_per_km)
    per_minute = _dec(cfg.ride_per_minute)
    minimum = _dec(cfg.ride_minimum_fare)

    est_minutes = int(round(dist_km / AVG_CITY_SPEED_KMH * 60))
    raw = (
        base
        + per_km * Decimal(str(round(dist_km, 4)))
        + per_minute * Decimal(str(est_minutes))
    )
    fare = max(minimum, raw).quantize(_CENT, rounding=ROUND_HALF_UP)

    return {"distance_km": dist_km, "fare": fare, "duration_min": est_minutes}


def settle_ride(ride) -> None:
    """Settle payment for a completed ride (call inside the completion transaction).

    Wallet rides:
        - Debit rider's wallet (idempotency_key f"ride:{ride.id}").
        - On InsufficientFunds flip to cash (driver collects) and return.
        - On success set paid_with_wallet=True and credit driver wallet
          (idempotency_key f"ridepay:{ride.id}").
    Cash rides:
        - No wallet movement.

    Raises on unexpected errors so the caller's atomic() block rolls back the
    entire completion, preventing a partial-settlement where the rider is
    debited but the driver receives nothing.
    """
    _do_settle(ride)


def _do_settle(ride) -> None:
    if ride.payment_method != "wallet":
        return  # cash — driver collects, nothing to do

    fare = _dec(ride.fare)
    if fare <= 0:
        return

    # Debit rider
    try:
        debit_wallet(
            ride.rider_id,
            fare,
            tx_type=WalletTransaction.Type.PAYMENT,
            idempotency_key=f"ride:{ride.id}",
            note=f"Ride #{ride.id}",
        )
    except InsufficientFunds:
        # Flip to cash — driver will collect from passenger.
        # Mutate in memory only; the outer atomic transaction saves once.
        ride.payment_method = "cash"
        return
    except Exception:
        raise

    # Mutate in memory only; the outer atomic transaction saves once.
    ride.paid_with_wallet = True

    # Credit driver (minus commission)
    if not getattr(ride, "driver_id", None):
        return

    cfg = PlatformConfig.get_solo()
    commission_pct = _dec(cfg.ride_commission_pct)
    driver_amount = (fare * (1 - commission_pct / Decimal("100"))).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    if driver_amount <= 0:
        return

    credit_wallet(
        ride.driver_id,
        driver_amount,
        tx_type=WalletTransaction.Type.TOPUP,
        idempotency_key=f"ridepay:{ride.id}",
        note=f"Ride #{ride.id} earnings",
        require_verified=False,
    )
