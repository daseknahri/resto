"""Tests for Wave 3 — recipient package tracking (token + public view + SMS).

Covers:
  - _generate_track_token            opaque, URL-safe, unguessable, unique
  - RideCreateView                   wires recipient_track_token + fires dispatched SMS
  - DriverRideStatusView             fires the in_progress (collected) SMS
  - RecipientTrackView (PUBLIC)      safe projection, 404s, PII redaction, ETA, code gating
  - send_recipient_track_sms_sync    locale resolution + best-effort send

All unit-level: SimpleTestCase + mocks, no real DB (mirrors test_ride_hailing.py).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.ride_views import (
    RideCreateView,
    DriverRideStatusView,
    RecipientTrackView,
    _generate_track_token,
    _serialize_recipient_track,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    return sess


def _make_customer(pk=1, is_driver=False, driver_approved=False,
                   wallet_balance=Decimal("100.00"), name="Test User",
                   driver_vehicle="", driver_lat=None, driver_lng=None, locale="en"):
    c = MagicMock()
    c.pk = pk
    c.id = pk
    c.is_driver = is_driver
    c.driver_approved = driver_approved
    c.wallet_balance = wallet_balance
    c.name = name
    c.phone = "0600000001"
    c.driver_vehicle = driver_vehicle
    c.driver_lat = driver_lat
    c.driver_lng = driver_lng
    c.driver_position_updated_at = None
    c.locale = locale
    return c


def _make_package_ride(pk=50, status_val="searching", driver=None,
                       recipient_name="Jane Doe", recipient_phone="0699999999",
                       delivery_code="123456", token="tok_" + "a" * 40):
    r = MagicMock()
    r.pk = pk
    r.id = pk
    r.kind = "package"
    r.status = status_val
    r.recipient_name = recipient_name
    r.recipient_phone = recipient_phone
    r.package_note = ""
    r.delivery_code = delivery_code
    r.recipient_track_token = token
    r.driver = driver
    r.driver_id = driver.id if driver else None
    r.rider_id = 10
    r.pickup_lat = 33.5
    r.pickup_lng = -7.6
    r.dropoff_lat = 33.55
    r.dropoff_lng = -7.65
    r.pickup_address = "Pickup St"
    r.dropoff_address = "Drop Ave"
    for ts in ("accepted_at", "arrived_at", "started_at", "completed_at", "cancelled_at"):
        setattr(r, ts, None)
    r.Kind = MagicMock(PACKAGE="package", RIDE="ride")
    return r


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ── Token generator ──────────────────────────────────────────────────────────────

class TrackTokenTests(SimpleTestCase):
    def test_token_is_url_safe_and_long(self):
        tok = _generate_track_token()
        # token_urlsafe(32) → ~43 chars, only URL-safe alphabet
        self.assertGreaterEqual(len(tok), 40)
        import string
        allowed = set(string.ascii_letters + string.digits + "-_")
        self.assertTrue(set(tok) <= allowed)

    def test_tokens_are_unique(self):
        toks = {_generate_track_token() for _ in range(200)}
        self.assertEqual(len(toks), 200)


# ── RecipientTrackView (PUBLIC) ──────────────────────────────────────────────────

@override_settings(VERTICALS_ENABLED=frozenset({"courier"}))
class RecipientTrackViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RecipientTrackView.as_view()

    def _get(self, token):
        req = self.factory.get(f"/api/track/{token}/")
        req.session = _session()  # no customer — PUBLIC
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    def test_blank_token_returns_404(self, _t):
        resp = self.view(self._get("   "), token="   ")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    def test_short_token_returns_404_without_db_lookup(self, _t):
        with patch("accounts.ride_views.RideRequest.objects") as mock_objs:
            resp = self.view(self._get("abc"), token="abc")
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
            mock_objs.filter.assert_not_called()

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    def test_unknown_token_returns_404(self, mock_objs, _t):
        mock_objs.filter.return_value.select_related.return_value.first.return_value = None
        tok = "z" * 40
        resp = self.view(self._get(tok), token=tok)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    def test_searching_projection_has_no_courier_and_has_code(self, mock_objs, _t):
        ride = _make_package_ride(status_val="searching", delivery_code="654321")
        mock_objs.filter.return_value.select_related.return_value.first.return_value = ride
        tok = ride.recipient_track_token
        resp = self.view(self._get(tok), token=tok)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data["status"], "searching")
        self.assertIsNone(data["courier"])
        self.assertIsNone(data["driver_lat"])
        # code shown to recipient while live
        self.assertEqual(data["delivery_code"], "654321")
        # No sender PII / fare / token leaked
        self.assertNotIn("fare", data)
        self.assertNotIn("recipient_phone", data)
        self.assertNotIn("recipient_track_token", data)
        self.assertNotIn("payment_method", data)

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    def test_in_progress_exposes_first_name_vehicle_gps_and_eta(self, mock_objs, _t):
        driver = _make_customer(pk=7, name="Karim Bennani", driver_vehicle="Yamaha",
                                driver_lat=33.54, driver_lng=-7.64)
        ride = _make_package_ride(status_val="in_progress", driver=driver)
        mock_objs.filter.return_value.select_related.return_value.first.return_value = ride
        tok = ride.recipient_track_token
        resp = self.view(self._get(tok), token=tok)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        # courier FIRST name only — no surname, no phone
        self.assertEqual(data["courier"]["first_name"], "Karim")
        self.assertEqual(data["courier"]["vehicle"], "Yamaha")
        self.assertNotIn("phone", data["courier"])
        self.assertNotIn("name", data["courier"])
        # live GPS exposed en route
        self.assertEqual(data["driver_lat"], 33.54)
        self.assertEqual(data["driver_lng"], -7.64)
        # ETA computed toward dropoff
        self.assertIsInstance(data["eta_minutes"], int)
        self.assertGreaterEqual(data["eta_minutes"], 1)

    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.RideRequest.objects")
    def test_completed_hides_code_and_gps(self, mock_objs, _t):
        driver = _make_customer(pk=7, name="Karim B", driver_lat=33.54, driver_lng=-7.64)
        ride = _make_package_ride(status_val="completed", driver=driver)
        mock_objs.filter.return_value.select_related.return_value.first.return_value = ride
        tok = ride.recipient_track_token
        resp = self.view(self._get(tok), token=tok)
        data = resp.data
        # No live GPS after completion
        self.assertIsNone(data["driver_lat"])
        # Code no longer shown once terminal
        self.assertNotIn("delivery_code", data)
        # Courier identity still shown (delivered by Karim)
        self.assertEqual(data["courier"]["first_name"], "Karim")

    @override_settings(VERTICALS_ENABLED=frozenset({"rides"}))
    @patch("accounts.ride_views.RideDriverThrottle.allow_request", return_value=True)
    def test_courier_vertical_disabled_returns_503(self, _t):
        tok = "q" * 40
        resp = self.view(self._get(tok), token=tok)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# ── _serialize_recipient_track unit (ETA toward pickup before collection) ─────────

class RecipientTrackProjectionTests(SimpleTestCase):
    def test_eta_targets_pickup_before_collection(self):
        driver = _make_customer(pk=7, name="A B", driver_lat=33.50, driver_lng=-7.60)
        ride = _make_package_ride(status_val="accepted", driver=driver)
        # driver sits exactly on pickup → near-zero distance → ETA floored to 1
        data = _serialize_recipient_track(ride)
        self.assertEqual(data["eta_minutes"], 1)
        self.assertEqual(data["driver_lat"], 33.50)


# ── Create wires the token + dispatched SMS ──────────────────────────────────────

@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier"}))
class PackageCreateTokenSmsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RideCreateView.as_view()

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_create_sets_token_and_fires_dispatched_sms(
        self, mock_est, mock_cust_objs, mock_ride_objs, mock_tx, _throttle
    ):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_package_ride(pk=55)
        mock_ride_objs.create.return_value = ride

        req = self.factory.post("/api/rides/", {
            "kind": "package",
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
            "recipient_name": "Jane Doe",
            "recipient_phone": "0699999999",
        }, format="json")
        req.session = _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)

        with patch("accounts.ride_views.push_new_ride_to_drivers"), \
             patch("accounts.push.push_recipient_track_sms") as mock_sms:
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        create_kwargs = mock_ride_objs.create.call_args[1]
        # token generated for the package (non-empty, URL-safe length)
        self.assertTrue(create_kwargs.get("recipient_track_token"))
        self.assertGreaterEqual(len(create_kwargs["recipient_track_token"]), 40)
        # dispatched SMS enqueued with the new ride id
        mock_sms.assert_called_once_with(ride.id, "dispatched")

    @patch("accounts.ride_views.RideRequestThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    @patch("accounts.ride_service.estimate_ride")
    def test_ride_kind_gets_no_token_no_recipient_sms(
        self, mock_est, mock_cust_objs, mock_ride_objs, mock_tx, _throttle
    ):
        rider = _make_customer(pk=1, wallet_balance=Decimal("100.00"))
        mock_cust_objs.get.return_value = rider
        mock_tx.atomic.return_value = _noop_atomic()
        mock_est.return_value = {"distance_km": 3.0, "fare": Decimal("15.00")}
        mock_ride_objs.filter.return_value.exclude.return_value.exists.return_value = False
        ride = _make_package_ride(pk=6)
        ride.kind = "ride"
        mock_ride_objs.create.return_value = ride

        req = self.factory.post("/api/rides/", {
            "pickup_lat": 33.5, "pickup_lng": -7.6,
            "dropoff_lat": 33.55, "dropoff_lng": -7.65,
        }, format="json")
        req.session = _session(customer_id=1)
        req.user = MagicMock(is_authenticated=False)

        with patch("accounts.ride_views.push_new_ride_to_drivers"), \
             patch("accounts.push.push_recipient_track_sms") as mock_sms:
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        create_kwargs = mock_ride_objs.create.call_args[1]
        self.assertEqual(create_kwargs.get("recipient_track_token"), "")
        mock_sms.assert_not_called()


# ── in_progress fires the collected SMS ──────────────────────────────────────────

@override_settings(VERTICALS_ENABLED=frozenset({"rides", "courier"}))
class PackageInProgressSmsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRideStatusView.as_view()

    def _post_status(self, ride, new_status, driver):
        req = self.factory.post(f"/api/driver/rides/{ride.id}/status/",
                                {"status": new_status}, format="json")
        req.session = _session(customer_id=driver.id)
        req.user = MagicMock(is_authenticated=False)
        return req

    @patch("accounts.ride_views.DriverStatusUpdateThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._tx")
    @patch("accounts.ride_views.RideRequest.objects")
    @patch("accounts.models.Customer.objects")
    def test_in_progress_transition_enqueues_collected_sms(
        self, mock_cust_objs, mock_ride_objs, mock_tx, _throttle
    ):
        driver = _make_customer(pk=7, is_driver=True, driver_approved=True)
        mock_cust_objs.get.return_value = driver
        mock_tx.atomic.return_value = _noop_atomic()
        ride = _make_package_ride(pk=80, status_val="arrived", driver=driver)
        ride.VALID_TRANSITIONS = {"arrived": {"in_progress", "cancelled"}}
        mock_ride_objs.select_for_update.return_value.get.return_value = ride

        req = self._post_status(ride, "in_progress", driver)
        with patch("accounts.push.push_recipient_track_sms") as mock_sms:
            resp = self.view(req, ride_id=ride.id)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_sms.assert_called_once_with(ride.id, "in_progress")


# ── send_recipient_track_sms_sync ────────────────────────────────────────────────

class RecipientTrackSmsSyncTests(SimpleTestCase):
    @patch("accounts.messaging._brand_https_base", return_value="https://kepoli.app")
    @patch("menu.sms.send_sms", return_value=True)
    def test_sends_localized_link_using_sender_locale(self, mock_send, _base):
        ride = _make_package_ride(pk=90, status_val="searching",
                                  token="t" * 43, recipient_phone="0699999999")
        # send_recipient_track_sms_sync does `from .models import Customer, RideRequest`
        # and reads under schema_context("public"); patch those seams + the context mgr.
        with patch("django_tenants.utils.schema_context") as _sc, \
             patch("accounts.models.RideRequest.objects") as mock_ride_objs, \
             patch("accounts.models.Customer.objects") as mock_cust_objs:
            _sc.return_value.__enter__ = MagicMock(return_value=None)
            _sc.return_value.__exit__ = MagicMock(return_value=False)
            mock_ride_objs.filter.return_value.first.return_value = ride
            mock_cust_objs.filter.return_value.values_list.return_value.first.return_value = "fr"
            from accounts.push import send_recipient_track_sms_sync
            ok = send_recipient_track_sms_sync(90, "dispatched")

        self.assertTrue(ok)
        # send_sms called with the French body + the absolute /track/<token> link
        args, kwargs = mock_send.call_args
        self.assertEqual(args[0], "0699999999")
        self.assertIn("https://kepoli.app/track/" + "t" * 43, args[1])
        self.assertIn("direct", args[1].lower())  # FR copy "en direct"
        self.assertEqual(kwargs["event"], "recipient.track.dispatched")

    @patch("menu.sms.send_sms", return_value=False)
    def test_unknown_event_returns_false_without_sending(self, mock_send):
        from accounts.push import send_recipient_track_sms_sync
        ok = send_recipient_track_sms_sync(90, "bogus")
        self.assertFalse(ok)
        mock_send.assert_not_called()
