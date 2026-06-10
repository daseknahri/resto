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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.ride_views import (
    RideEstimateView,
    RideCreateView,
    RideActiveView,
    RideCancelView,
    RideRateView,
    DriverRideListView,
    DriverRideAcceptView,
    DriverRideStatusView,
    DriverDocUploadView,
    DriverRateRideView,
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
    r.TERMINAL_STATUSES = {"completed", "cancelled"}
    r.is_terminal = status_val in {"completed", "cancelled"}
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
    @patch("accounts.models.Customer.objects")
    def test_non_car_driver_returns_403(self, mock_cust_objs, _throttle):
        driver = _make_customer(pk=2, is_driver=True, driver_approved=True,
                                is_driver_online=True, driver_vehicle_type="motorbike")
        mock_cust_objs.get.return_value = driver

        with patch("accounts.ride_views._tx") as mock_tx:
            mock_tx.atomic.return_value = _noop_atomic()
            mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver
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
        from accounts.models import WalletTransaction

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
        # The query for non-terminal returns this ride
        mock_ride_objs.filter.return_value.exclude.return_value.select_related.return_value.order_by.return_value.first.return_value = ride

        req = self.factory.get("/api/rides/active/")
        req.session = _session(customer_id=10)
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        driver_data = resp.data.get("driver") or {}
        self.assertIsNone(driver_data.get("phone"))
        self.assertIsNone(driver_data.get("driver_lat"))


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
    @patch("accounts.models.Customer.objects")
    def test_accept_blocked_without_car_approved(self, mock_cust_objs, _throttle):
        """Car driver without car_approved cannot accept a ride."""
        driver = _make_customer(
            pk=2, is_driver=True, driver_approved=True, is_driver_online=True,
            driver_vehicle_type="car", driver_car_approved=False,
        )
        mock_cust_objs.get.return_value = driver

        with patch("accounts.ride_views._tx") as mock_tx:
            mock_tx.atomic.return_value = _noop_atomic()
            mock_cust_objs.select_for_update.return_value.filter.return_value.first.return_value = driver
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
        import math
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
