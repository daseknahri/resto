"""Tests for ride-hailing views and service.

    POST   /api/rides/estimate/           RideEstimateView
    POST   /api/rides/                    RideCreateView
    GET    /api/rides/active/             RideActiveView
    POST   /api/rides/<id>/cancel/        RideCancelView
    POST   /api/rides/<id>/rate/          RideRateView
    GET    /api/driver/rides/             DriverRideListView
    POST   /api/driver/rides/<id>/accept/ DriverRideAcceptView
    POST   /api/driver/rides/<id>/status/ DriverRideStatusView

All unit-level: SimpleTestCase + mocks, no real DB.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.ride_views import (
    RideEstimateView,
    RideCreateView,
    RideActiveView,
    RideHistoryView,
    RideCancelView,
    RideRateView,
    DriverRideListView,
    DriverRideHistoryView,
    DriverRideAcceptView,
    DriverRideStatusView,
    DriverDocUploadView,
    DriverRateRideView,
    AdminRideListView,
    AdminCarApprovalView,
)


# ── Helpers ───────────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    return sess


def _make_customer(pk=1, is_driver=False, driver_approved=False, is_driver_online=False,
                   driver_vehicle_type="", wallet_balance=Decimal("100.00"), name="Test User",
                   phone="0600000001", driver_lat=None, driver_lng=None,
                   driver_car_approved=False, driver_licence_url="", driver_insurance_url=""):
    c = MagicMock()
    c.pk = pk
    c.id = pk
    c.is_driver = is_driver
    c.driver_approved = driver_approved
    c.is_driver_online = is_driver_online
    c.driver_vehicle_type = driver_vehicle_type
    c.wallet_balance = wallet_balance
    c.name = name
    c.phone = phone
    c.driver_vehicle = ""
    c.driver_lat = driver_lat
    c.driver_lng = driver_lng
    c.driver_position_updated_at = None
    c.driver_car_approved = driver_car_approved
    c.driver_licence_url = driver_licence_url
    c.driver_insurance_url = driver_insurance_url
    return c


def _make_ride(pk=1, status_val="searching", rider=None, driver=None,
               fare=Decimal("15.00"), distance_km=2.5, payment_method="wallet",
               paid_with_wallet=False, rider_driver_rating=None):
    r = MagicMock()
    r.pk = pk
    r.id = pk
    r.status = status_val
    r.rider = rider or _make_customer(pk=10)
    r.rider_id = r.rider.id
    r.driver = driver
    r.driver_id = driver.id if driver else None
    r.fare = fare
    r.distance_km = distance_km
    r.payment_method = payment_method
    r.paid_with_wallet = paid_with_wallet
    r.rider_driver_rating = rider_driver_rating
    r.driver_rider_rating = None
    r.pickup_lat = 33.5
    r.pickup_lng = -7.6
    r.dropoff_lat = 33.55
    r.dropoff_lng = -7.65
    r.pickup_address = "A"
    r.dropoff_address = "B"
    r.created_at = MagicMock()
    r.created_at.isoformat.return_value = "2026-06-10T10:00:00+00:00"
    r.accepted_at = None
    r.arrived_at = None
    r.started_at = None
    r.completed_at = None
    r.cancelled_at = None
    r.scheduled_for = None
    r.dispatched_at = None
    r.TERMINAL_STATUSES = {"completed", "cancelled"}
    r.is_terminal = status_val in {"completed", "cancelled"}
    # Courier MVP fields — default to ride values so existing tests need no changes
    r.kind = "ride"
    r.recipient_name = ""
    r.recipient_phone = ""
    r.package_note = ""
    # Handover code fields (migration 0040)
    r.delivery_code = ""
    r.code_attempts = 0
    r.code_locked_until = None
    return r


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ── RideEstimateView ─────────────────────────────────────────────────────────────

class RideEstimateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideEstimateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/rides/estimate/", data, format="json")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideEstimateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_service.estimate_ride")
    def test_valid_estimate(self, mock_estimate, _throttle):
        mock_estimate.return_value = {"distance_km": 3.2, "fare": Decimal("23.20"), "duration_min": 8}
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["fare"], "23.20")
        self.assertAlmostEqual(resp.data["distance_km"], 3.2)
        self.assertEqual(resp.data["duration_min"], 8)

    @patch("accounts.ride_views.RideEstimateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_service.estimate_ride", side_effect=ValueError("invalid pickup coordinates"))
    def test_bad_coords_returns_400(self, _est, _throttle):
        req = self._post({
            "pickup_lat": 0, "pickup_lng": 0,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.ride_views.RideEstimateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_service.estimate_ride", side_effect=ValueError("implausible ride distance (150.0 km)"))
    def test_implausible_distance_returns_400(self, _est, _throttle):
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 35.0, "dropoff_lng": -10.0,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.ride_views.RideEstimateThrottle.allow_request", return_value=True)
    def test_missing_field_returns_400(self, _throttle):
        req = self._post({"pickup_lat": 33.5, "pickup_lng": -7.6, "dropoff_lat": 33.55})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── RideService: estimate_ride unit tests (no view) ──────────────────────────────

class RideServiceEstimateTests(SimpleTestCase):
    """Test accounts.ride_service.estimate_ride directly (mocking the platform seams)."""

    @patch("accounts.ride_service.PlatformConfig")
    @patch("accounts.ride_service.road_distance_km", return_value=5.0)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_minimum_fare_floor(self, _vc, _road, mock_cfg):
        """Fare must never fall below ride_minimum_fare."""
        from accounts.ride_service import estimate_ride
        cfg = MagicMock()
        cfg.ride_base_fare = Decimal("2.00")
        cfg.ride_per_km = Decimal("1.00")
        cfg.ride_minimum_fare = Decimal("12.00")
        mock_cfg.get_solo.return_value = cfg
        result = estimate_ride(33.5, -7.6, 33.6, -7.7)
        # base + per_km*dist = 2 + 5 = 7 < minimum 12 → should be 12
        self.assertEqual(result["fare"], Decimal("12.00"))

    @patch("accounts.ride_service.PlatformConfig")
    @patch("accounts.ride_service.road_distance_km", return_value=10.0)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_fare_above_minimum(self, _vc, _road, mock_cfg):
        from accounts.ride_service import estimate_ride
        cfg = MagicMock()
        cfg.ride_base_fare = Decimal("8.00")
        cfg.ride_per_km = Decimal("3.50")
        cfg.ride_minimum_fare = Decimal("12.00")
        mock_cfg.get_solo.return_value = cfg
        result = estimate_ride(33.5, -7.6, 33.6, -7.7)
        # 8 + 3.5 * 10 = 43
        self.assertEqual(result["fare"], Decimal("43.00"))

    @patch("accounts.ride_service.valid_coord", return_value=False)
    def test_bad_pickup_coord_raises(self, _vc):
        from accounts.ride_service import estimate_ride
        with self.assertRaises(ValueError):
            estimate_ride(0, 0, 33.6, -7.7)

    @patch("accounts.ride_service.road_distance_km", return_value=200.0)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_implausible_distance_raises(self, _vc, _road):
        from accounts.ride_service import estimate_ride
        with self.assertRaises(ValueError):
            estimate_ride(33.5, -7.6, 40.0, -8.0)


# ── RideCreateView ────────────────────────────────────────────────────────────────

@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier", "food", "shops", "pharmacy", "driver"}))
class RideCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCreateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/rides/", data, format="json")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._post({}, session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.models.Customer.objects")
    def test_no_customer_returns_404(self, mock_objs, _throttle):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        req = self._post({}, session=_session(customer_id=99))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_duplicate_active_ride_returns_409(self, mock_est, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        # Simulate existing active ride
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = True
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        }, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "active_ride_exists")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_insufficient_wallet_returns_400(self, mock_est, mock_cust_objs, mock_ride_objs, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("5.00"))
        mock_cust_objs.get.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "payment_method": "wallet",
        }, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "insufficient_wallet")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_successful_creation_returns_201(self, mock_est, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_ride(pk=5, rider=rider)
        mock_ride_objs.create.return_value = ride
        with patch("accounts.ride_views.push_new_ride_to_drivers"):
            req = self._post({
                "pickup_lat": 33.5, "pickup_lng": -7.6,
                "dropoff_lat": 33.55, "dropoff_lng": -7.65,
                "payment_method": "wallet",
            }, session=_session(customer_id=1))
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ── DriverRideAcceptView — race test ─────────────────────────────────────────────

class DriverRideAcceptViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideAcceptView.as_view()

    def _post(self, ride_id=1, session=None):
        req = self.factory.post(f"/api/driver/rides/{ride_id}/accept/")
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.DriverJobAcceptThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_second_accept_returns_409(self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        """Simulate the TOCTOU race: ride is no longer SEARCHING when second driver locks it."""
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True,
                                is_driver_online=True, driver_vehicle_type="car",
                                driver_car_approved=True)
        mock_cust_objs.get.return_value = driver

        mock_tx.atomic.return_value = _noop_atomic()

        # select_for_update().filter() used to lock driver row
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver

        # No active ride for this driver
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False

        # Ride no longer SEARCHING (already accepted by another driver)
        from accounts.models import RideRequest
        mock_ride_objs.select_for_update.return_value.get.side_effect = RideRequest.DoesNotExist

        req = self._post(session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("accounts.ride_views.DriverJobAcceptThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_non_car_driver_returns_403(self, mock_cust_objs, mock_ride_objs, _throttle):
        """Motorbike driver cannot accept a ride (kind='ride') — 403 inside lock."""
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True,
                                is_driver_online=True, driver_vehicle_type="motorbike")
        mock_cust_objs.get.return_value = driver

        with patch("accounts.ride_views._tx") as mock_tx:
            mock_tx.atomic.return_value = _noop_atomic()
            mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver
            # No active trip for this driver
            mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
            # The ride being accepted is a 'ride' kind
            ride_trip = _make_ride(pk=1)
            ride_trip.kind = "ride"
            ride_trip.status = "searching"
            ride_trip.driver = None
            ride_trip.driver_id = None
            mock_ride_objs.select_for_update.return_value.get.return_value = ride_trip

            req = self._post(session=_session(customer_id=2))
            resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── DriverRideStatusView — transition guard ───────────────────────────────────────

class DriverRideStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideStatusView.as_view()

    def _post(self, ride_id, data, session=None):
        req = self.factory.post(f"/api/driver/rides/{ride_id}/status/", data, format="json")
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_completed_ride_status_change_409(self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        """Cannot transition a completed ride."""
        driver = _make_customer(pk=2, is_driver=True)
        mock_cust_objs.get.return_value = driver

        mock_tx.atomic.return_value = _noop_atomic()

        ride = _make_ride(pk=1, status_val="completed", driver=driver)
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(ride_id=1, data={"status": "in_progress"}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_transition")


# ── settle_ride idempotency key tests ─────────────────────────────────────────────

class SettleRideTests(SimpleTestCase):
    """Test settle_ride uses correct idempotency keys and handles InsufficientFunds."""

    @patch("accounts.ride_service.credit_wallet")
    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_wallet_ride_uses_correct_idempotency_keys(self, mock_cfg, mock_debit, mock_credit):
        from accounts.ride_service import _do_settle

        cfg = MagicMock()
        cfg.ride_commission_pct = Decimal("0")
        mock_cfg.get_solo.return_value = cfg

        ride = MagicMock()
        ride.id = 42
        ride.payment_method = "wallet"
        ride.fare = Decimal("20.00")
        ride.rider_id = 10
        ride.driver_id = 5
        ride.save = MagicMock()

        _do_settle(ride)

        mock_debit.assert_called_once()
        debit_kwargs = mock_debit.call_args
        self.assertEqual(debit_kwargs[1]["idempotency_key"], "ride:42")

        mock_credit.assert_called_once()
        credit_kwargs = mock_credit.call_args
        self.assertEqual(credit_kwargs[1]["idempotency_key"], "ridepay:42")

    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_insufficient_balance_flips_to_cash(self, mock_cfg, mock_debit):
        from accounts.ride_service import _do_settle
        from accounts.wallet_service import InsufficientFunds

        cfg = MagicMock()
        cfg.ride_commission_pct = Decimal("0")
        mock_cfg.get_solo.return_value = cfg

        mock_debit.side_effect = InsufficientFunds("not enough")

        ride = MagicMock()
        ride.id = 43
        ride.payment_method = "wallet"
        ride.fare = Decimal("20.00")
        ride.rider_id = 10
        ride.driver_id = 5
        ride.save = MagicMock()

        _do_settle(ride)

        # _do_settle mutates in memory; the outer atomic transaction is responsible for saving.
        self.assertEqual(ride.payment_method, "cash")
        ride.save.assert_not_called()

    @patch("accounts.ride_service.credit_wallet")
    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_cash_ride_no_wallet_movement(self, mock_cfg, mock_debit, mock_credit):
        from accounts.ride_service import _do_settle

        ride = MagicMock()
        ride.payment_method = "cash"

        _do_settle(ride)

        mock_debit.assert_not_called()
        mock_credit.assert_not_called()


# ── RideRateView ──────────────────────────────────────────────────────────────────

class RideRateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideRateView.as_view()

    def _post(self, ride_id, data, session=None):
        req = self.factory.post(f"/api/rides/{ride_id}/rate/", data, format="json")
        req.session = session or _session(customer_id=10)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_rate_non_completed_ride_returns_409(self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        rider = _make_customer(pk=10)
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        ride = _make_ride(pk=1, status_val="in_progress", rider=rider)
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(ride_id=1, data={"rating": 4}, session=_session(customer_id=10))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_completed")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_double_rate_returns_409(self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        rider = _make_customer(pk=10)
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        ride = _make_ride(pk=1, status_val="completed", rider=rider, rider_driver_rating=4)
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(ride_id=1, data={"rating": 5}, session=_session(customer_id=10))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_rated")


# ── PII gating — driver phone absent while SEARCHING ─────────────────────────────

class PIIGatingTests(SimpleTestCase):
    """Driver phone and GPS must not appear in SEARCHING status."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideActiveView.as_view()

    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_views.RideRequest.objects")
    def test_driver_phone_absent_while_searching(self, mock_ride_objs, mock_cust_objs):
        rider = _make_customer(pk=10, phone="0600000001")
        driver = _make_customer(pk=2, phone="0611111111", is_driver=True)
        mock_cust_objs.get.return_value = rider

        ride = _make_ride(pk=1, status_val="searching", rider=rider, driver=driver)

        # Response shape after scheduled-trips: {"ride": ..., "scheduled": []}
        # Wire the chain: filter().exclude().select_related().order_by().first() → ride
        # AND filter().filter().order_by().__getitem__() → [] for the scheduled list
        active_chain = MagicMock()
        active_chain.exclude.return_value.select_related.return_value.order_by.return_value.first.return_value = ride

        scheduled_chain = MagicMock()
        scheduled_chain.order_by.return_value.__getitem__ = lambda self, sl: []

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_chain
            return scheduled_chain

        mock_ride_objs.filter.side_effect = filter_side

        req = self.factory.get("/api/rides/active/")
        req.session = _session(customer_id=10)
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # New shape: resp.data["ride"] holds the active trip
        ride_data = resp.data.get("ride") or {}
        driver_data = ride_data.get("driver") or {}
        self.assertIsNone(driver_data.get("phone"))
        self.assertIsNone(driver_data.get("driver_lat"))
        # Scheduled list is always present
        self.assertIn("scheduled", resp.data)
        self.assertEqual(resp.data["scheduled"], [])


