"""R5: VERTICALS_ENABLED gate tests.

All tests are SimpleTestCase (no DB). Verifies:
  • _vertical_gate returns 503 for the right combos of kind and enabled set.
  • _vertical_gate returns None when the vertical is enabled.
  • RideEstimateView returns 503 when all ride verticals are disabled.
  • RideCreateView returns 503 for the matching kind when disabled.
  • CustomerSessionView platform dict includes enabled_verticals.
"""
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory


# ── Helper ────────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    d = {}
    if customer_id is not None:
        d["customer_id"] = customer_id
    m = MagicMock()
    m.get = lambda key, default=None: d.get(key, default)
    m.__setitem__ = lambda s, key, value: d.__setitem__(key, value)
    m.pop = lambda key, default=None: d.pop(key, default)
    return m


# ── _vertical_gate unit tests ─────────────────────────────────────────────────

class VerticalGateFunctionTests(SimpleTestCase):
    """Directly tests the _vertical_gate helper without HTTP overhead."""

    def _gate(self, kind, enabled_set):
        from django.test import override_settings
        from accounts.ride_views import _vertical_gate
        from accounts.models import RideRequest
        kind_map = {"ride": RideRequest.Kind.RIDE, "package": RideRequest.Kind.PACKAGE, None: None}
        with override_settings(VERTICALS_ENABLED=frozenset(enabled_set)):
            return _vertical_gate(kind_map[kind])

    def test_ride_blocked_when_rides_not_in_enabled(self):
        resp = self._gate("ride", {"courier", "food"})
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data["code"], "vertical_disabled")

    def test_package_blocked_when_courier_not_in_enabled(self):
        resp = self._gate("package", {"rides", "food"})
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 503)

    def test_none_kind_blocked_when_both_disabled(self):
        resp = self._gate(None, {"food", "shops"})
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 503)

    def test_ride_allowed_when_rides_in_enabled(self):
        resp = self._gate("ride", {"rides", "courier"})
        self.assertIsNone(resp)

    def test_package_allowed_when_courier_in_enabled(self):
        resp = self._gate("package", {"rides", "courier"})
        self.assertIsNone(resp)

    def test_none_kind_allowed_when_rides_in_enabled(self):
        resp = self._gate(None, {"rides"})
        self.assertIsNone(resp)

    def test_none_kind_allowed_when_courier_in_enabled(self):
        resp = self._gate(None, {"courier"})
        self.assertIsNone(resp)


# ── RideEstimateView — HTTP-level gate ───────────────────────────────────────

class RideEstimateVerticalGateTests(SimpleTestCase):
    def setUp(self):
        from accounts.ride_views import RideEstimateView
        self.view = RideEstimateView.as_view()
        self.factory = APIRequestFactory()

    @override_settings(VERTICALS_ENABLED=frozenset())
    def test_returns_503_when_all_ride_verticals_disabled(self):
        req = self.factory.post(
            "/api/rides/estimate/",
            {"pickup_lat": 33.5, "pickup_lng": -7.6, "dropoff_lat": 33.6, "dropoff_lng": -7.7},
            format="json",
        )
        req.session = _session()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "vertical_disabled")


# ── RideCreateView — kind-specific HTTP-level gate ────────────────────────────

class RideCreateVerticalGateTests(SimpleTestCase):
    def setUp(self):
        from accounts.ride_views import RideCreateView
        self.view = RideCreateView.as_view()
        self.factory = APIRequestFactory()

    @override_settings(VERTICALS_ENABLED=frozenset({"courier"}))
    def test_ride_kind_blocked_when_rides_disabled(self):
        req = self.factory.post(
            "/api/rides/",
            {"kind": "ride", "pickup_lat": 33.5, "pickup_lng": -7.6,
             "dropoff_lat": 33.6, "dropoff_lng": -7.7,
             "pickup_address": "A", "dropoff_address": "B", "payment_method": "wallet"},
            format="json",
        )
        req.session = _session(customer_id=1)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "vertical_disabled")

    @override_settings(VERTICALS_ENABLED=frozenset({"rides"}))
    def test_package_kind_blocked_when_courier_disabled(self):
        req = self.factory.post(
            "/api/rides/",
            {"kind": "package", "pickup_lat": 33.5, "pickup_lng": -7.6,
             "dropoff_lat": 33.6, "dropoff_lng": -7.7,
             "pickup_address": "A", "dropoff_address": "B", "payment_method": "wallet",
             "recipient_name": "Bob", "recipient_phone": "+21261234567"},
            format="json",
        )
        req.session = _session(customer_id=1)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "vertical_disabled")


# ── CustomerSessionView — platform.enabled_verticals ─────────────────────────

class CustomerSessionPlatformTest(SimpleTestCase):
    def setUp(self):
        from accounts.views import CustomerSessionView
        self.view = CustomerSessionView.as_view()
        self.factory = APIRequestFactory()

    @override_settings(
        VERTICALS_ENABLED=frozenset({"food", "courier", "driver"}),
        PSP_TOPUP_ENABLED=False,
    )
    def test_platform_includes_enabled_verticals(self):
        req = self.factory.get("/api/customer/session/")
        req.session = _session()
        resp = self.view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("platform", resp.data)
        self.assertIn("enabled_verticals", resp.data["platform"])
        enabled = set(resp.data["platform"]["enabled_verticals"])
        self.assertIn("food", enabled)
        self.assertIn("courier", enabled)
        self.assertNotIn("rides", enabled)

    @override_settings(
        VERTICALS_ENABLED=frozenset({"food", "rides", "courier", "driver"}),
        PSP_TOPUP_ENABLED=False,
    )
    def test_rides_in_enabled_verticals_when_configured(self):
        req = self.factory.get("/api/customer/session/")
        req.session = _session()
        resp = self.view(req)
        self.assertIn("rides", set(resp.data["platform"]["enabled_verticals"]))
