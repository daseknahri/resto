"""Ride-hailing / courier API views.

All ride and package-delivery views live here for reviewability. Wired into
config/shared_api_urls.py next to the driver block.

Rider endpoints (session customer_id):
    POST   /api/rides/estimate/           — fare estimate (throttled)
    POST   /api/rides/                    — create ride or package trip (SEARCHING or SCHEDULED)
    GET    /api/rides/active/             — rider's active/recent trip + upcoming scheduled list
    GET    /api/rides/history/            — rider's last 20 terminal trips
    POST   /api/rides/<id>/cancel/        — rider cancels (including SCHEDULED)
    POST   /api/rides/<id>/rate/          — rider rates driver (1-5)

Driver endpoints (is_driver + driver_approved):
    GET    /api/driver/rides/             — open SEARCHING trips + own active + last_completed
    GET    /api/driver/rides/history/     — driver's last 20 completed/cancelled trips
    POST   /api/driver/rides/<id>/accept/ — first-accept-wins
    POST   /api/driver/rides/<id>/status/ — advance status
    POST   /api/driver/docs/             — upload licence or insurance doc
    POST   /api/driver/rides/<id>/rate/  — driver rates rider (1-5)

Admin endpoints (IsPlatformAdmin):
    GET    /api/admin/rides/              — latest 50 trips, optional ?status= filter
    POST   /api/admin/drivers/<id>/car-approve/ — approve car docs
    POST   /api/admin/drivers/<id>/car-reject/  — reject car docs

Dispatch rules by kind:
    ride    → online + approved CAR drivers with driver_car_approved=True.
    package → ALL online + approved drivers regardless of vehicle type or car docs.

Fare model for packages is shared with rides (MVP decision: same base/km/min rates).
"""
from django.db import transaction as _tx
from django.utils import timezone as _tz
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.delivery_pricing import haversine_km, valid_coord

from .models import Customer, RideRequest
from .push import push_new_ride_to_drivers, push_ride_event_to_rider
from .throttles import (
    AdminPIIThrottle,
    DriverDocUploadThrottle,
    RideEstimateThrottle,
    RideRequestThrottle,
    RideDriverThrottle,
    DriverJobAcceptThrottle,
    DriverStatusUpdateThrottle,
)
from sales.permissions import IsPlatformAdmin


# ── Serialiser helper ─────────────────────────────────────────────────────────────

def _ts(dt):
    return dt.isoformat() if dt else None


def _generate_package_code() -> str:
    """Return a 6-digit zero-padded random string for package handover proof."""
    import secrets
    return str(secrets.randbelow(1_000_000)).zfill(6)


def _serialize_ride(ride, *, include_driver_pii=False, include_delivery_code=False):
    """Serialize a RideRequest.

    include_driver_pii     — expose driver phone + GPS (own active trip only).
    include_delivery_code  — expose the package handover code (rider's own trip only;
                             NEVER set this for driver offer/active payloads or admin).
    """
    driver = None
    if ride.driver_id:
        drv = ride.driver
        driver = {
            "name": drv.name or "",
            "phone": drv.phone if include_driver_pii else None,
            "driver_vehicle": drv.driver_vehicle or "",
            "driver_lat": drv.driver_lat if include_driver_pii else None,
            "driver_lng": drv.driver_lng if include_driver_pii else None,
            "driver_position_updated_at": _ts(drv.driver_position_updated_at) if include_driver_pii else None,
        }
    data = {
        "id": ride.id,
        "kind": ride.kind,
        "status": ride.status,
        "fare": str(ride.fare),
        "distance_km": ride.distance_km,
        "pickup_address": ride.pickup_address,
        "dropoff_address": ride.dropoff_address,
        "pickup_lat": ride.pickup_lat,
        "pickup_lng": ride.pickup_lng,
        "dropoff_lat": ride.dropoff_lat,
        "dropoff_lng": ride.dropoff_lng,
        "payment_method": ride.payment_method,
        "paid_with_wallet": ride.paid_with_wallet,
        "scheduled_for": _ts(ride.scheduled_for),
        "dispatched_at": _ts(ride.dispatched_at),
        "created_at": _ts(ride.created_at),
        "accepted_at": _ts(ride.accepted_at),
        "arrived_at": _ts(ride.arrived_at),
        "started_at": _ts(ride.started_at),
        "completed_at": _ts(ride.completed_at),
        "cancelled_at": _ts(ride.cancelled_at),
        "rider_driver_rating": ride.rider_driver_rating,
        "driver_rider_rating": ride.driver_rider_rating,
        "driver": driver,
        # Package-specific fields (always present; empty string for rides)
        "recipient_name": ride.recipient_name or "",
        "package_note": ride.package_note or "",
        # recipient_phone: always included. This is recipient PII provided by the rider
        # (they own it), not driver PII, so it must not be gated by include_driver_pii.
        # The driver receives it via their own-trip serialization (include_driver_pii=True),
        # and the rider always sees it on their own trip regardless of status.
        "recipient_phone": ride.recipient_phone or "",
    }
    # Handover code: only when the caller explicitly opts in (rider's own trip only).
    # NEVER included in driver offer lists, driver active-trip, or admin payloads.
    if include_delivery_code and ride.kind == RideRequest.Kind.PACKAGE:
        data["delivery_code"] = getattr(ride, "delivery_code", "") or ""
    return data