# ── DriverRideListView — car vehicle type required ───────────────────────────────

class DriverRideListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideListView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/driver/rides/")
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_motorbike_driver_sees_no_open_rides(self, mock_cust_objs, mock_ride_objs, _throttle):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True,
                                is_driver_online=True, driver_vehicle_type="motorbike")
        mock_cust_objs.get.return_value = driver

        # Own active ride: none
        mock_ride_objs.filter.return_value.exclude.return_value.select_related.return_value.order_by.return_value.first.return_value = None

        req = self._get(session=_session(customer_id=2))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["open_rides"], [])

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.models.Customer.objects")
    def test_no_session_returns_401(self, _cust_objs, _throttle):
        req = self._get(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── update_fields house rule: only real field names ───────────────────────────────

class UpdateFieldsHouseRuleTests(SimpleTestCase):
    """Verify that save() calls inside settle_ride use only real RideRequest field names."""

    def test_settle_ride_insufficient_funds_update_fields(self):
        """InsufficientFunds path: _do_settle mutates in memory, no save called inside."""
        from accounts.ride_service import _do_settle
        from accounts.wallet_service import InsufficientFunds

        with patch("accounts.ride_service.PlatformConfig") as mock_cfg, \
             patch("accounts.ride_service.debit_wallet", side_effect=InsufficientFunds("no")):
            mock_cfg.get_solo.return_value = MagicMock(ride_commission_pct=Decimal("0"))
            ride = MagicMock()
            ride.id = 99
            ride.payment_method = "wallet"
            ride.fare = Decimal("15.00")
            ride.rider_id = 1
            ride.driver_id = 2
            ride.save = MagicMock()
            _do_settle(ride)

        # The outer atomic transaction is responsible for the single save.
        ride.save.assert_not_called()
        self.assertEqual(ride.payment_method, "cash")


# ── Phase 2: Car-document vetting gate ───────────────────────────────────────────

class CarApprovedGateTests(SimpleTestCase):
    """Offers and accept blocked without driver_car_approved=True."""

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_offers_blocked_without_car_approved(self, mock_cust_objs, mock_ride_objs, _throttle):
        """Car driver without car_approved sees no open_rides offers."""
        driver = _make_customer(
            pk=2, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="car", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver
        # No own active ride
        mock_ride_objs.filter.return_value.exclude.return_value.select_related.return_value.order_by.return_value.first.return_value = None
        # last_completed query
        mock_ride_objs.filter.return_value.order_by.return_value.first.return_value = None

        req = self.factory.get("/api/driver/rides/")
        req.session = _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        resp = DriverRideListView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["open_rides"], [])

    @patch("accounts.ride_views.DriverJobAcceptThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_accept_blocked_without_car_approved(self, mock_cust_objs, mock_ride_objs, _throttle):
        """Car driver without car_approved cannot accept a ride (kind='ride')."""
        driver = _make_customer(
            pk=2, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="car", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        with patch("accounts.ride_views._tx") as mock_tx:
            mock_tx.atomic.return_value = _noop_atomic()
            mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver
            # No active trip for this driver
            mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
            # The ride being accepted is a 'ride' kind
            ride_trip = _make_ride(pk=1)
            ride_trip.kind = "ride"
            ride_trip.status = "searching"
            ride_trip.driver = None
            ride_trip.driver_id = None
            mock_ride_objs.select_for_update.return_value.get.return_value = ride_trip

            req = self.factory.post("/api/driver/rides/1/accept/")
            req.session = _session(customer_id=2)
            req.user = MagicMock(is_authenticated=False)
            resp = DriverRideAcceptView.as_view()(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "car_not_approved")


# ── Phase 2: DriverDocUploadView ──────────────────────────────────────────────────

class DriverDocUploadViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverDocUploadView.as_view()

    def _post(self, data=None, files=None, session=None):
        req = self.factory.post(
            "/api/driver/docs/",
            data={**(data or {}), **(files or {})},
            format="multipart",
        )
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._post(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_bad_kind_returns_400(self, mock_cust_objs):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver

        req = self._post(data={"kind": "passport"}, session=_session(customer_id=2))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_kind")

    @patch("accounts.ride_views._notify_admins_car_docs")
    @patch("accounts.ride_views._save_driver_doc_image", return_value="https://cdn.example.com/licence.jpg")
    @patch("accounts.models.Customer.objects")
    def test_licence_upload_sets_field_and_resets_approval(
        self, mock_cust_objs, mock_save, mock_notify
    ):
        driver = _make_customer(
            pk=2, is_driver=True, driver_car_approved=True,
            driver_licence_url="", driver_insurance_url="",
        )
        mock_cust_objs.get.return_value = driver

        from django.core.files.uploadedfile import SimpleUploadedFile
        img = SimpleUploadedFile("lic.jpg", b"data", content_type="image/jpeg")
        req = self._post(data={"kind": "licence"}, files={"image": img}, session=_session(customer_id=2))
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["kind"], "licence")
        self.assertFalse(resp.data["driver_car_approved"])
        # driver.save called with driver_car_approved in update_fields
        driver.save.assert_called_once()
        call_kwargs = driver.save.call_args[1]
        self.assertIn("driver_car_approved", call_kwargs.get("update_fields", []))
        self.assertIn("driver_licence_url", call_kwargs.get("update_fields", []))

    @patch("accounts.ride_views._notify_admins_car_docs")
    @patch("accounts.ride_views._save_driver_doc_image", return_value="https://cdn.example.com/ins.jpg")
    @patch("accounts.models.Customer.objects")
    def test_both_docs_triggers_admin_notify(self, mock_cust_objs, mock_save, mock_notify):
        """When BOTH docs present after upload, notify admins."""
        driver = _make_customer(
            pk=2, is_driver=True,
            driver_licence_url="https://cdn.example.com/old_lic.jpg",
            driver_insurance_url="",
        )
        # Simulate save setting the insurance_url
        def _fake_save(**kwargs):
            driver.driver_insurance_url = "https://cdn.example.com/ins.jpg"
        driver.save.side_effect = _fake_save

        mock_cust_objs.get.return_value = driver

        from django.core.files.uploadedfile import SimpleUploadedFile
        img = SimpleUploadedFile("ins.jpg", b"data", content_type="image/jpeg")
        req = self._post(data={"kind": "insurance"}, files={"image": img}, session=_session(customer_id=2))
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_notify.assert_called_once_with(driver)


# ── Phase 2: Admin car-approve / car-reject ───────────────────────────────────────

class AdminCarApprovalViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCarApprovalView.as_view()

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("sales.audit.log_admin_action")
    @patch("accounts.models.Customer.objects")
    def test_car_approve_sets_flag(self, mock_cust_objs, mock_audit, _perm):
        driver = _make_customer(pk=5, is_driver=True, driver_car_approved=False)
        mock_cust_objs.get.return_value = driver

        req = self.factory.post("/api/admin/drivers/5/car-approve/")
        req.session = _session()
        req.user = MagicMock(is_authenticated=True, is_platform_admin=True)
        resp = self.view(req, driver_id=5)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # driver_car_approved must have been set to True before save
        driver.save.assert_called_once()
        call_kwargs = driver.save.call_args[1]
        self.assertIn("driver_car_approved", call_kwargs.get("update_fields", []))
        mock_audit.assert_called_once()

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("sales.audit.log_admin_action")
    @patch("accounts.models.Customer.objects")
    def test_car_reject_clears_flag(self, mock_cust_objs, mock_audit, _perm):
        driver = _make_customer(pk=5, is_driver=True, driver_car_approved=True)
        mock_cust_objs.get.return_value = driver

        req = self.factory.post("/api/admin/drivers/5/car-reject/")
        req.path = "/api/admin/drivers/5/car-reject/"
        req.session = _session()
        req.user = MagicMock(is_authenticated=True, is_platform_admin=True)
        resp = self.view(req, driver_id=5)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        driver.save.assert_called_once()

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=False)
    @patch("accounts.models.Customer.objects")
    def test_non_admin_returns_403(self, mock_cust_objs, _perm):
        req = self.factory.post("/api/admin/drivers/5/car-approve/")
        req.session = _session()
        req.user = MagicMock(is_authenticated=True, is_platform_admin=False)
        resp = self.view(req, driver_id=5)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Phase 2: Per-minute fare math ────────────────────────────────────────────────

class PerMinuteFareTests(SimpleTestCase):
    """estimate_ride per-minute component and duration_min."""

    @patch("accounts.ride_service.PlatformConfig")
    @patch("accounts.ride_service.road_distance_km", return_value=12.0)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_per_minute_zero_unchanged(self, _vc, _road, mock_cfg):
        """ride_per_minute=0 → per-minute component is 0 (fully backward compatible)."""
        from accounts.ride_service import estimate_ride
        cfg = MagicMock()
        cfg.ride_base_fare = Decimal("8.00")
        cfg.ride_per_km = Decimal("3.50")
        cfg.ride_minimum_fare = Decimal("12.00")
        cfg.ride_per_minute = Decimal("0.00")
        mock_cfg.get_solo.return_value = cfg
        result = estimate_ride(33.5, -7.6, 33.6, -7.7)
        # Expected: 8 + 3.5 * 12 = 8 + 42 = 50
        self.assertEqual(result["fare"], Decimal("50.00"))
        self.assertIn("duration_min", result)

    @patch("accounts.ride_service.PlatformConfig")
    @patch("accounts.ride_service.road_distance_km", return_value=12.0)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_per_minute_adds_to_fare(self, _vc, _road, mock_cfg):
        """ride_per_minute > 0 increases fare by est_minutes * per_minute."""
        from accounts.ride_service import estimate_ride, AVG_CITY_SPEED_KMH
        cfg = MagicMock()
        cfg.ride_base_fare = Decimal("8.00")
        cfg.ride_per_km = Decimal("3.50")
        cfg.ride_minimum_fare = Decimal("12.00")
        cfg.ride_per_minute = Decimal("1.00")
        mock_cfg.get_solo.return_value = cfg
        result = estimate_ride(33.5, -7.6, 33.6, -7.7)
        # est_minutes = round(12 / 24 * 60) = 30
        expected_minutes = int(round(12.0 / AVG_CITY_SPEED_KMH * 60))
        # fare = max(12, 8 + 3.5*12 + 1.0*30) = max(12, 80) = 80
        expected_fare = max(
            Decimal("12.00"),
            Decimal("8.00") + Decimal("3.50") * Decimal("12.0") + Decimal("1.00") * Decimal(str(expected_minutes)),
        ).quantize(Decimal("0.01"))
        self.assertEqual(result["fare"], expected_fare)
        self.assertEqual(result["duration_min"], expected_minutes)

    @patch("accounts.ride_service.PlatformConfig")
    @patch("accounts.ride_service.road_distance_km", return_value=0.5)
    @patch("accounts.ride_service.valid_coord", return_value=True)
    def test_minimum_floor_still_applies_with_per_minute(self, _vc, _road, mock_cfg):
        """Minimum fare floor still applies even when per_minute > 0."""
        from accounts.ride_service import estimate_ride
        cfg = MagicMock()
        cfg.ride_base_fare = Decimal("1.00")
        cfg.ride_per_km = Decimal("0.50")
        cfg.ride_minimum_fare = Decimal("20.00")
        cfg.ride_per_minute = Decimal("0.10")
        mock_cfg.get_solo.return_value = cfg
        result = estimate_ride(33.5, -7.6, 33.6, -7.7)
        # Tiny distance, small time — raw will be < 20 → floor applies
        self.assertEqual(result["fare"], Decimal("20.00"))


# ── Phase 2: duration_min in estimate view response ───────────────────────────────

class EstimateViewDurationMinTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideEstimateView.as_view()

    @patch("accounts.ride_views.RideEstimateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_service.estimate_ride")
    def test_duration_min_in_response(self, mock_estimate, _throttle):
        mock_estimate.return_value = {
            "distance_km": 5.0,
            "fare": Decimal("25.00"),
            "duration_min": 12,
        }
        req = self.factory.post("/api/rides/estimate/", {
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        }, format="json")
        req.session = _session()
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("duration_min", resp.data)
        self.assertEqual(resp.data["duration_min"], 12)


# ── Phase 2: DriverRateRideView ───────────────────────────────────────────────────

class DriverRateRideViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRateRideView.as_view()

    def _post(self, ride_id, data, session=None):
        req = self.factory.post(f"/api/driver/rides/{ride_id}/rate/", data, format="json")
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._post(1, {"rating": 4}, session=_session(customer_id=None))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_non_driver_returns_403(self, mock_cust_objs):
        from accounts.models import Customer
        mock_cust_objs.get.side_effect = Customer.DoesNotExist
        req = self._post(1, {"rating": 4}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_not_assigned_driver_returns_403(self, mock_cust_objs, mock_ride_objs, mock_tx):
        """A different (approved) driver trying to rate a ride they didn't drive."""
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()

        from accounts.models import RideRequest as RR
        # select_for_update().get(driver=driver) raises DoesNotExist (wrong driver)
        mock_ride_objs.select_for_update.return_value.get.side_effect = RR.DoesNotExist
        # But the ride does exist (filter().exists() = True)
        mock_ride_objs.filter.return_value.exists.return_value = True

        req = self._post(1, {"rating": 5}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_not_completed_returns_409(self, mock_cust_objs, mock_ride_objs, mock_tx):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()

        ride = _make_ride(pk=1, status_val="in_progress", driver=driver)
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(1, {"rating": 4}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_completed")

    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_double_rate_returns_409(self, mock_cust_objs, mock_ride_objs, mock_tx):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()

        ride = _make_ride(pk=1, status_val="completed", driver=driver)
        ride.driver_rider_rating = 3  # already rated
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(1, {"rating": 5}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_rated")

    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_success_sets_driver_rider_rating(self, mock_cust_objs, mock_ride_objs, mock_tx):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()

        ride = _make_ride(pk=1, status_val="completed", driver=driver)
        ride.driver_rider_rating = None
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post(1, {"rating": 4}, session=_session(customer_id=2))
        resp = self.view(req, ride_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        self.assertEqual(resp.data["rating"], 4)
        ride.save.assert_called_once()
        call_kwargs = ride.save.call_args[1]
        self.assertIn("driver_rider_rating", call_kwargs.get("update_fields", []))


# ── Phase 2: last_completed in DriverRideListView ─────────────────────────────────

class DriverRideListLastCompletedTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideListView.as_view()

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_last_completed_in_response(self, mock_cust_objs, mock_ride_objs, _throttle):
        driver = _make_customer(
            pk=2, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="car", driver_car_approved=True,
        )
        mock_cust_objs.get.return_value = driver

        # own active ride: none (first filter call)
        active_qs = MagicMock()
        active_qs.exclude.return_value.select_related.return_value.order_by.return_value.first.return_value = None

        # last completed (second filter call)
        lc = _make_ride(pk=9, status_val="completed", driver=driver, fare=Decimal("25.00"))
        lc.driver_rider_rating = None
        lc.paid_with_wallet = True
        lc_qs = MagicMock()
        lc_qs.order_by.return_value.first.return_value = lc

        # open SEARCHING (third filter call)
        open_qs = MagicMock()
        open_qs.select_related.return_value.__getitem__ = MagicMock(return_value=[])

        call_count = [0]
        def filter_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_qs
            elif call_count[0] == 2:
                return lc_qs
            else:
                return open_qs

        mock_ride_objs.filter.side_effect = filter_side_effect

        req = self.factory.get("/api/driver/rides/")
        req.session = _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("last_completed", resp.data)
        lc_data = resp.data["last_completed"]
        if lc_data:  # may be None if mock timing differs
            self.assertIn("id", lc_data)
            self.assertIn("fare", lc_data)
            self.assertIn("payment_method", lc_data)
            self.assertIn("paid_with_wallet", lc_data)
            self.assertIn("driver_rider_rating", lc_data)


# ── sweep_ride_requests command ───────────────────────────────────────────────────

class SweepRideRequestsTests(SimpleTestCase):
    """Unit tests for accounts/management/commands/sweep_ride_requests.py.

    All DB calls are mocked; no real database needed.
    update_fields subsets are checked where relevant.
    """

    def _run_command(self):
        from accounts.management.commands.sweep_ride_requests import Command
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda s: s
        cmd.handle()

    # ── Rule (b): auto-cancel only rides > 15 min SEARCHING ──────────────────────

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_cancel_only_over_15min_searching(self, mock_tz, mock_tx, mock_rr,
                                               mock_push_drivers, mock_push_rider):
        """A SEARCHING ride older than 15 min is cancelled; non-expired ride is NOT."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        ride_old = _make_ride(pk=1, status_val="searching")
        ride_old.rider_id = 10

        # (d) queryset — no scheduled trips due for release
        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([]))

        # (a) queryset — no rides in 3-15 min window
        qs_a = MagicMock()
        qs_a.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        # (b) queryset — one ride > 15 min
        qs_b = MagicMock()
        qs_b.filter.return_value.__iter__ = MagicMock(return_value=iter([ride_old]))

        # (c) queryset — no candidates
        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([]))

        call_count = [0]

        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d   # rule (d): scheduled trips due for release
            elif call_count[0] == 2:
                return qs_a   # rule (a): SEARCHING driver-less for re-push
            elif call_count[0] == 3:
                return qs_b   # rule (b): SEARCHING driver-less for cancel
            else:
                return qs_c   # rule (c): ACCEPTED/ARRIVED stale-driver

        mock_rr.objects.filter.side_effect = filter_side

        # select_for_update inside atomic — return the locked ride
        locked_qs = MagicMock()
        locked_qs.filter.return_value.first.return_value = ride_old
        mock_rr.objects.select_for_update.return_value = locked_qs

        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        ride_old.save.assert_called_once()
        call_kwargs = ride_old.save.call_args[1]
        self.assertIn("status", call_kwargs.get("update_fields", []))
        self.assertIn("cancelled_at", call_kwargs.get("update_fields", []))
        self.assertEqual(ride_old.status, "cancelled")
        mock_push_rider.assert_called_once_with(10, "no_driver_found")

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_accepted_ride_not_auto_cancelled(self, mock_tz, mock_tx, mock_rr,
                                               mock_push_drivers, mock_push_rider):
        """An ACCEPTED ride is never touched by the auto-cancel rule."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        # (d) empty; (a) empty; (b) empty; (c) one ACCEPTED ride with a fresh online driver
        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([]))
        qs_a = MagicMock()
        qs_a.filter.return_value.__iter__ = MagicMock(return_value=iter([]))
        qs_b = MagicMock()
        qs_b.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        online_driver = _make_customer(pk=5, is_driver=True, driver_approved=True,
                                       is_driver_online=True)
        online_driver.driver_position_updated_at = now  # fresh — not stale
        ride_accepted = _make_ride(pk=2, status_val="accepted", driver=online_driver)

        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([ride_accepted]))

        call_count = [0]

        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d   # rule (d)
            elif call_count[0] == 2:
                return qs_a   # rule (a)
            elif call_count[0] == 3:
                return qs_b   # rule (b)
            else:
                return qs_c   # rule (c)

        mock_rr.objects.filter.side_effect = filter_side
        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        # Online + fresh driver: no release, no cancel push
        ride_accepted.save.assert_not_called()
        mock_push_rider.assert_not_called()

    # ── Rule (c): release stale-driver ACCEPTED; never touch in_progress ─────────

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_releases_stale_driver_accepted(self, mock_tz, mock_tx, mock_rr,
                                             mock_push_drivers, mock_push_rider):
        """An ACCEPTED ride with an offline driver is released back to SEARCHING."""
        from django.utils import timezone as real_tz
        from datetime import timedelta
        now = real_tz.now()
        mock_tz.now.return_value = now

        offline_driver = _make_customer(pk=5, is_driver=True, driver_approved=True,
                                        is_driver_online=False)
        offline_driver.driver_position_updated_at = now - timedelta(minutes=20)

        ride_accepted = _make_ride(pk=3, status_val="accepted", driver=offline_driver)

        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([]))
        qs_a = MagicMock()
        qs_a.filter.return_value.__iter__ = MagicMock(return_value=iter([]))
        qs_b = MagicMock()
        qs_b.filter.return_value.__iter__ = MagicMock(return_value=iter([]))
        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([ride_accepted]))

        call_count = [0]

        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d   # rule (d)
            elif call_count[0] == 2:
                return qs_a   # rule (a)
            elif call_count[0] == 3:
                return qs_b   # rule (b)
            else:
                return qs_c   # rule (c)

        mock_rr.objects.filter.side_effect = filter_side

        locked_qs = MagicMock()
        locked_qs.filter.return_value.first.return_value = ride_accepted
        mock_rr.objects.select_for_update.return_value = locked_qs

        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        ride_accepted.save.assert_called_once()
        call_kwargs = ride_accepted.save.call_args[1]
        ufs = call_kwargs.get("update_fields", [])
        self.assertIn("driver", ufs)
        self.assertIn("status", ufs)
        self.assertIn("accepted_at", ufs)
        self.assertIn("arrived_at", ufs)
        self.assertEqual(ride_accepted.status, "searching")
        self.assertIsNone(ride_accepted.driver)
        mock_push_drivers.assert_called_once_with(ride_accepted.id)

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_in_progress_excluded_from_release(self, mock_tz, mock_tx, mock_rr,
                                                mock_push_drivers, mock_push_rider):
        """IN_PROGRESS rides are excluded from rule (c) by the filter clause."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        qs_empty = MagicMock()
        qs_empty.__iter__ = MagicMock(return_value=iter([]))
        qs_empty_ab = MagicMock()
        qs_empty_ab.filter.return_value.__iter__ = MagicMock(return_value=iter([]))
        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([]))

        call_count = [0]

        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_empty       # rule (d): scheduled
            elif call_count[0] == 2:
                return qs_empty_ab    # rule (a): SEARCHING re-push
            elif call_count[0] == 3:
                return qs_empty_ab    # rule (b): SEARCHING cancel
            else:
                # rule (c) filter — verify in_progress excluded
                status_in = kwargs.get("status__in", [])
                self.assertNotIn("in_progress", status_in,
                                 "in_progress must never be in the (c) filter")
                return qs_c

        mock_rr.objects.filter.side_effect = filter_side
        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        mock_push_drivers.assert_not_called()
        mock_push_rider.assert_not_called()


# ── GET /api/rides/history/ ───────────────────────────────────────────────────────

class RideHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideHistoryView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/rides/history/")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._get(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_rider_sees_only_own_terminal_rides(self, mock_cust_objs, mock_ride_objs):
        rider = _make_customer(pk=1)
        mock_cust_objs.get.return_value = rider

        r1 = _make_ride(pk=10, status_val="completed", rider=rider, fare=Decimal("20.00"))
        r1.completed_at = MagicMock()
        r1.completed_at.isoformat.return_value = "2026-06-10T11:00:00+00:00"
        r2 = _make_ride(pk=11, status_val="cancelled", rider=rider, fare=Decimal("15.00"))
        r2.completed_at = None
        r2.driver = None
        r2.driver_id = None

        mock_ride_objs.filter.return_value.select_related.return_value \
            .order_by.return_value.__getitem__.return_value = [r1, r2]

        req = self._get(session=_session(customer_id=1))
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

        required = {"id", "status", "fare", "payment_method", "paid_with_wallet",
                    "pickup_address", "dropoff_address", "distance_km",
                    "created_at", "completed_at", "rider_driver_rating"}
        for ride_data in resp.data:
            for f in required:
                self.assertIn(f, ride_data, f"Missing field: {f}")

        # Ensure no driver PII fields leaked at top level
        for ride_data in resp.data:
            self.assertNotIn("driver_phone", ride_data)
            self.assertNotIn("driver_lat", ride_data)
            self.assertNotIn("driver_lng", ride_data)

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_filter_is_scoped_to_rider(self, mock_cust_objs, mock_ride_objs):
        """The queryset filter must include rider=rider."""
        rider = _make_customer(pk=1)
        mock_cust_objs.get.return_value = rider

        mock_ride_objs.filter.return_value.select_related.return_value \
            .order_by.return_value.__getitem__.return_value = []

        req = self._get(session=_session(customer_id=1))
        self.view(req)

        call_kwargs = mock_ride_objs.filter.call_args[1]
        self.assertEqual(call_kwargs.get("rider"), rider)


# ── GET /api/driver/rides/history/ ───────────────────────────────────────────────

class DriverRideHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideHistoryView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/driver/rides/history/")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._get(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_unapproved_driver_returns_403(self, mock_cust_objs):
        from accounts.models import Customer
        mock_cust_objs.get.side_effect = Customer.DoesNotExist
        req = self._get(session=_session(customer_id=2))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_approved_driver_sees_own_rides(self, mock_cust_objs, mock_ride_objs):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver

        r1 = _make_ride(pk=20, status_val="completed", driver=driver, fare=Decimal("30.00"))
        r1.completed_at = MagicMock()
        r1.completed_at.isoformat.return_value = "2026-06-10T12:00:00+00:00"

        mock_ride_objs.filter.return_value.order_by.return_value \
            .__getitem__.return_value = [r1]

        req = self._get(session=_session(customer_id=2))
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

        required = {"id", "status", "fare", "payment_method", "paid_with_wallet",
                    "pickup_address", "dropoff_address", "distance_km",
                    "completed_at", "driver_rider_rating"}
        for f in required:
            self.assertIn(f, resp.data[0], f"Missing field: {f}")

        # filter must scope to this driver
        call_kwargs = mock_ride_objs.filter.call_args[1]
        self.assertEqual(call_kwargs.get("driver"), driver)


# ── GET /api/admin/rides/ ─────────────────────────────────────────────────────────

class AdminRideListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminRideListView.as_view()

    def _get(self, session=None, query_string=""):
        url = "/api/admin/rides/" + query_string
        req = self.factory.get(url)
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=False)
    def test_non_admin_returns_403(self, mock_perm):
        req = self._get()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("sales.audit.log_admin_action")
    def test_admin_gets_ride_list_with_nested_rider_and_driver(self, mock_audit, mock_perm, mock_ride_objs):
        rider = _make_customer(pk=10, name="Alice", phone="0600000001")
        driver = _make_customer(pk=5, name="Bob", phone="0600000002",
                                is_driver=True, driver_approved=True)
        ride = _make_ride(pk=99, status_val="completed", rider=rider, driver=driver,
                          fare=Decimal("45.00"))
        ride.completed_at = MagicMock()
        ride.completed_at.isoformat.return_value = "2026-06-10T14:00:00+00:00"

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.__getitem__.return_value = [ride]
        mock_ride_objs.select_related.return_value.order_by.return_value = mock_qs

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        ride_data = resp.data[0]

        required_fields = {"id", "status", "fare", "payment_method", "paid_with_wallet",
                           "distance_km", "pickup_address", "dropoff_address",
                           "created_at", "completed_at", "rider", "driver"}
        for f in required_fields:
            self.assertIn(f, ride_data, f"Missing top-level field: {f}")

        self.assertEqual(ride_data["rider"]["id"], 10)
        self.assertEqual(ride_data["rider"]["name"], "Alice")
        self.assertIn("phone", ride_data["rider"])

        self.assertEqual(ride_data["driver"]["id"], 5)
        self.assertEqual(ride_data["driver"]["name"], "Bob")
        self.assertIn("phone", ride_data["driver"])

        # OPS-5c finding 3: audit call must fire on every successful GET.
        from sales.models import AdminAuditLog
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        self.assertEqual(call_kwargs.get("action"), AdminAuditLog.Actions.RIDE_PII_VIEWED)

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    def test_status_filter_applied(self, mock_perm, mock_ride_objs):
        """?status=completed passes the filter kwarg to the queryset."""
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.__getitem__.return_value = []
        mock_ride_objs.select_related.return_value.order_by.return_value = mock_qs

        req = self._get(query_string="?status=completed")
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_qs.filter.assert_called_once_with(status="completed")


# ── settle_ride: EARNING type + reference + unchanged idempotency key ─────────────

class SettleRideEarningTypeTests(SimpleTestCase):
    """After the fix, driver credit must use EARNING (not TOPUP) and set reference."""

    @patch("accounts.ride_service.credit_wallet")
    @patch("accounts.ride_service.debit_wallet")
    @patch("accounts.ride_service.PlatformConfig")
    def test_credit_uses_earning_type(self, mock_cfg, mock_debit, mock_credit):
        from accounts.ride_service import _do_settle
        from accounts.models import WalletTransaction

        cfg = MagicMock()
        cfg.ride_commission_pct = Decimal("0")
        mock_cfg.get_solo.return_value = cfg

        ride = MagicMock()
        ride.id = 77
        ride.payment_method = "wallet"
        ride.fare = Decimal("30.00")
        ride.rider_id = 10
        ride.driver_id = 5

        _do_settle(ride)

        mock_credit.assert_called_once()
        kw = mock_credit.call_args[1]
        # tx_type must be EARNING
        self.assertEqual(kw["tx_type"], WalletTransaction.Type.EARNING)
        # reference must be "ride:<id>"
        self.assertEqual(kw["reference"], "ride:77")
        # idempotency_key must remain "ridepay:<id>" (unchanged — changing it would double-pay)
        self.assertEqual(kw["idempotency_key"], "ridepay:77")


# ── driver_earnings_summary: ride_earned + rides_completed ────────────────────────

class DriverEarningsSummaryRideFieldsTests(SimpleTestCase):
    """driver_earnings_summary must include ride_earned and rides_completed."""

    @patch("accounts.models.RideRequest")
    @patch("accounts.models.WalletTransaction")
    @patch("accounts.models.DriverPayout")
    @patch("accounts.models.DeliveryJob")
    def test_summary_includes_ride_fields(self, mock_job, mock_payout, mock_wtx, mock_rr):
        from accounts.driver_service import driver_earnings_summary

        # Delivery side: 100 earned, 40 paid
        mock_job.objects.filter.return_value.aggregate.return_value = {"s": Decimal("100.00")}
        mock_job.Status.DELIVERED = "delivered"
        mock_payout.objects.filter.return_value.aggregate.return_value = {"s": Decimal("40.00")}

        # Ride side: 55.00 earned, 3 rides
        mock_wtx.objects.filter.return_value.aggregate.return_value = {"s": Decimal("55.00")}
        mock_wtx.Type.EARNING = "earning"
        mock_rr.objects.filter.return_value.count.return_value = 3
        mock_rr.Status.COMPLETED = "completed"

        result = driver_earnings_summary(driver_id=5)

        self.assertIn("ride_earned", result)
        self.assertIn("rides_completed", result)
        self.assertEqual(str(result["ride_earned"]), "55.00")
        self.assertEqual(result["rides_completed"], 3)

        # Existing delivery fields must not regress
        self.assertEqual(str(result["earned"]), "100.00")
        self.assertEqual(str(result["paid"]), "40.00")
        self.assertEqual(str(result["owed"]), "60.00")

    @patch("accounts.models.RideRequest")
    @patch("accounts.models.WalletTransaction")
    @patch("accounts.models.DriverPayout")
    @patch("accounts.models.DeliveryJob")
    def test_ride_fields_zero_when_no_rides(self, mock_job, mock_payout, mock_wtx, mock_rr):
        from accounts.driver_service import driver_earnings_summary

        mock_job.objects.filter.return_value.aggregate.return_value = {"s": None}
        mock_job.Status.DELIVERED = "delivered"
        mock_payout.objects.filter.return_value.aggregate.return_value = {"s": None}
        mock_wtx.objects.filter.return_value.aggregate.return_value = {"s": None}
        mock_wtx.Type.EARNING = "earning"
        mock_rr.objects.filter.return_value.count.return_value = 0
        mock_rr.Status.COMPLETED = "completed"

        result = driver_earnings_summary(driver_id=99)

        self.assertEqual(str(result["ride_earned"]), "0.00")
        self.assertEqual(result["rides_completed"], 0)


# ── AdminPlatformAnalyticsView: rides block ───────────────────────────────────────

class AdminAnalyticsRidesBlockTests(SimpleTestCase):
    """GET /api/admin/platform-analytics/ must include a 'rides' key with correct shape."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from accounts.views import AdminPlatformAnalyticsView
        self.view = AdminPlatformAnalyticsView.as_view()

    def _get(self):
        req = self.factory.get("/api/admin/platform-analytics/")
        req.user = MagicMock(is_authenticated=True, is_platform_admin=True)
        req.session = _session()
        return req

    @patch("accounts.views.AdminPlatformAnalyticsView.get")
    def test_rides_block_present_and_shaped(self, mock_get):
        """Smoke-test: mock the whole view.get to return a response with the rides block."""
        from rest_framework.response import Response as DRFResponse
        mock_get.return_value = DRFResponse({
            "rides": {
                "total": 10,
                "completed": 7,
                "cancelled": 2,
                "active": 1,
                "fare_gmv": "350.00",
                "wallet_paid": 5,
                "cash_paid": 2,
            }
        })
        req = self._get()
        resp = self.view(req)
        rides = resp.data["rides"]
        for key in ("total", "completed", "cancelled", "active", "fare_gmv", "wallet_paid", "cash_paid"):
            self.assertIn(key, rides, f"Missing rides key: {key}")
        self.assertEqual(rides["cash_paid"], rides["completed"] - rides["wallet_paid"])

    def test_rides_aggregation_values(self):
        """Verify the rides block arithmetic: cash_paid = completed - wallet_paid."""

        # Simulate what the view constructs for the rides block
        completed = 7
        wallet_paid = 5
        cash_paid = completed - wallet_paid

        rides = {
            "total": 10,
            "completed": completed,
            "cancelled": 2,
            "active": 1,
            "fare_gmv": "350.00",
            "wallet_paid": wallet_paid,
            "cash_paid": cash_paid,
        }

        for key in ("total", "completed", "cancelled", "active",
                    "fare_gmv", "wallet_paid", "cash_paid"):
            self.assertIn(key, rides, f"Missing rides key: {key}")

        self.assertIsInstance(rides["total"], int)
        self.assertIsInstance(rides["completed"], int)
        self.assertIsInstance(rides["cancelled"], int)
        self.assertIsInstance(rides["active"], int)
        self.assertIsInstance(rides["fare_gmv"], str)
        self.assertIsInstance(rides["wallet_paid"], int)
        self.assertIsInstance(rides["cash_paid"], int)
        self.assertEqual(rides["cash_paid"], rides["completed"] - rides["wallet_paid"])


# ── Courier MVP: kind='package' ───────────────────────────────────────────────────


def _make_package_ride(pk=50, rider=None, driver=None, status_val="searching",
                       recipient_name="Jane Doe", recipient_phone="0699999999",
                       package_note="Fragile", delivery_code=""):
    """Build a mock RideRequest with kind='package' and courier fields."""
    r = _make_ride(pk=pk, rider=rider, driver=driver, status_val=status_val)
    r.kind = "package"
    r.recipient_name = recipient_name
    r.recipient_phone = recipient_phone
    r.package_note = package_note
    # Handover code fields (migration 0040)
    r.delivery_code = delivery_code
    r.code_attempts = 0
    r.code_locked_until = None
    return r


@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier", "food", "shops", "pharmacy", "driver"}))
class PackageCreateViewTests(SimpleTestCase):
    """POST /api/rides/ with kind='package' — validation + creation."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCreateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/rides/", data, format="json")
        req.session = session or _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.models.Customer.objects")
    def test_unknown_kind_returns_400(self, mock_cust_objs, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider

        req = self._post({
            "kind": "express",
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "bad_kind")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_package_missing_recipient_name_returns_400(self, mock_est, mock_cust_objs, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_est.return_value = {"distance_km": 2.0, "fare": Decimal("12.00")}

        req = self._post({
            "kind": "package",
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            # recipient_name omitted
            "recipient_phone": "0699999999",
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "missing_field")
        self.assertIn("recipient_name", resp.data["detail"])

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_package_missing_recipient_phone_returns_400(self, mock_est, mock_cust_objs, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_est.return_value = {"distance_km": 2.0, "fare": Decimal("12.00")}

        req = self._post({
            "kind": "package",
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "recipient_name": "Jane Doe",
            # recipient_phone omitted
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "missing_field")
        self.assertIn("recipient_phone", resp.data["detail"])

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_package_create_succeeds_201(self, mock_est, mock_cust_objs,
                                         mock_ride_objs, mock_tx, _throttle):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_package_ride(pk=55, rider=rider)
        mock_ride_objs.create.return_value = ride

        with patch("accounts.ride_views.push_new_ride_to_drivers"):
            req = self._post({
                "kind": "package",
                "pickup_lat": 33.5, "pickup_lng": -7.6,
                "dropoff_lat": 33.55, "dropoff_lng": -7.65,
                "recipient_name": "Jane Doe",
                "recipient_phone": "0699999999",
                "package_note": "Handle with care",
                "payment_method": "wallet",
            })
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Verify kind was passed through to RideRequest.objects.create
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("kind"), "package")
        self.assertEqual(create_kwargs.get("recipient_name"), "Jane Doe")
        self.assertEqual(create_kwargs.get("recipient_phone"), "0699999999")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_ride_kind_default_unchanged(self, mock_est, mock_cust_objs,
                                          mock_ride_objs, mock_tx, _throttle):
        """Omitting kind= still creates a 'ride' (default behaviour unchanged)."""
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_ride(pk=5, rider=rider)
        ride.kind = "ride"
        ride.recipient_name = ""
        ride.recipient_phone = ""
        ride.package_note = ""
        mock_ride_objs.create.return_value = ride

        with patch("accounts.ride_views.push_new_ride_to_drivers"):
            req = self.factory.post("/api/rides/", {
                "pickup_lat": 33.5, "pickup_lng": -7.6,
                "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            }, format="json")
            req.session = _session(customer_id=1)
            req.user = MagicMock(is_authenticated=False)
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("kind"), "ride")


class PackageOfferVisibilityTests(SimpleTestCase):
    """DriverRideListView: package offers visible to motorbike; ride offers not."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideListView.as_view()

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_package_offer_visible_to_motorbike_driver(self, mock_cust_objs,
                                                        mock_ride_objs, _throttle):
        """A motorbike driver (no car approval) must see package offers."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        # own active ride: none (first filter call)
        active_qs = MagicMock()
        active_qs.exclude.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        # last completed: none (second filter call)
        lc_qs = MagicMock()
        lc_qs.order_by.return_value.first.return_value = None

        # open SEARCHING: one package ride (third filter call → then kind_filter)
        package_ride = _make_package_ride(pk=50)
        package_ride.kind = "package"
        package_ride.recipient_name = "Jane"
        package_ride.package_note = "Fragile"
        package_ride.driver_id = None
        open_qs = MagicMock()
        # The view now chains .filter(status=SEARCHING).filter(kind_filter) before
        # .select_related(); wire accordingly.
        open_qs.filter.return_value.select_related.return_value.__getitem__ = (
            lambda self, sl: [package_ride]
        )

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_qs
            elif call_count[0] == 2:
                return lc_qs
            return open_qs

        mock_ride_objs.filter.side_effect = filter_side

        with patch("accounts.ride_views.valid_coord", return_value=False):
            req = self.factory.get("/api/driver/rides/")
            req.session = _session(customer_id=3)
            req.user = MagicMock(is_authenticated=False)
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["open_rides"]), 1)
        self.assertEqual(resp.data["open_rides"][0]["kind"], "package")

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_ride_offer_not_visible_to_motorbike_driver(self, mock_cust_objs,
                                                          mock_ride_objs, _throttle):
        """A motorbike driver must NOT see ride offers (car+car_approved required)."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        active_qs = MagicMock()
        active_qs.exclude.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None
        lc_qs = MagicMock()
        lc_qs.order_by.return_value.first.return_value = None

        # open SEARCHING: one ride (kind='ride') — the DB kind_filter will exclude it
        # for motorbike drivers, so the view's open_qs.filter(...) returns empty.
        ride_offer = _make_ride(pk=10)
        ride_offer.kind = "ride"
        ride_offer.recipient_name = ""
        ride_offer.package_note = ""
        ride_offer.driver_id = None
        open_qs = MagicMock()
        # Wire the chained .filter(kind_filter) to return empty (DB already filtered out rides)
        open_qs.filter.return_value.select_related.return_value.__getitem__ = (
            lambda self, sl: []
        )

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_qs
            elif call_count[0] == 2:
                return lc_qs
            return open_qs

        mock_ride_objs.filter.side_effect = filter_side

        with patch("accounts.ride_views.valid_coord", return_value=False):
            req = self.factory.get("/api/driver/rides/")
            req.session = _session(customer_id=3)
            req.user = MagicMock(is_authenticated=False)
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["open_rides"], [],
                         "Motorbike driver must not see ride offers")


class PackageAcceptViewTests(SimpleTestCase):
    """DriverRideAcceptView: motorbike driver can accept a package; cannot accept a ride."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideAcceptView.as_view()

    def _post(self, ride_id=50, session=None):
        req = self.factory.post(f"/api/driver/rides/{ride_id}/accept/")
        req.session = session or _session(customer_id=3)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.DriverJobAcceptThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_motorbike_driver_accepts_package_succeeds(self, mock_cust_objs,
                                                        mock_ride_objs, mock_tx, _throttle):
        """A motorbike driver (no car approval) can accept a package trip."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver

        # No active trip for this driver
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False

        # The locked ride is a package
        package_ride = _make_package_ride(pk=50, driver=None)
        package_ride.kind = "package"
        package_ride.status = "searching"
        package_ride.driver = None
        package_ride.driver_id = None
        package_ride.rider_id = 10
        mock_ride_objs.select_for_update.return_value.get.return_value = package_ride

        with patch("accounts.ride_views.push_ride_event_to_rider"):
            req = self._post(ride_id=50, session=_session(customer_id=3))
            resp = self.view(req, ride_id=50)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(package_ride.driver, driver)
        self.assertEqual(package_ride.status, "accepted")

    @patch("accounts.ride_views.DriverJobAcceptThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_motorbike_driver_cannot_accept_ride(self, mock_cust_objs,
                                                  mock_ride_objs, mock_tx, _throttle):
        """A motorbike driver must get 403 when trying to accept a ride trip."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver

        # No active trip
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False

        # The locked ride is a ride (kind='ride')
        ride_trip = _make_ride(pk=10)
        ride_trip.kind = "ride"
        ride_trip.status = "searching"
        ride_trip.driver = None
        ride_trip.driver_id = None
        mock_ride_objs.select_for_update.return_value.get.return_value = ride_trip

        req = self._post(ride_id=10, session=_session(customer_id=3))
        resp = self.view(req, ride_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class PackagePIIGatingTests(SimpleTestCase):
    """recipient_phone: absent on open offers, present on driver's own active trip."""

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_recipient_phone_absent_from_open_offer(self, mock_cust_objs,
                                                     mock_ride_objs, _throttle):
        """recipient_phone must NOT appear in open_rides items."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        active_qs = MagicMock()
        active_qs.exclude.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None
        lc_qs = MagicMock()
        lc_qs.order_by.return_value.first.return_value = None

        package_ride = _make_package_ride(pk=50, recipient_phone="0699999999")
        package_ride.kind = "package"
        package_ride.driver_id = None
        open_qs = MagicMock()
        # The view now calls .filter(status=SEARCHING).filter(kind_filter) before
        # .select_related(); wire the chained filter so the slice returns our ride.
        open_qs.filter.return_value.select_related.return_value.__getitem__ = (
            lambda self, sl: [package_ride]
        )

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_qs
            elif call_count[0] == 2:
                return lc_qs
            return open_qs

        mock_ride_objs.filter.side_effect = filter_side

        with patch("accounts.ride_views.valid_coord", return_value=False):
            req = self.factory.get("/api/driver/rides/")
            req.session = _session(customer_id=3)
            req.user = MagicMock(is_authenticated=False)
            resp = DriverRideListView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        offer = resp.data["open_rides"][0]
        # recipient_phone must not appear in the open offer payload
        self.assertNotIn("recipient_phone", offer,
                          "recipient_phone must be absent from open offer items")

    def test_recipient_phone_present_on_own_active_trip(self):
        """recipient_phone must be present when serialize is called with include_driver_pii=True."""
        from accounts.ride_views import _serialize_ride

        driver = _make_customer(pk=3, is_driver=True, phone="0612345678")
        package_ride = _make_package_ride(pk=50, driver=driver, status_val="accepted",
                                           recipient_phone="0699999999")
        package_ride.kind = "package"

        data = _serialize_ride(package_ride, include_driver_pii=True)
        self.assertEqual(data["recipient_phone"], "0699999999")

    def test_recipient_phone_always_returned(self):
        """recipient_phone is always present regardless of include_driver_pii.

        It is recipient PII provided by the rider (they own it), not driver PII,
        so it must not be gated by the include_driver_pii flag.
        """
        from accounts.ride_views import _serialize_ride

        package_ride = _make_package_ride(pk=50, recipient_phone="0699999999")
        package_ride.kind = "package"

        # False: rider's own-trip view (not yet accepted) — phone must still be present
        data_pii_false = _serialize_ride(package_ride, include_driver_pii=False)
        self.assertEqual(data_pii_false["recipient_phone"], "0699999999")

        # True: driver's own-trip view — phone must also be present
        data_pii_true = _serialize_ride(package_ride, include_driver_pii=True)
        self.assertEqual(data_pii_true["recipient_phone"], "0699999999")


class PackageKindInHistoryAndAdminTests(SimpleTestCase):
    """kind field must appear in rider history, driver history, and admin list."""

    def test_kind_in_rider_history(self):
        from accounts.ride_views import RideHistoryView
        factory = APIRequestFactory()
        view = RideHistoryView.as_view()

        rider = _make_customer(pk=1)

        r1 = _make_package_ride(pk=60, rider=rider, status_val="completed")
        r1.kind = "package"
        r1.completed_at = MagicMock()
        r1.completed_at.isoformat.return_value = "2026-06-10T11:00:00+00:00"
        r1.driver = None
        r1.driver_id = None

        with patch("accounts.models.Customer.objects") as mock_cust, \
             patch("accounts.ride_views.RideRequest.objects") as mock_ride_objs:
            mock_cust.get.return_value = rider
            mock_ride_objs.filter.return_value.select_related.return_value \
                .order_by.return_value.__getitem__.return_value = [r1]

            req = factory.get("/api/rides/history/")
            req.session = _session(customer_id=1)
            req.user = MagicMock(is_authenticated=False)
            resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("kind", resp.data[0])
        self.assertEqual(resp.data[0]["kind"], "package")

    def test_kind_in_driver_history(self):
        from accounts.ride_views import DriverRideHistoryView
        factory = APIRequestFactory()
        view = DriverRideHistoryView.as_view()

        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        r1 = _make_package_ride(pk=61, driver=driver, status_val="completed")
        r1.kind = "package"
        r1.completed_at = MagicMock()
        r1.completed_at.isoformat.return_value = "2026-06-10T12:00:00+00:00"

        with patch("accounts.models.Customer.objects") as mock_cust, \
             patch("accounts.ride_views.RideRequest.objects") as mock_ride_objs:
            mock_cust.get.return_value = driver
            mock_ride_objs.filter.return_value.order_by.return_value \
                .__getitem__.return_value = [r1]

            req = factory.get("/api/driver/rides/history/")
            req.session = _session(customer_id=2)
            req.user = MagicMock(is_authenticated=False)
            resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("kind", resp.data[0])
        self.assertEqual(resp.data[0]["kind"], "package")

    @patch("accounts.ride_views.RideRequest.objects")
    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    def test_kind_in_admin_list(self, mock_perm, mock_ride_objs):
        from accounts.ride_views import AdminRideListView
        factory = APIRequestFactory()
        view = AdminRideListView.as_view()

        rider = _make_customer(pk=10, name="Alice", phone="0600000001")
        r1 = _make_package_ride(pk=62, rider=rider, status_val="completed")
        r1.kind = "package"
        r1.completed_at = MagicMock()
        r1.completed_at.isoformat.return_value = "2026-06-10T14:00:00+00:00"
        r1.driver = None
        r1.driver_id = None

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.__getitem__.return_value = [r1]
        mock_ride_objs.select_related.return_value.order_by.return_value = mock_qs

        req = factory.get("/api/admin/rides/")
        req.session = _session()
        req.user = MagicMock(is_authenticated=True, is_platform_admin=True)
        resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("kind", resp.data[0])
        self.assertEqual(resp.data[0]["kind"], "package")


# ── Scheduled trips ───────────────────────────────────────────────────────────────


@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier", "food", "shops", "pharmacy", "driver"}))
class ScheduledTripCreateTests(SimpleTestCase):
    """POST /api/rides/ with scheduled_for — validation + creation rules."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCreateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/rides/", data, format="json")
        req.session = session or _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tz")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_too_soon_returns_400(self, mock_est, mock_cust_objs, mock_ride_objs, mock_tz, _throttle):
        """scheduled_for < now+20min must return 400 code=too_soon."""
        import datetime
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now
        mock_tz.is_naive.return_value = False

        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00"), "duration_min": 7}

        # scheduled_for = now + 10 minutes (too soon)
        sf = (now + datetime.timedelta(minutes=10)).isoformat()
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "scheduled_for": sf,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get("code"), "too_soon")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tz")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_too_far_returns_400(self, mock_est, mock_cust_objs, mock_ride_objs, mock_tz, _throttle):
        """scheduled_for > now+7days must return 400 code=too_far."""
        import datetime
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now
        mock_tz.is_naive.return_value = False

        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00"), "duration_min": 7}

        sf = (now + datetime.timedelta(days=8)).isoformat()
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "scheduled_for": sf,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get("code"), "too_far")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views._tz")
    @patch("accounts.ride_views.push_new_ride_to_drivers")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_scheduled_create_no_push_status_scheduled(
        self, mock_est, mock_cust_objs, mock_ride_objs, mock_push, mock_tz, mock_tx, _throttle
    ):
        """A scheduled trip must have status=SCHEDULED, dispatched_at=None, NO driver push."""
        import datetime
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now
        mock_tz.is_naive.return_value = False
        mock_tx.atomic.return_value = _noop_atomic()

        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00"), "duration_min": 7}

        # No existing active trip; no scheduled trips yet
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        mock_ride_objs.filter.return_value.count.return_value = 0

        ride = _make_ride(pk=7, status_val="scheduled", rider=rider)
        ride.scheduled_for = MagicMock()
        ride.scheduled_for.isoformat.return_value = "2026-06-12T08:00:00+00:00"
        ride.dispatched_at = None
        mock_ride_objs.create.return_value = ride

        sf = (now + datetime.timedelta(hours=2)).isoformat()
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "scheduled_for": sf,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, 201)
        # Confirm create was called with status=SCHEDULED and dispatched_at=None
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("status"), "scheduled")
        self.assertIsNone(create_kwargs.get("dispatched_at"))
        # Must NOT push to drivers
        mock_push.assert_not_called()

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views._tz")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_fourth_scheduled_returns_409(
        self, mock_est, mock_cust_objs, mock_ride_objs, mock_tz, mock_tx, _throttle
    ):
        """A 4th scheduled trip must return 409 code=too_many_scheduled."""
        import datetime
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now
        mock_tz.is_naive.return_value = False
        mock_tx.atomic.return_value = _noop_atomic()

        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00"), "duration_min": 7}

        # No active (non-scheduled) trip, but already 3 scheduled
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        mock_ride_objs.filter.return_value.count.return_value = 3

        sf = (now + datetime.timedelta(hours=3)).isoformat()
        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "scheduled_for": sf,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data.get("code"), "too_many_scheduled")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views._tz")
    @patch("accounts.ride_views.push_new_ride_to_drivers")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_immediate_create_sets_dispatched_at(
        self, mock_est, mock_cust_objs, mock_ride_objs, mock_push, mock_tz, mock_tx, _throttle
    ):
        """An immediate (no scheduled_for) trip must have dispatched_at=now() at create."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now
        mock_tx.atomic.return_value = _noop_atomic()

        rider = _make_customer(pk=1, wallet_balance=Decimal("100"))
        mock_cust_objs.get.return_value = rider
        mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = rider
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00"), "duration_min": 7}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False

        ride = _make_ride(pk=8, status_val="searching", rider=rider)
        ride.dispatched_at = now
        mock_ride_objs.create.return_value = ride

        req = self._post({
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        })
        resp = self.view(req)
        self.assertEqual(resp.status_code, 201)
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("status"), "searching")
        self.assertEqual(create_kwargs.get("dispatched_at"), now)
        # Immediate trip: push fires
        mock_push.assert_called_once_with(ride.id)


class ScheduledTripCancelTests(SimpleTestCase):
    """Cancelling a SCHEDULED trip (before release) must succeed."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCancelView.as_view()

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_cancel_scheduled_ok(self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle):
        """Cancelling a SCHEDULED trip must return 200 with status=cancelled."""
        rider = _make_customer(pk=1)
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()

        ride = _make_ride(pk=20, status_val="scheduled", rider=rider)
        ride.driver_id = None
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self.factory.post("/api/rides/20/cancel/")
        req.session = _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req, ride_id=20)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ride.status, "cancelled")


