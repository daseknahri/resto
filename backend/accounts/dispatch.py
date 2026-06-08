"""Ranked-offer delivery dispatch — the brain of the driver-assignment loop.

Instead of broadcasting every new job to every online driver and letting the
fastest tap win (which favours whoever is staring at the app, not the best
driver), we **offer each job to the nearest free driver first**, privately, for a
short window. If they decline or the window lapses, we cascade to the next
nearest, and so on. When the cascade is exhausted (or we can't rank anyone — no
fresh GPS, no pickup point), the job falls back to an **open pool** that any free
online driver can claim — the original behaviour, kept as a guaranteed safety net
so an order is never stranded.

This mirrors how mature platforms (Uber/inDrive/Glovo) dispatch: a ranked,
time-boxed offer cascade with a broadcast fallback and a manual/owner escape
hatch (the owner can re-dispatch from their dashboard).

State lives on ``DeliveryJob``:
    offered_to / offer_expires_at  — the current exclusive offer + its deadline
    declined_by (JSON list)        — driver ids who declined or timed out
    offer_round                    — cascade depth (bounds the loop; audit)
    is_open_pool                   — True once it falls back to broadcast

All mutations are row-locked; pushes happen after commit and never raise.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

# How long a single exclusive offer stays with one driver before it lapses.
OFFER_TTL_SECONDS = 60
# Most drivers to offer privately before opening the job to the whole pool.
MAX_OFFER_ROUNDS = 6
# A driver's GPS must be at least this fresh to be ranked for an exclusive offer.
# Staler than this → they can't be ranked, but they can still grab from the pool.
POSITION_FRESH_SECONDS = 300


def _tenant_name(tenant_id) -> str:
    try:
        from tenancy.models import Tenant
        t = Tenant.objects.filter(id=tenant_id).first()
        return (t.name if t else "") or ""
    except Exception:
        return ""


def pick_nearest_driver(job, exclude_ids):
    """The closest free, approved, online driver with a fresh GPS fix to the
    pickup point — or None when nobody is rankable (→ caller opens the pool).

    "Free" = no active (assigned/at_restaurant/picked_up) job. ``exclude_ids`` are
    drivers who already declined/timed-out this job.
    """
    from tenancy.delivery_pricing import haversine_km, valid_coord
    from .models import Customer, DeliveryJob

    if not valid_coord(getattr(job, "pickup_lat", None), getattr(job, "pickup_lng", None)):
        return None

    fresh_since = timezone.now() - timedelta(seconds=POSITION_FRESH_SECONDS)
    candidates = list(
        Customer.objects.filter(
            is_driver=True,
            driver_approved=True,
            is_driver_online=True,
            driver_position_updated_at__gte=fresh_since,
            driver_lat__isnull=False,
            driver_lng__isnull=False,
        ).exclude(id__in=list(exclude_ids or []))
    )
    if not candidates:
        return None

    busy = set(
        DeliveryJob.objects.filter(
            driver_id__in=[c.id for c in candidates],
            status__in=DeliveryJob.ACTIVE_STATUSES,
        ).values_list("driver_id", flat=True)
    )

    best, best_km = None, None
    for c in candidates:
        if c.id in busy or not valid_coord(c.driver_lat, c.driver_lng):
            continue
        km = haversine_km(job.pickup_lat, job.pickup_lng, c.driver_lat, c.driver_lng)
        if best is None or km < best_km:
            best, best_km = c, km
    return best


def _do_push(action, tenant_id):
    """Run the push decided under lock (after commit). Never raises."""
    try:
        if action is None:
            return
        kind = action[0]
        name = _tenant_name(tenant_id)
        if kind == "broadcast":
            from .push import push_new_job_to_drivers
            push_new_job_to_drivers(name)
        elif kind == "offer":
            from .push import push_job_offer_to_driver
            push_job_offer_to_driver(action[1], name)
    except Exception:
        pass


def offer_to_next_driver(job_id):
    """Offer a SEARCHING job to the next-nearest free driver, or open the pool.

    Row-locked. A no-op unless the job is still SEARCHING. Returns the chosen
    Customer (exclusive offer) or None (opened to the pool / nothing to do).
    Sends the appropriate push after commit.
    """
    from .models import DeliveryJob

    action = None
    tenant_id = None
    chosen = None
    with transaction.atomic():
        job = DeliveryJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.status != DeliveryJob.Status.SEARCHING:
            return None
        tenant_id = job.tenant_id
        exclude = set(job.declined_by or [])
        driver = None
        if (job.offer_round or 0) < MAX_OFFER_ROUNDS:
            driver = pick_nearest_driver(job, exclude)

        if driver is None:
            # Cascade exhausted / nobody rankable → fall back to the open pool.
            job.offered_to = None
            job.offer_expires_at = None
            job.is_open_pool = True
            job.save(update_fields=["offered_to", "offer_expires_at", "is_open_pool"])
            action = ("broadcast",)
        else:
            job.offered_to = driver
            job.offer_expires_at = timezone.now() + timedelta(seconds=OFFER_TTL_SECONDS)
            job.offer_round = (job.offer_round or 0) + 1
            job.is_open_pool = False
            job.save(update_fields=["offered_to", "offer_expires_at", "offer_round", "is_open_pool"])
            action = ("offer", driver.id)
            chosen = driver

    _do_push(action, tenant_id)
    return chosen


def start_dispatch(job):
    """Kick off dispatch for a freshly created/re-opened job (offer round 0)."""
    return offer_to_next_driver(job.id if hasattr(job, "id") else job)


def decline_offer(job_id, driver_id):
    """Driver declines their exclusive offer → record it and cascade to the next.

    A no-op (returns the job) when the offer isn't this driver's. Returns the
    result of the next offer otherwise.
    """
    from .models import DeliveryJob

    with transaction.atomic():
        job = DeliveryJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.status != DeliveryJob.Status.SEARCHING:
            return None
        if job.offered_to_id != driver_id:
            return job  # not your offer (already cascaded / open pool) — ignore
        declined = list(job.declined_by or [])
        if driver_id not in declined:
            declined.append(driver_id)
        job.declined_by = declined
        job.offered_to = None
        job.offer_expires_at = None
        job.save(update_fields=["declined_by", "offered_to", "offer_expires_at"])

    return offer_to_next_driver(job_id)


def expire_and_cascade_stale_offers():
    """Advance exclusive offers whose window lapsed (driver ignored it). Treats
    the lapse as a decline and cascades. Returns the number advanced. Called by
    the stale-job sweep.
    """
    from .models import DeliveryJob

    now = timezone.now()
    stale = list(
        DeliveryJob.objects.filter(
            status=DeliveryJob.Status.SEARCHING,
            is_open_pool=False,
            offered_to__isnull=False,
            offer_expires_at__lte=now,
        ).values_list("id", "offered_to_id")
    )
    advanced = 0
    for job_id, drv_id in stale:
        try:
            with transaction.atomic():
                job = DeliveryJob.objects.select_for_update().filter(pk=job_id).first()
                if (
                    job is None
                    or job.status != DeliveryJob.Status.SEARCHING
                    or job.is_open_pool
                    or job.offered_to_id != drv_id
                    or job.offer_expires_at is None
                    or job.offer_expires_at > now
                ):
                    continue  # changed between scan and lock
                declined = list(job.declined_by or [])
                if drv_id is not None and drv_id not in declined:
                    declined.append(drv_id)
                job.declined_by = declined
                job.offered_to = None
                job.offer_expires_at = None
                job.save(update_fields=["declined_by", "offered_to", "offer_expires_at"])
            offer_to_next_driver(job_id)
            advanced += 1
        except Exception:
            continue
    return advanced
