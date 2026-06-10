"""Ride-hailing API views.

All ride views live here for reviewability. Wired into config/shared_api_urls.py
next to the driver block.

Rider endpoints (session customer_id):
    POST   /api/rides/estimate/           — fare estimate (throttled)
    POST   /api/rides/                    — create ride (SEARCHING)
    GET    /api/rides/active/             — rider's active/recent ride
    POST   /api/rides/<id>/cancel/        — rider cancels
    POST   /api/rides/<id>/rate/          — rider rates driver (1-5)

Driver endpoints (is_driver + driver_approved):
    GET    /api/driver/rides/             — open SEARCHING rides + own active
    POST   /api/driver/rides/<id>/accept/ — first-accept-wins
    POST   /api/driver/rides/<id>/status/ — advance status
"""
from django.db import transaction as _tx
from django.utils import timezone as _tz
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Customer, RideRequest
from .push import push_new_ride_to_drivers, push_ride_event_to_rider
from .throttles import (
    RideEstimateThrottle,
    RideRequestThrottle,
    RideDriverThrottle,
    DriverJobAcceptThrottle,
    DriverStatusUpdateThrottle,
)


# ── Serialiser helper ─────────────────────────────────────────────────────────────

def _ts(dt):
    return dt.isoformat() if dt else None


def _serialize_ride(ride, *, include_driver_pii=False):
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
    return {
        "id": ride.id,
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
        "created_at": _ts(ride.created_at),
        "accepted_at": _ts(ride.accepted_at),
        "arrived_at": _ts(ride.arrived_at),
        "started_at": _ts(ride.started_at),
        "completed_at": _ts(ride.completed_at),
        "cancelled_at": _ts(ride.cancelled_at),
        "rider_driver_rating": ride.rider_driver_rating,
        "driver_rider_rating": ride.driver_rider_rating,
        "driver": driver,
    }


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
        })


class RideCreateView(APIView):
    """POST /api/rides/ — create a ride request (SEARCHING)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideRequestThrottle]

    def post(self, request, *args, **kwargs):
        from decimal import Decimal
        from .ride_service import estimate_ride

        rider, err = _get_rider(request)
        if err:
            return err

        # Validate required fields
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

        # Guard: one non-terminal ride per rider
        if RideRequest.objects.filter(
            rider=rider,
        ).exclude(status__in=RideRequest.TERMINAL_STATUSES).exists():
            return Response(
                {"detail": "You already have an active ride.", "code": "active_ride_exists"},
                status=status.HTTP_409_CONFLICT,
            )

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

        ride = RideRequest.objects.create(
            rider=rider,
            pickup_lat=float(request.data["pickup_lat"]),
            pickup_lng=float(request.data["pickup_lng"]),
            dropoff_lat=float(request.data["dropoff_lat"]),
            dropoff_lng=float(request.data["dropoff_lng"]),
            pickup_address=str(request.data.get("pickup_address") or "")[:255],
            dropoff_address=str(request.data.get("dropoff_address") or "")[:255],
            distance_km=result["distance_km"],
            fare=fare,
            payment_method=payment_method,
            status=RideRequest.Status.SEARCHING,
        )

        # Notify nearby car drivers (best-effort, after commit)
        try:
            push_new_ride_to_drivers(ride.id)
        except Exception:
            pass

        return Response(_serialize_ride(ride), status=status.HTTP_201_CREATED)


class RideActiveView(APIView):
    """GET /api/rides/active/ — rider's current non-terminal ride (or latest completed within 10 min)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        rider, err = _get_rider(request)
        if err:
            return err

        # First look for a non-terminal ride
        ride = (
            RideRequest.objects.filter(rider=rider)
            .exclude(status__in=RideRequest.TERMINAL_STATUSES)
            .select_related("driver")
            .order_by("-created_at")
            .first()
        )
        if ride is None:
            # Fall back to completed within the last 10 minutes (rating window)
            from datetime import timedelta
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

        if ride is None:
            return Response(None)

        # PII (driver phone + GPS) only revealed after driver is accepted
        pii_ok = ride.status not in (RideRequest.Status.SEARCHING,)
        return Response(_serialize_ride(ride, include_driver_pii=pii_ok))


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

            if ride.status not in ("searching", "accepted"):
                return Response(
                    {
                        "detail": f"Cannot cancel a ride in status '{ride.status}'.",
                        "allowed": ["searching", "accepted"],
                        "code": "bad_transition",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            driver_id = ride.driver_id
            ride.status = RideRequest.Status.CANCELLED
            ride.cancelled_at = now
            ride.save(update_fields=["status", "cancelled_at"])

        # Notify assigned driver (best-effort)
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
    """GET /api/driver/rides/ — open SEARCHING rides + own active ride.

    Only car drivers see ride offers.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RideDriverThrottle]

    def get(self, request, *args, **kwargs):
        driver, err = _get_driver(request)
        if err:
            return err

        # Own active ride (any non-terminal ride assigned to this driver)
        own_ride = (
            RideRequest.objects.filter(driver=driver)
            .exclude(status__in=RideRequest.TERMINAL_STATUSES)
            .select_related("rider")
            .order_by("-created_at")
            .first()
        )

        # Open SEARCHING rides — only offered to car drivers
        open_rides = []
        if driver.driver_vehicle_type == Customer.VEHICLE_TYPE_CAR:
            from tenancy.delivery_pricing import haversine_km, valid_coord
            qs = list(
                RideRequest.objects.filter(status=RideRequest.Status.SEARCHING)
                .select_related("rider")[:20]
            )
            for r in qs:
                dist_to_pickup = None
                if valid_coord(driver.driver_lat, driver.driver_lng) and valid_coord(r.pickup_lat, r.pickup_lng):
                    dist_to_pickup = round(
                        haversine_km(driver.driver_lat, driver.driver_lng, r.pickup_lat, r.pickup_lng), 2
                    )
                data = {
                    "id": r.id,
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
                }
                open_rides.append(data)

        return Response({
            "open_rides": open_rides,
            "active_ride": _serialize_ride(own_ride, include_driver_pii=True) if own_ride else None,
        })


class DriverRideAcceptView(APIView):
    """POST /api/driver/rides/<id>/accept/ — first-accept-wins, atomic."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverJobAcceptThrottle]

    def post(self, request, ride_id, *args, **kwargs):
        driver, err = _get_driver(request)
        if err:
            return err

        if driver.driver_vehicle_type != Customer.VEHICLE_TYPE_CAR:
            return Response(
                {"detail": "Only car drivers can accept ride requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = _tz.now()
        with _tx.atomic():
            # Lock driver row first (serialize concurrent accepts from same driver)
            Customer.objects.select_for_update().filter(pk=driver.id).first()

            # Check driver doesn't already have an active ride
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
                ride.completed_at = now
                update_fields.append("completed_at")
                # settle_ride runs INSIDE the transaction
                from .ride_service import settle_ride
                settle_ride(ride)
                # save may have updated payment_method/paid_with_wallet inside settle
                update_fields += ["payment_method", "paid_with_wallet"]

            ride.save(update_fields=update_fields)

        return Response(_serialize_ride(ride, include_driver_pii=True))