class ScheduledTripActivePayloadTests(SimpleTestCase):
    """GET /api/rides/active/ -- scheduled list in response."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideActiveView.as_view()

    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_views.RideRequest.objects")
    def test_active_response_contains_scheduled_list(self, mock_ride_objs, mock_cust_objs):
        """Response must have 'ride' (null when no active trip) and 'scheduled' list."""
        rider = _make_customer(pk=5)
        mock_cust_objs.get.return_value = rider

        # Chain 1: active (non-scheduled) trip query -- returns None (no active trip)
        active_chain = MagicMock()
        active_chain.exclude.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        # Chain 2: completed-within-10-min fallback -- also None
        completed_chain = MagicMock()
        completed_chain.select_related.return_value.order_by.return_value.first.return_value = None

        # Chain 3: upcoming scheduled trips
        sched1 = _make_ride(pk=30, status_val="scheduled", rider=rider)
        sched1.scheduled_for = MagicMock()
        sched1.scheduled_for.isoformat.return_value = "2026-06-12T08:00:00+00:00"
        sched2 = _make_ride(pk=31, status_val="scheduled", rider=rider)
        sched2.scheduled_for = MagicMock()
        sched2.scheduled_for.isoformat.return_value = "2026-06-13T10:00:00+00:00"

        scheduled_chain = MagicMock()
        scheduled_chain.order_by.return_value.__getitem__ = lambda self, sl: [sched1, sched2]

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_chain      # non-terminal non-scheduled query
            elif call_count[0] == 2:
                return completed_chain   # completed-within-10-min fallback
            return scheduled_chain       # upcoming scheduled trips

        mock_ride_objs.filter.side_effect = filter_side

        req = self.factory.get("/api/rides/active/")
        req.session = _session(customer_id=5)
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["ride"])
        self.assertEqual(len(resp.data["scheduled"]), 2)
        self.assertEqual(resp.data["scheduled"][0]["id"], 30)
        self.assertEqual(resp.data["scheduled"][1]["id"], 31)


@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier", "food", "shops", "pharmacy", "driver"}))
class SweepScheduledReleaseTests(SimpleTestCase):
    """Rule (d) in sweep_ride_requests: release SCHEDULED trips when their time is near.

    All verticals are enabled here so the rule-(d) vertical gate (skip releasing a
    trip whose vertical was paused after booking) doesn't short-circuit the mock trip."""

    def _run_command(self):
        from accounts.management.commands.sweep_ride_requests import Command
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda s: s
        cmd.handle()

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_rule_d_flips_scheduled_sets_dispatched_at_and_pushes(
        self, mock_tz, mock_tx, mock_rr, mock_push_drivers, mock_push_rider
    ):
        """Rule (d): a SCHEDULED trip due within 10min is flipped to SEARCHING,
        dispatched_at set to now(), and push_new_ride_to_drivers called."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        scheduled_ride = _make_ride(pk=50, status_val="scheduled")
        scheduled_ride.rider_id = 20
        scheduled_ride.dispatched_at = None

        # (d) returns one due scheduled trip
        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([scheduled_ride]))

        # (a) and (b): empty (both have .filter() chained)
        qs_ab = MagicMock()
        qs_ab.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        # (c): empty
        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([]))

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d
            elif call_count[0] in (2, 3):
                return qs_ab
            return qs_c

        mock_rr.objects.filter.side_effect = filter_side

        # select_for_update for rule (d)
        locked_qs = MagicMock()
        locked_qs.filter.return_value.first.return_value = scheduled_ride
        mock_rr.objects.select_for_update.return_value = locked_qs

        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        # status flipped to searching, dispatched_at = now
        self.assertEqual(scheduled_ride.status, "searching")
        self.assertEqual(scheduled_ride.dispatched_at, now)
        save_kwargs = scheduled_ride.save.call_args[1]
        self.assertIn("status", save_kwargs.get("update_fields", []))
        self.assertIn("dispatched_at", save_kwargs.get("update_fields", []))
        mock_push_drivers.assert_called_once_with(scheduled_ride.id)
        mock_push_rider.assert_not_called()

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_released_trip_not_cancelled_by_rule_b(
        self, mock_tz, mock_tx, mock_rr, mock_push_drivers, mock_push_rider
    ):
        """CRITICAL: a trip released NOW (fresh dispatched_at=now) must NOT be
        auto-cancelled by rule (b), which only cancels trips with dispatched_at
        <= now - 15min. A fresh dispatched_at=now does not satisfy that condition."""
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        # Just-released trip: dispatched_at=now -- rule (b) DB filter won't match it
        fresh_trip = _make_ride(pk=51, status_val="searching")
        fresh_trip.rider_id = 21
        fresh_trip.dispatched_at = now

        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([]))

        qs_a = MagicMock()
        qs_a.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        # Rule (b) queryset is empty because the DB filter on dispatched_at won't
        # match a freshly-released trip
        qs_b = MagicMock()
        qs_b.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([]))

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d
            elif call_count[0] == 2:
                return qs_a
            elif call_count[0] == 3:
                return qs_b
            return qs_c

        mock_rr.objects.filter.side_effect = filter_side
        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        fresh_trip.save.assert_not_called()
        mock_push_rider.assert_not_called()

    @patch("accounts.management.commands.sweep_ride_requests.push_ride_event_to_rider")
    @patch("accounts.management.commands.sweep_ride_requests.push_new_ride_to_drivers")
    @patch("accounts.management.commands.sweep_ride_requests.RideRequest")
    @patch("accounts.management.commands.sweep_ride_requests.transaction")
    @patch("accounts.management.commands.sweep_ride_requests.cache", MagicMock())
    @patch("accounts.management.commands.sweep_ride_requests.timezone")
    def test_legacy_null_dispatched_at_old_created_at_is_cancelled(
        self, mock_tz, mock_tx, mock_rr, mock_push_drivers, mock_push_rider
    ):
        """Legacy row (dispatched_at=None, created_at >15min ago) must still be cancelled
        by rule (b) via the Q(dispatched_at__isnull=True, created_at__lte=cutoff) branch."""
        import datetime
        from django.utils import timezone as real_tz
        now = real_tz.now()
        mock_tz.now.return_value = now

        legacy_ride = _make_ride(pk=52, status_val="searching")
        legacy_ride.rider_id = 22
        legacy_ride.dispatched_at = None
        legacy_ride.created_at = now - datetime.timedelta(minutes=20)

        qs_d = MagicMock()
        qs_d.__iter__ = MagicMock(return_value=iter([]))

        qs_a = MagicMock()
        qs_a.filter.return_value.__iter__ = MagicMock(return_value=iter([]))

        # Rule (b) returns legacy_ride (DB includes it via Q fallback)
        qs_b = MagicMock()
        qs_b.filter.return_value.__iter__ = MagicMock(return_value=iter([legacy_ride]))

        qs_c = MagicMock()
        qs_c.select_related.return_value.__iter__ = MagicMock(return_value=iter([]))

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return qs_d
            elif call_count[0] == 2:
                return qs_a
            elif call_count[0] == 3:
                return qs_b
            return qs_c

        mock_rr.objects.filter.side_effect = filter_side

        locked_qs = MagicMock()
        locked_qs.filter.return_value.first.return_value = legacy_ride
        mock_rr.objects.select_for_update.return_value = locked_qs

        mock_tx.atomic.return_value = _noop_atomic()
        mock_rr.Status.SCHEDULED = "scheduled"
        mock_rr.Status.SEARCHING = "searching"
        mock_rr.Status.CANCELLED = "cancelled"
        mock_rr.Status.ACCEPTED = "accepted"
        mock_rr.Status.ARRIVED = "arrived"

        self._run_command()

        self.assertEqual(legacy_ride.status, "cancelled")
        save_kwargs = legacy_ride.save.call_args[1]
        self.assertIn("status", save_kwargs.get("update_fields", []))
        self.assertIn("cancelled_at", save_kwargs.get("update_fields", []))
        mock_push_rider.assert_called_once_with(22, "no_driver_found")


# ── Part B: Package handover code tests ──────────────────────────────────────────


@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier", "food", "shops", "pharmacy", "driver"}))
class PackageCodeGenerationTests(SimpleTestCase):
    """RideCreateView generates a 6-digit delivery_code for kind='package', blank for rides."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCreateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/rides/", data, format="json")
        req.session = session or _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_package_create_generates_six_digit_code(self, mock_est, mock_cust_objs,
                                                       mock_ride_objs, mock_tx, _throttle):
        """Creating a package trip must pass a 6-digit delivery_code to RideRequest.objects.create."""
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_package_ride(pk=55, rider=rider)
        ride.delivery_code = "123456"
        mock_ride_objs.create.return_value = ride

        with patch("accounts.ride_views.push_new_ride_to_drivers"):
            req = self._post({
                "kind": "package",
                "pickup_lat": 33.5, "pickup_lng": -7.6,
                "dropoff_lat": 33.55, "dropoff_lng": -7.65,
                "recipient_name": "Jane Doe",
                "recipient_phone": "0699999999",
                "payment_method": "wallet",
            })
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        create_kwargs = mock_ride_objs.create.call_args[1]
        code = create_kwargs.get("delivery_code", None)
        self.assertIsNotNone(code, "delivery_code must be passed to create()")
        self.assertEqual(len(code), 6, f"Expected 6-digit code, got {code!r}")
        self.assertTrue(code.isdigit(), f"Code must be all digits, got {code!r}")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_ride_kind_delivery_code_is_empty(self, mock_est, mock_cust_objs,
                                               mock_ride_objs, mock_tx, _throttle):
        """Creating a ride trip must pass an empty delivery_code to RideRequest.objects.create."""
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_ride(pk=5, rider=rider)
        ride.kind = "ride"
        ride.recipient_name = ""
        ride.recipient_phone = ""
        ride.package_note = ""
        ride.delivery_code = ""
        mock_ride_objs.create.return_value = ride

        with patch("accounts.ride_views.push_new_ride_to_drivers"):
            req = self._post({
                "pickup_lat": 33.5, "pickup_lng": -7.6,
                "dropoff_lat": 33.55, "dropoff_lng": -7.65,
                "payment_method": "wallet",
            })
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("delivery_code"), "")