# ── Auth helpers ──────────────────────────────────────────────────────────────────

def _get_rider(request):
    """Return (Customer, None) or (None, error Response)."""
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return None, Response(
            {"detail": "Customer session required."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        return Customer.objects.get(pk=customer_id), None
    except Customer.DoesNotExist:
        return None, Response(
            {"detail": "Customer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _get_driver(request):
    """Return (Customer, None) or (None, error Response). Driver must be approved + online."""
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return None, Response(
            {"detail": "Customer session required."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        drv = Customer.objects.get(
            pk=customer_id, is_driver=True, driver_approved=True, is_driver_online=True,
        )
        return drv, None
    except Customer.DoesNotExist:
        return None, Response(
            {"detail": "Driver must be approved and online."},
            status=status.HTTP_403_FORBIDDEN,
        )


def _parse_float(value, label):
    """Return (float, None) or (None, error str)."""
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"{label} must be a number"


# ── Rider views ───────────────────────────────────────────────────────────────────


class RideEstimateView(APIView):
    """POST /api/rides/estimate/ — returns {distance_km, fare} or 400."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideEstimateThrottle]

    def post(self, request, *args, **kwargs):
        from .ride_service import estimate_ride

        for field in ("pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"):
            if request.data.get(field) is None:
                return Response(
                    {"detail": f"{field} is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = estimate_ride(
                request.data["pickup_lat"],
                request.data["pickup_lng"],
                request.data["dropoff_lat"],
                request.data["dropoff_lng"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "distance_km": result["distance_km"],
            "fare": str(result["fare"]),
            "duration_min": result["duration_min"],
        })


class RideCreateView(APIView):
    """POST /api/rides/ — create a ride or package trip (SEARCHING or SCHEDULED).

    Body (ride):    kind='ride' (default), pickup/dropoff coords + addresses, payment_method.
                    Optional: scheduled_for (ISO 8601, tz-aware or UTC assumed).
    Body (package): kind='package', above + recipient_name (required), recipient_phone (required),
                    package_note (optional, ≤200 chars).

    Fare model is shared between rides and packages (MVP decision — same base/km/min rates).

    Scheduling rules:
        scheduled_for absent/null → immediate trip (status=SEARCHING, dispatched_at=now()).
        scheduled_for present     → future trip (status=SCHEDULED, dispatched_at=None,
                                    no driver push at create time).
        Validation: scheduled_for must be >= now+20min (400 "too_soon") and
                    <= now+7days (400 "too_far").
        Cap: max 3 non-terminal SCHEDULED trips per rider (409 "too_many_scheduled").
        Active-trip guard (one non-terminal non-scheduled trip) still applies;
        SCHEDULED trips are excluded from that guard so a rider with a future trip
        can still request an immediate one.

    Dispatch after create:
        ride    → online approved CAR drivers with driver_car_approved (existing behaviour).
        package → ALL online approved drivers, any vehicle type, no car-doc requirement.
        (Scheduled trips: no dispatch at create; sweep_ride_requests rule (d) releases them.)
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideRequestThrottle]

    def post(self, request, *args, **kwargs):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils.dateparse import parse_datetime
        from .ride_service import estimate_ride

        rider, err = _get_rider(request)
        if err:
            return err

        # Resolve kind — reject unknown values rather than silently coercing,
        # so client typos and future kinds surface instead of becoming rides.
        kind = (request.data.get("kind") or "ride").strip().lower()
        if kind not in ("ride", "package"):
            return Response(
                {"detail": "kind must be 'ride' or 'package'.", "code": "bad_kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate required geo fields
        for field in ("pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"):
            if request.data.get(field) is None:
                return Response(
                    {"detail": f"{field} is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Package-specific required fields
        recipient_name = ""
        recipient_phone = ""
        package_note = ""
        if kind == "package":
            recipient_name = str(request.data.get("recipient_name") or "").strip()
            recipient_phone = str(request.data.get("recipient_phone") or "").strip()
            if not recipient_name:
                return Response(
                    {"detail": "recipient_name is required for package trips.", "code": "missing_field"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not recipient_phone:
                return Response(
                    {"detail": "recipient_phone is required for package trips.", "code": "missing_field"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            package_note = str(request.data.get("package_note") or "").strip()[:200]

        # Parse optional scheduled_for
        scheduled_for = None
        raw_sf = request.data.get("scheduled_for")
        if raw_sf:
            dt = parse_datetime(str(raw_sf))
            if dt is None:
                return Response(
                    {"detail": "scheduled_for must be a valid ISO 8601 datetime.", "code": "bad_scheduled_for"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Make timezone-aware (assume UTC if naive)
            if _tz.is_naive(dt):
                dt = _tz.make_aware(dt, _tz.utc)
            now_sf = _tz.now()
            if dt < now_sf + timedelta(minutes=20):
                return Response(
                    {"detail": "scheduled_for must be at least 20 minutes from now.", "code": "too_soon"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if dt > now_sf + timedelta(days=7):
                return Response(
                    {"detail": "scheduled_for must be within 7 days from now.", "code": "too_far"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            scheduled_for = dt

        try:
            result = estimate_ride(
                request.data["pickup_lat"],
                request.data["pickup_lng"],
                request.data["dropoff_lat"],
                request.data["dropoff_lng"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payment_method = request.data.get("payment_method", "wallet")
        if payment_method not in ("wallet", "cash"):
            payment_method = "wallet"

        fare = result["fare"]

        # Wallet method requires sufficient balance
        if payment_method == "wallet":
            from decimal import Decimal as _Dec
            balance = _Dec(str(rider.wallet_balance or "0"))
            if balance < fare:
                return Response(
                    {
                        "detail": "Insufficient wallet balance for this ride.",
                        "code": "insufficient_wallet",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        now = _tz.now()

        with _tx.atomic():
            # Lock the rider row to prevent concurrent double-submission (TOCTOU guard)
            Customer.objects.select_for_update().filter(pk=rider.id).first()

            # Guard: one non-terminal, non-scheduled trip per rider.
            # SCHEDULED trips are excluded: a rider with a future scheduled trip can still
            # book an immediate trip now.
            if RideRequest.objects.filter(
                rider=rider,
            ).exclude(
                status__in=RideRequest.TERMINAL_STATUSES | {RideRequest.Status.SCHEDULED}
            ).exists():
                return Response(
                    {"detail": "You already have an active ride.", "code": "active_ride_exists"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Cap: max 3 non-terminal SCHEDULED trips per rider.
            if scheduled_for is not None:
                scheduled_count = RideRequest.objects.filter(
                    rider=rider,
                    status=RideRequest.Status.SCHEDULED,
                ).count()
                if scheduled_count >= 3:
                    return Response(
                        {"detail": "You cannot have more than 3 upcoming scheduled trips.", "code": "too_many_scheduled"},
                        status=status.HTTP_409_CONFLICT,
                    )

            # Determine initial status and dispatched_at
            if scheduled_for is not None:
                initial_status = RideRequest.Status.SCHEDULED
                dispatched_at = None
            else:
                initial_status = RideRequest.Status.SEARCHING
                dispatched_at = now

            ride = RideRequest.objects.create(
                rider=rider,
                kind=kind,
                pickup_lat=float(request.data["pickup_lat"]),
                pickup_lng=float(request.data["pickup_lng"]),
                dropoff_lat=float(request.data["dropoff_lat"]),
                dropoff_lng=float(request.data["dropoff_lng"]),
                pickup_address=str(request.data.get("pickup_address") or "")[:255],
                dropoff_address=str(request.data.get("dropoff_address") or "")[:255],
                distance_km=result["distance_km"],
                fare=fare,
                payment_method=payment_method,
                status=initial_status,
                scheduled_for=scheduled_for,
                dispatched_at=dispatched_at,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                package_note=package_note,
                # Generate handover code for packages; rides get an empty string.
                delivery_code=_generate_package_code() if kind == "package" else "",
            )

        # Dispatch: only for immediate trips (scheduled trips wait for sweep rule d).
        # package → all approved drivers; ride → car drivers only (existing helper).
        if scheduled_for is None:
            try:
                push_new_ride_to_drivers(ride.id)
            except Exception:
                pass

        return Response(_serialize_ride(ride), status=status.HTTP_201_CREATED)


class RideActiveView(APIView):
    """GET /api/rides/active/ — rider's current non-terminal ride (or latest completed within 10 min).

    Response shape:
        {
            "ride": <serialized active/recent trip or null>,
            "scheduled": [<up to 3 upcoming SCHEDULED trips, soonest first>]
        }

    "ride" excludes SCHEDULED status — a scheduled trip in the future is not the active trip.
    "scheduled" always contains the rider's upcoming scheduled trips (max 3, soonest first).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from datetime import timedelta
        rider, err = _get_rider(request)
        if err:
            return err

        # Current active trip: non-terminal and NOT scheduled
        ride = (
            RideRequest.objects.filter(rider=rider)
            .exclude(status__in=RideRequest.TERMINAL_STATUSES | {RideRequest.Status.SCHEDULED})
            .select_related("driver")
            .order_by("-created_at")
            .first()
        )
        if ride is None:
            # Fall back to completed within the last 10 minutes (rating window)
            cutoff = _tz.now() - timedelta(minutes=10)
            ride = (
                RideRequest.objects.filter(
                    rider=rider,
                    status=RideRequest.Status.COMPLETED,
                    completed_at__gte=cutoff,
                )
                .select_related("driver")
                .order_by("-completed_at")
                .first()
            )

        # Upcoming scheduled trips (soonest first, max 3)
        scheduled_qs = (
            RideRequest.objects.filter(
                rider=rider,
                status=RideRequest.Status.SCHEDULED,
            )
            .order_by("scheduled_for")[:3]
        )
        scheduled_list = [_serialize_ride(r) for r in scheduled_qs]

        ride_data = None
        if ride is not None:
            # PII (driver phone + GPS) only revealed after driver is accepted.
            # Handover code: always shown to the rider on their own active trip so
            # they can share it with the recipient (it is absent from driver payloads).
            pii_ok = ride.status not in (RideRequest.Status.SEARCHING,)
            ride_data = _serialize_ride(
                ride, include_driver_pii=pii_ok, include_delivery_code=True
            )

        return Response({"ride": ride_data, "scheduled": scheduled_list})


class RideCancelView(APIView):
    """POST /api/rides/<id>/cancel/ — rider cancels (searching or accepted only)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideRequestThrottle]

    def post(self, request, ride_id, *args, **kwargs):
        rider, err = _get_rider(request)
        if err:
            return err

        now = _tz.now()
        with _tx.atomic():
            try:
                ride = RideRequest.objects.select_for_update().get(
                    pk=ride_id, rider=rider
                )
            except RideRequest.DoesNotExist:
                return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

            if ride.status not in ("scheduled", "searching", "accepted"):
                return Response(
                    {
                        "detail": f"Cannot cancel a ride in status '{ride.status}'.",
                        "allowed": ["scheduled", "searching", "accepted"],
                        "code": "bad_transition",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            driver_id = ride.driver_id
            ride.status = RideRequest.Status.CANCELLED
            ride.cancelled_at = now
            ride.save(update_fields=["status", "cancelled_at"])

        # Notify assigned driver (best-effort; scheduled trips have no driver)
        if driver_id:
            try:
                from django_tenants.utils import schema_context
                from menu.push import _send_one
                from .models import CustomerPushSubscription
                with schema_context("public"):
                    subs = list(CustomerPushSubscription.objects.filter(customer_id=driver_id))
                for s in subs:
                    _send_one(s.endpoint, s.p256dh, s.auth, "Ride cancelled", "The rider cancelled the ride.", "/driver")
            except Exception:
                pass

        return Response(_serialize_ride(ride))


class RideRateView(APIView):
    """POST /api/rides/<id>/rate/ — rider rates the driver (1-5, once)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideRequestThrottle]

    def post(self, request, ride_id, *args, **kwargs):
        rider, err = _get_rider(request)
        if err:
            return err

        try:
            rating = int(request.data.get("rating", 0))
        except (TypeError, ValueError):
            rating = 0
        if rating < 1 or rating > 5:
            return Response(
                {"detail": "Rating must be an integer between 1 and 5."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with _tx.atomic():
            try:
                ride = RideRequest.objects.select_for_update().get(pk=ride_id, rider=rider)
            except RideRequest.DoesNotExist:
                return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

            if ride.status != RideRequest.Status.COMPLETED:
                return Response(
                    {"detail": "Can only rate a completed ride.", "code": "not_completed"},
                    status=status.HTTP_409_CONFLICT,
                )
            if ride.rider_driver_rating is not None:
                return Response(
                    {"detail": "You have already rated this ride.", "code": "already_rated"},
                    status=status.HTTP_409_CONFLICT,
                )

            ride.rider_driver_rating = rating
            ride.save(update_fields=["rider_driver_rating"])

        return Response({"ok": True, "rating": rating})


# ── Driver views ──────────────────────────────────────────────────────────────────


class DriverRideListView(APIView):
    """GET /api/driver/rides/ — open SEARCHING trips + own active trip + last_completed.

    Offer visibility rules by kind:
        package — visible to EVERY online approved driver (any vehicle type, no car docs needed).
        ride    — visible only to car drivers with driver_car_approved=True (existing behaviour).

    Own active trip is always returned regardless of kind so an in-progress trip is never stranded.
    last_completed: driver's most recent COMPLETED trip within the 10-min rating window so the SPA
    can show the rate prompt.

    PII note: recipient_phone is NOT included in open offer items (it is only present on the
    driver's own active trip via _serialize_ride with include_driver_pii=True).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideDriverThrottle]

    def get(self, request, *args, **kwargs):
        driver, err = _get_driver(request)
        if err:
            return err

        # Own active trip (any non-terminal trip assigned to this driver)
        own_ride = (
            RideRequest.objects.filter(driver=driver)
            # SCHEDULED trips have no driver by design; exclude explicitly so a
            # data anomaly can never surface one as the driver's active trip.
            .exclude(status__in=[*RideRequest.TERMINAL_STATUSES, RideRequest.Status.SCHEDULED])
            .select_related("rider")
            .order_by("-created_at")
            .first()
        )

        # Last completed trip within 10-minute rating window
        last_completed = None
        from datetime import timedelta
        cutoff = _tz.now() - timedelta(minutes=10)
        lc_ride = (
            RideRequest.objects.filter(
                driver=driver,
                status=RideRequest.Status.COMPLETED,
                completed_at__gte=cutoff,
            )
            .order_by("-completed_at")
            .first()
        )
        if lc_ride:
            last_completed = {
                "id": lc_ride.id,
                "kind": lc_ride.kind,
                "fare": str(lc_ride.fare),
                "payment_method": lc_ride.payment_method,
                "paid_with_wallet": lc_ride.paid_with_wallet,
                "driver_rider_rating": lc_ride.driver_rider_rating,
            }

        # Determine which kinds this driver is eligible to see as open offers.
        # package: all approved online drivers (no vehicle-type or car-doc restriction).
        # ride:    only car drivers with driver_car_approved.
        is_car_approved = (
            driver.driver_vehicle_type == Customer.VEHICLE_TYPE_CAR
            and driver.driver_car_approved
        )

        # Build a DB-level kind filter so the [:40] cap is applied only to trips this
        # driver can actually accept. Without this, a high-volume moment where all 40
        # newest trips are 'ride' trips would leave a motorbike driver with zero package
        # offers even when older package trips are SEARCHING.
        from django.db.models import Q
        if is_car_approved:
            # Car-approved: see both rides and packages
            kind_filter = Q(kind=RideRequest.Kind.RIDE) | Q(kind=RideRequest.Kind.PACKAGE)
        else:
            # Non-car-approved: packages only
            kind_filter = Q(kind=RideRequest.Kind.PACKAGE)

        open_rides = []
        qs = list(
            RideRequest.objects.filter(status=RideRequest.Status.SEARCHING)
            .filter(kind_filter)
            .select_related("rider")[:40]
        )
        for r in qs:
            # Per-kind visibility gate (redundant after DB filter, kept as safety assertion)
            if r.kind == RideRequest.Kind.RIDE and not is_car_approved:
                continue  # ride offer: car+car_approved required
            # package offers: visible to all approved online drivers — no extra gate

            dist_to_pickup = None
            if valid_coord(driver.driver_lat, driver.driver_lng) and valid_coord(r.pickup_lat, r.pickup_lng):
                dist_to_pickup = round(
                    haversine_km(driver.driver_lat, driver.driver_lng, r.pickup_lat, r.pickup_lng), 2
                )
            data = {
                "id": r.id,
                "kind": r.kind,
                "pickup_address": r.pickup_address,
                "dropoff_address": r.dropoff_address,
                "pickup_lat": r.pickup_lat,
                "pickup_lng": r.pickup_lng,
                "dropoff_lat": r.dropoff_lat,
                "dropoff_lng": r.dropoff_lng,
                "distance_km": r.distance_km,
                "fare": str(r.fare),
                "payment_method": r.payment_method,
                "distance_to_pickup_km": dist_to_pickup,
                "created_at": _ts(r.created_at),
                # Package metadata visible on open offers (NOT recipient_phone — PII)
                "recipient_name": r.recipient_name if r.kind == RideRequest.Kind.PACKAGE else None,
                "package_note": r.package_note if r.kind == RideRequest.Kind.PACKAGE else None,
            }
            open_rides.append(data)

        return Response({
            "open_rides": open_rides,
            "active_ride": _serialize_ride(own_ride, include_driver_pii=True) if own_ride else None,
            "last_completed": last_completed,
        })


class DriverRideAcceptView(APIView):
    """POST /api/driver/rides/<id>/accept/ — first-accept-wins, atomic.

    Per-kind eligibility gate (mirrors DriverRideListView offer visibility):
        ride    — requires vehicle==car AND driver_car_approved.
        package — any approved online driver (no car-doc requirement).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverJobAcceptThrottle]

    def post(self, request, ride_id, *args, **kwargs):
        driver, err = _get_driver(request)
        if err:
            return err

        now = _tz.now()
        with _tx.atomic():
            # Lock driver row first (serialize concurrent accepts from same driver)
            Customer.objects.select_for_update().filter(pk=driver.id).first()

            # Check driver doesn't already have an active trip
            if RideRequest.objects.filter(
                driver=driver,
            ).exclude(status__in=RideRequest.TERMINAL_STATUSES).exists():
                return Response(
                    {"detail": "Complete your current ride before accepting a new one."},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                ride = RideRequest.objects.select_for_update().get(
                    pk=ride_id,
                    status=RideRequest.Status.SEARCHING,
                    driver__isnull=True,
                )
            except RideRequest.DoesNotExist:
                return Response(
                    {"detail": "Ride not available.", "code": "not_available"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Per-kind eligibility check (done inside the lock so the kind is authoritative)
            if ride.kind == RideRequest.Kind.RIDE:
                if driver.driver_vehicle_type != Customer.VEHICLE_TYPE_CAR:
                    return Response(
                        {"detail": "Only car drivers can accept ride requests."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if not driver.driver_car_approved:
                    return Response(
                        {"detail": "Car documents not yet approved.", "code": "car_not_approved"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            # kind=='package': no extra gate — any approved online driver may accept

            ride.driver = driver
            ride.status = RideRequest.Status.ACCEPTED
            ride.accepted_at = now
            ride.save(update_fields=["driver", "status", "accepted_at"])

        # Notify rider (best-effort, after commit)
        try:
            push_ride_event_to_rider(ride.rider_id, "accepted")
        except Exception:
            pass

        return Response(_serialize_ride(ride, include_driver_pii=True), status=status.HTTP_200_OK)


class DriverRideStatusView(APIView):
    """POST /api/driver/rides/<id>/status/ — driver advances ride status.

    Body: { "status": "arrived" | "in_progress" | "completed" | "searching" }
    "searching" from accepted/arrived = driver-abandon (clears driver, back to pool).

    Deliberately does NOT require is_driver_online: a driver who toggled offline
    mid-ride must still be able to advance/complete it — never strand a ride.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverStatusUpdateThrottle]

    def post(self, request, ride_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response(
                {"detail": "Customer session required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            driver = Customer.objects.get(pk=customer_id, is_driver=True, driver_approved=True)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Driver account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = (request.data.get("status") or "").strip()
        now = _tz.now()

        with _tx.atomic():
            try:
                ride = RideRequest.objects.select_for_update().get(pk=ride_id, driver=driver)
            except RideRequest.DoesNotExist:
                return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

            # Driver-abandon: return ride to the pool
            if new_status == "searching" and ride.status in ("accepted", "arrived"):
                ride.driver = None
                ride.status = RideRequest.Status.SEARCHING
                ride.accepted_at = None
                ride.arrived_at = None
                ride.save(update_fields=["driver", "status", "accepted_at", "arrived_at"])
                return Response(_serialize_ride(ride))

            allowed = set(RideRequest.VALID_TRANSITIONS.get(ride.status, set()))
            if new_status not in allowed:
                return Response(
                    {
                        "detail": f"Cannot transition from '{ride.status}' to '{new_status}'.",
                        "allowed": list(allowed),
                        "code": "bad_transition",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            update_fields = ["status"]
            ride.status = new_status

            if new_status == "arrived":
                ride.arrived_at = now
                update_fields.append("arrived_at")
            elif new_status == "in_progress":
                ride.started_at = now
                update_fields.append("started_at")
            elif new_status == "completed":
                # Package handover: driver must supply the 6-digit code the rider
                # shared with the recipient. Mirrors DeliveryJob's lockout pattern.
                if ride.kind == RideRequest.Kind.PACKAGE:
                    from datetime import timedelta as _td
                    _expected = getattr(ride, "delivery_code", "") or ""
                    if _expected:
                        if ride.code_locked_until and ride.code_locked_until > now:
                            return Response(
                                {"detail": "Too many incorrect codes — try again shortly.",
                                 "code": "code_locked"},
                                status=status.HTTP_429_TOO_MANY_REQUESTS,
                            )
                        _provided = str(request.data.get("code") or "").strip()
                        if _provided != _expected:
                            ride.code_attempts = (ride.code_attempts or 0) + 1
                            _f = ["code_attempts"]
                            if ride.code_attempts >= 5:
                                ride.code_locked_until = now + _td(minutes=5)
                                ride.code_attempts = 0
                                _f.append("code_locked_until")
                            ride.save(update_fields=_f)
                            return Response(
                                {"detail": "Incorrect handover code. Ask the recipient for the code.",
                                 "code": "bad_code"},
                                status=status.HTTP_409_CONFLICT,
                            )
                        # Correct code — reset lockout state
                        ride.code_attempts = 0
                        ride.code_locked_until = None
                        update_fields += ["code_attempts", "code_locked_until"]

                ride.completed_at = now
                update_fields.append("completed_at")
                # settle_ride runs INSIDE the transaction
                from .ride_service import settle_ride
                settle_ride(ride)
                # save may have updated payment_method/paid_with_wallet inside settle
                update_fields += ["payment_method", "paid_with_wallet"]

            ride.save(update_fields=update_fields)

        return Response(_serialize_ride(ride, include_driver_pii=True))


# ── Car-document upload ───────────────────────────────────────────────────────────

# Storage constants mirrored from tenancy.api.ImageUploadView
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
_BLOCKED_CT = {"image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}


def _save_driver_doc_image(upload, request) -> str:
    """Validate, optimise and save a driver document image.

    Reuses tenancy.api storage logic (default_storage / ContentFile) and the
    same content-type / size rules as ImageUploadView.  Returns the absolute URL.
    Raises ValueError with a user-visible message on validation failure.
    """
    import uuid
    from datetime import datetime
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    if upload is None:
        raise ValueError("Image file is required.")
    if upload.size > _MAX_UPLOAD_BYTES:
        raise ValueError("Image too large. Max size is 8MB.")
    ct = (upload.content_type or "").strip().lower()
    if not ct.startswith("image/"):
        raise ValueError("Only image uploads are allowed.")
    if ct in _BLOCKED_CT:
        raise ValueError("SVG and icon uploads are not permitted.")

    # OPS-5c item 1: transcode via Pillow; if it cannot decode the bytes the
    # image is untrustworthy (possible polyglot/corrupt upload) — reject with a
    # ValueError so the caller returns 400.  Do NOT fall back to raw bytes: that
    # would store and serve the file with the client-supplied content_type,
    # bypassing the only real sanitiser we have.
    try:
        from tenancy.api import _optimize_image
        data, ext, content_type, _ = _optimize_image(upload, variant="")
    except Exception:
        raise ValueError("Could not decode image. Upload a valid JPEG, PNG, WEBP, or GIF.")

    now = datetime.utcnow()
    rel_path = f"uploads/driver-docs/{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"
    saved = default_storage.save(rel_path, ContentFile(data))
    url = default_storage.url(saved)
    if url.startswith("/"):
        url = request.build_absolute_uri(url)
    return url


class DriverDocUploadView(APIView):
    """POST /api/driver/docs/ — upload a licence or insurance document image.

    Session: customer must have is_driver=True (driver_approved NOT required — drivers
    can submit docs before approval).  Multipart body:
        kind  — "licence" | "insurance"
        image — image file

    Stores the URL on the matching Customer field.  When BOTH urls are set after
    this upload, platform admins are notified (mirrors DriverRegisterView pattern).
    Submitting again replaces the doc and resets driver_car_approved=False.

    OPS-5c item 7: DriverDocUploadThrottle limits submissions per driver session
    (10/hour) — each upload is 8 MB and triggers an admin notification email.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [DriverDocUploadThrottle]

    def post(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response(
                {"detail": "Customer session required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            driver = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Driver account not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        kind = (request.data.get("kind") or "").strip().lower()
        if kind not in ("licence", "insurance"):
            return Response(
                {"detail": "kind must be 'licence' or 'insurance'.", "code": "bad_kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            url = _save_driver_doc_image(request.FILES.get("image"), request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        update_fields = ["driver_car_approved", "updated_at"]
        driver.driver_car_approved = False  # Reset on each new submission

        if kind == "licence":
            driver.driver_licence_url = url
            update_fields.append("driver_licence_url")
        else:
            driver.driver_insurance_url = url
            update_fields.append("driver_insurance_url")

        driver.save(update_fields=update_fields)

        # Notify admins when BOTH docs are now present (best-effort)
        if driver.driver_licence_url and driver.driver_insurance_url:
            try:
                _notify_admins_car_docs(driver)
            except Exception:
                pass

        return Response({
            "kind": kind,
            "url": url,
            "driver_car_approved": False,
            "driver_licence_url": driver.driver_licence_url or "",
            "driver_insurance_url": driver.driver_insurance_url or "",
        }, status=status.HTTP_200_OK)


def _notify_admins_car_docs(driver):
    """Best-effort notify platform admins that a driver has uploaded both car docs."""
    try:
        from django.db.models import Q
        from django.core.mail import send_mail as _send_mail
        from django.conf import settings as _cfg
        from .models import User
        from .notifications import record_notification

        admins = list(
            User.objects.filter(
                Q(is_platform_admin=True) | Q(is_superuser=True) | Q(is_staff=True)
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        name = driver.name or driver.phone or driver.email or f"Customer #{driver.id}"
        if admins:
            _send_mail(
                subject="Driver car documents ready for review — Kepoli",
                message=(
                    f"Driver {name} has uploaded both licence and insurance documents.\n\n"
                    "Please review and approve or reject their car verification in the admin console."
                ),
                from_email=_cfg.DEFAULT_FROM_EMAIL,
                recipient_list=admins,
                fail_silently=True,
            )
        record_notification(
            channel="email",
            event="driver_car_docs_uploaded",
            status="sent" if admins else "skipped",
            recipient=", ".join(admins)[:300],
            detail=f"Car docs submitted: {name}"[:300],
            reference=f"car_docs:{driver.id}",
        )
    except Exception:
        pass


# ── Driver rates rider ────────────────────────────────────────────────────────────


class DriverRateRideView(APIView):
    """POST /api/driver/rides/<id>/rate/ — driver rates the rider (1-5, once).

    Auth: session customer_id with is_driver=True + driver_approved=True.
    The driver must be the one assigned to this ride.
    Ride must be COMPLETED (409 otherwise).
    Once only — 409 if driver_rider_rating already set.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, ride_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response(
                {"detail": "Customer session required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            driver = Customer.objects.get(pk=customer_id, is_driver=True, driver_approved=True)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Approved driver account not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            rating = int(request.data.get("rating", 0))
        except (TypeError, ValueError):
            rating = 0
        if rating < 1 or rating > 5:
            return Response(
                {"detail": "Rating must be an integer between 1 and 5."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with _tx.atomic():
            try:
                ride = RideRequest.objects.select_for_update().get(pk=ride_id, driver=driver)
            except RideRequest.DoesNotExist:
                # Distinguish "not found" from "not assigned to this driver"
                if RideRequest.objects.filter(pk=ride_id).exists():
                    return Response(
                        {"detail": "You are not the assigned driver for this ride."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

            if ride.status != RideRequest.Status.COMPLETED:
                return Response(
                    {"detail": "Can only rate a completed ride.", "code": "not_completed"},
                    status=status.HTTP_409_CONFLICT,
                )
            if ride.driver_rider_rating is not None:
                return Response(
                    {"detail": "You have already rated this ride.", "code": "already_rated"},
                    status=status.HTTP_409_CONFLICT,
                )

            ride.driver_rider_rating = rating
            ride.save(update_fields=["driver_rider_rating"])

        return Response({"ok": True, "rating": rating})


# ── Rider history ─────────────────────────────────────────────────────────────────


class RideHistoryView(APIView):
    """GET /api/rides/history/ — session rider's last 20 terminal rides, newest-first.

    Fields: id, status, fare, payment_method, paid_with_wallet, pickup_address,
            dropoff_address, distance_km, created_at, completed_at,
            rider_driver_rating.
    No driver PII beyond driver name.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        rider, err = _get_rider(request)
        if err:
            return err

        rides = (
            RideRequest.objects.filter(
                rider=rider,
                status__in=RideRequest.TERMINAL_STATUSES,
            )
            .select_related("driver")
            .order_by("-created_at")[:20]
        )
        data = []
        for ride in rides:
            driver_name = None
            if ride.driver_id and ride.driver:
                driver_name = ride.driver.name or ""
            data.append({
                "id": ride.id,
                "kind": ride.kind,
                "status": ride.status,
                "fare": str(ride.fare),
                "payment_method": ride.payment_method,
                "paid_with_wallet": ride.paid_with_wallet,
                "pickup_address": ride.pickup_address,
                "dropoff_address": ride.dropoff_address,
                "distance_km": ride.distance_km,
                "created_at": _ts(ride.created_at),
                "completed_at": _ts(ride.completed_at),
                "rider_driver_rating": ride.rider_driver_rating,
                "driver_name": driver_name,
            })
        return Response(data)


# ── Driver history ─────────────────────────────────────────────────────────────────


class DriverRideHistoryView(APIView):
    """GET /api/driver/rides/history/ — session driver's last 20 completed/cancelled rides.

    Auth: is_driver=True + driver_approved=True (is_driver_online NOT required).
    Fields: id, status, fare, payment_method, paid_with_wallet, pickup_address,
            dropoff_address, distance_km, completed_at, driver_rider_rating.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response(
                {"detail": "Customer session required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            driver = Customer.objects.get(pk=customer_id, is_driver=True, driver_approved=True)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Approved driver account not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        rides = (
            RideRequest.objects.filter(
                driver=driver,
                status__in=RideRequest.TERMINAL_STATUSES,
            )
            .order_by("-created_at")[:20]
        )
        data = []
        for ride in rides:
            data.append({
                "id": ride.id,
                "kind": ride.kind,
                "status": ride.status,
                "fare": str(ride.fare),
                "payment_method": ride.payment_method,
                "paid_with_wallet": ride.paid_with_wallet,
                "pickup_address": ride.pickup_address,
                "dropoff_address": ride.dropoff_address,
                "distance_km": ride.distance_km,
                "completed_at": _ts(ride.completed_at),
                "driver_rider_rating": ride.driver_rider_rating,
            })
        return Response(data)


# ── Admin: ride oversight ──────────────────────────────────────────────────────────


class AdminRideListView(APIView):
    """GET /api/admin/rides/ — IsPlatformAdmin; latest 50 rides, optional ?status= filter.

    Fields per ride: id, status, fare, payment_method, paid_with_wallet,
                     distance_km, pickup_address, dropoff_address, created_at,
                     completed_at,
                     rider {id, name, phone},
                     driver {id, name, phone} (or null).

    OPS-5c item 2: restored to OPS-5/5b standard — IsPlatformAdmin permission
    class (DRF session auth + CSRF), AdminPIIThrottle, audit on GET.
    """

    permission_classes = [IsPlatformAdmin]
    throttle_classes = [AdminPIIThrottle]

    def get(self, request, *args, **kwargs):
        from sales.audit import log_admin_action
        from sales.models import AdminAuditLog

        log_admin_action(
            action=AdminAuditLog.Actions.RIDE_PII_VIEWED,
            request=request,
            target_repr="admin:ride_list",
            metadata={"filter": request.query_params.get("status", "")},
        )

        qs = RideRequest.objects.select_related("rider", "driver").order_by("-created_at")
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            valid_statuses = [s.value for s in RideRequest.Status]
            if status_filter not in valid_statuses:
                return Response(
                    {"detail": f"Invalid status '{status_filter}'. Valid values: {valid_statuses}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)
        rides = qs[:50]

        data = []
        for ride in rides:
            rider_data = None
            if ride.rider_id and ride.rider:
                rider_data = {
                    "id": ride.rider.id,
                    "name": ride.rider.name or "",
                    "phone": ride.rider.phone or "",
                }
            driver_data = None
            if ride.driver_id and ride.driver:
                driver_data = {
                    "id": ride.driver.id,
                    "name": ride.driver.name or "",
                    "phone": ride.driver.phone or "",
                }
            data.append({
                "id": ride.id,
                "kind": ride.kind,
                "status": ride.status,
                "fare": str(ride.fare),
                "payment_method": ride.payment_method,
                "paid_with_wallet": ride.paid_with_wallet,
                "distance_km": ride.distance_km,
                "pickup_address": ride.pickup_address,
                "dropoff_address": ride.dropoff_address,
                "created_at": _ts(ride.created_at),
                "completed_at": _ts(ride.completed_at),
                "rider": rider_data,
                "driver": driver_data,
            })
        return Response(data)


# ── Admin: car-document approval ──────────────────────────────────────────────────


class AdminCarApprovalView(APIView):
    """POST /api/admin/drivers/<id>/car-approve/  — approve car docs.
       POST /api/admin/drivers/<id>/car-reject/   — reject car docs (clears flag).

    Mirrors AdminDriverApprovalView style including audit logging.

    OPS-5c item 2: restored to OPS-5/5b standard — IsPlatformAdmin permission
    class (DRF session auth + CSRF), AdminPIIThrottle.
    """

    permission_classes = [IsPlatformAdmin]
    throttle_classes = [AdminPIIThrottle]

    def post(self, request, driver_id, *args, **kwargs):
        from sales.audit import log_admin_action
        from sales.models import AdminAuditLog

        approve = request.path.rstrip("/").endswith("car-approve")
        try:
            driver = Customer.objects.get(pk=driver_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver not found.", "code": "not_found"}, status=404)

        driver.driver_car_approved = approve
        driver.save(update_fields=["driver_car_approved", "updated_at"])

        action = (
            AdminAuditLog.Actions.DRIVER_APPROVED  # reuse closest action
            if approve
            else AdminAuditLog.Actions.DRIVER_REJECTED
        )
        log_admin_action(
            action=action,
            request=request,
            target_repr=f"driver:{driver.id}:car",
            metadata={
                "name": driver.name or "",
                "phone": driver.phone or "",
                "car_approved": approve,
            },
        )
        return Response({
            "id": driver.id,
            "driver_car_approved": bool(driver.driver_car_approved),
            "driver_licence_url": driver.driver_licence_url or "",
            "driver_insurance_url": driver.driver_insurance_url or "",
        })