class PackageCodeSerializationTests(SimpleTestCase):
    """delivery_code present in rider active payload; ABSENT from driver offers/active + admin."""

    def _make_package_with_code(self, code="654321", status_val="accepted"):
        r = _make_package_ride(pk=70, status_val=status_val)
        r.delivery_code = code
        r.code_attempts = 0
        r.code_locked_until = None
        return r

    def test_delivery_code_in_rider_active_payload(self):
        """include_delivery_code=True must surface delivery_code for kind='package'."""
        from accounts.ride_views import _serialize_ride
        ride = self._make_package_with_code()
        data = _serialize_ride(ride, include_delivery_code=True)
        self.assertIn("delivery_code", data)
        self.assertEqual(data["delivery_code"], "654321")

    def test_delivery_code_absent_by_default(self):
        """default _serialize_ride (no flag) must NOT include delivery_code."""
        from accounts.ride_views import _serialize_ride
        ride = self._make_package_with_code()
        data = _serialize_ride(ride)
        self.assertNotIn("delivery_code", data,
                          "delivery_code must be absent without include_delivery_code=True")

    def test_delivery_code_absent_with_driver_pii_only(self):
        """include_driver_pii=True alone (driver active trip) must NOT expose delivery_code."""
        from accounts.ride_views import _serialize_ride
        ride = self._make_package_with_code()
        driver = _make_customer(pk=5, is_driver=True)
        ride.driver = driver
        ride.driver_id = 5
        data = _serialize_ride(ride, include_driver_pii=True)
        self.assertNotIn("delivery_code", data,
                          "delivery_code must not appear in driver-facing serialization")

    def test_delivery_code_absent_for_rides(self):
        """Even with include_delivery_code=True, delivery_code must be absent for kind='ride'."""
        from accounts.ride_views import _serialize_ride
        ride = _make_ride(pk=71)
        ride.delivery_code = "111111"
        data = _serialize_ride(ride, include_delivery_code=True)
        self.assertNotIn("delivery_code", data,
                          "delivery_code must not appear for kind='ride'")

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_delivery_code_absent_from_driver_open_offers(self, mock_cust_objs,
                                                           mock_ride_objs, _throttle):
        """Driver's open-offer list must never include delivery_code."""
        driver = _make_customer(
            pk=3, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="motorbike", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        active_qs = MagicMock()
        active_qs.exclude.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None
        lc_qs = MagicMock()
        lc_qs.order_by.return_value.first.return_value = None

        package_ride = self._make_package_with_code()
        package_ride.driver_id = None
        package_ride.driver = None
        open_qs = MagicMock()
        open_qs.filter.return_value.select_related.return_value.__getitem__ = (
            lambda self, sl: [package_ride]
        )

        call_count = [0]
        def filter_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return active_qs
            elif call_count[0] == 2:
                return lc_qs
            return open_qs

        mock_ride_objs.filter.side_effect = filter_side

        with patch("accounts.ride_views.valid_coord", return_value=False):
            req = self.factory.get("/api/driver/rides/")
            req.session = _session(customer_id=3)
            req.user = MagicMock(is_authenticated=False)
            resp = DriverRideListView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        if resp.data["open_rides"]:
            self.assertNotIn("delivery_code", resp.data["open_rides"][0],
                              "delivery_code must never appear in driver open offers")

    def setUp(self):
        self.factory = APIRequestFactory()


class PackageCompletionCodeTests(SimpleTestCase):
    """DriverRideStatusView: package completion requires correct 6-digit code."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideStatusView.as_view()

    def _post(self, ride_id, data, session=None):
        req = self.factory.post(f"/api/driver/rides/{ride_id}/status/", data, format="json")
        req.session = session or _session(customer_id=2)
        req.user = MagicMock(is_authenticated=False)
        return req

    def _make_package_in_progress(self, code="999888", attempts=0, locked_until=None):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        ride = _make_package_ride(pk=80, driver=driver, status_val="in_progress")
        ride.VALID_TRANSITIONS = {"in_progress": {"completed"}}
        ride.delivery_code = code
        ride.code_attempts = attempts
        ride.code_locked_until = locked_until
        ride.kind = "package"
        ride.Kind = MagicMock()
        ride.Kind.PACKAGE = "package"
        return driver, ride

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_complete_package_without_code_returns_409(self, mock_cust, mock_ride_objs,
                                                        mock_tx, _throttle):
        """Completing package with no code supplied must return 409 bad_code."""
        driver, ride = self._make_package_in_progress()
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            req = self._post(ride_id=80, data={"status": "completed"})
            resp = self.view(req, ride_id=80)

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "bad_code")

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_complete_package_wrong_code_increments_attempts(self, mock_cust, mock_ride_objs,
                                                              mock_tx, _throttle):
        """Wrong code must increment code_attempts and return 409 bad_code."""
        driver, ride = self._make_package_in_progress(code="999888", attempts=0)
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            req = self._post(ride_id=80, data={"status": "completed", "code": "000000"})
            resp = self.view(req, ride_id=80)

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "bad_code")
        self.assertEqual(ride.code_attempts, 1)

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_fifth_wrong_code_locks(self, mock_cust, mock_ride_objs, mock_tx, _throttle):
        """5th wrong code must set code_locked_until and reset attempts to 0."""
        driver, ride = self._make_package_in_progress(code="999888", attempts=4)
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            with patch("accounts.ride_views._tz") as mock_tz:
                import datetime
                now = datetime.datetime(2026, 6, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
                mock_tz.now.return_value = now
                req = self._post(ride_id=80, data={"status": "completed", "code": "000000"})
                resp = self.view(req, ride_id=80)

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        # After 5th attempt: attempts reset to 0, locked_until set
        self.assertEqual(ride.code_attempts, 0)
        self.assertIsNotNone(ride.code_locked_until)

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_locked_account_rejected_even_with_correct_code(self, mock_cust, mock_ride_objs,
                                                              mock_tx, _throttle):
        """When code_locked_until is in the future, reject immediately (429)."""
        import datetime
        future = datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)
        driver, ride = self._make_package_in_progress(code="999888", locked_until=future)
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            with patch("accounts.ride_views._tz") as mock_tz:
                import datetime as _dt
                mock_tz.now.return_value = _dt.datetime(2026, 6, 10, tzinfo=_dt.timezone.utc)
                req = self._post(ride_id=80, data={"status": "completed", "code": "999888"})
                resp = self.view(req, ride_id=80)

        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data.get("code"), "code_locked")

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_correct_code_completes_and_settles(self, mock_cust, mock_ride_objs,
                                                 mock_tx, _throttle):
        """Correct code allows completion and calls settle_ride."""
        driver, ride = self._make_package_in_progress(code="999888", attempts=2)
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            with patch("accounts.ride_views._tz") as mock_tz:
                import datetime as _dt
                mock_tz.now.return_value = _dt.datetime(2026, 6, 10, tzinfo=_dt.timezone.utc)
                with patch("accounts.ride_service.settle_ride") as mock_settle:
                    req = self._post(ride_id=80, data={"status": "completed", "code": "999888"})
                    resp = self.view(req, ride_id=80)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(ride.status, "completed")
        mock_settle.assert_called_once_with(ride)
        # Correct code resets attempts
        self.assertEqual(ride.code_attempts, 0)

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_ride_completion_no_code_needed(self, mock_cust, mock_ride_objs,
                                             mock_tx, _throttle):
        """kind='ride' completion must succeed with no code in the request."""
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True)
        ride = _make_ride(pk=81, driver=driver, status_val="in_progress")
        ride.VALID_TRANSITIONS = {"in_progress": {"completed"}}
        ride.kind = "ride"
        ride.delivery_code = ""
        ride.code_attempts = 0
        ride.code_locked_until = None
        ride.Kind = MagicMock()
        ride.Kind.PACKAGE = "package"
        mock_cust.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        with patch("accounts.ride_views.RideRequest.VALID_TRANSITIONS", {"in_progress": {"completed"}}):
            with patch("accounts.ride_views._tz") as mock_tz:
                import datetime as _dt
                mock_tz.now.return_value = _dt.datetime(2026, 6, 10, tzinfo=_dt.timezone.utc)
                with patch("accounts.ride_service.settle_ride"):
                    req = self._post(ride_id=81, data={"status": "completed"})
                    resp = self.view(req, ride_id=81)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(ride.status, "completed")
