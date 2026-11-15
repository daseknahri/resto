"""
Run 8 G3b W9 — DeliveryZone radius + polygon validation (A2-34, A2-35).

Covers ONLY the validation added in this cluster:
  - A2-34: approx_radius_km must be > 0 and <= 100 km (POST + PATCH),
            via the shared _validate_radius helper.
  - A2-35: polygon lat/lng range-checked (-90..90 / -180..180) and centre
            lat/lng range-checked, via _valid_polygon (+ POST/PATCH centre
            checks). Boundary values (-90/90, -180/180, 100 km) are accepted.

NOT re-tested here: the fee-tier validation from G3a A2-11
(_validate_fee_tiers / compute_fee belt) — see test_admin_delivery_views.py
and the G3a tests.

All tests are unit-level (SimpleTestCase + mocks — no real DB), following the
pattern of test_admin_delivery_views.py.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    MAX_ZONE_RADIUS_KM,
    AdminDeliveryZoneDetailView,
    AdminDeliveryZoneListCreateView,
    _validate_radius,
    _valid_polygon,
)
from accounts.models import User


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _make_zone(zone_id=1):
    z = MagicMock()
    z.id = zone_id
    z.name = "Downtown"
    z.city = "Casablanca"
    z.polygon = [{"lat": 33.5, "lng": -7.6}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}]
    z.center_lat = 33.55
    z.center_lng = -7.55
    z.approx_radius_km = 5.0
    z.is_active = True
    z.fee_tiers = []
    z.created_at = MagicMock()
    z.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return z


def _sc_mock():
    """schema_context mock for use in with statements."""
    ctx = MagicMock()
    ctx.__enter__ = lambda s: None
    ctx.__exit__ = lambda s, *a: None
    return ctx


def _good_polygon():
    return [
        {"lat": 33.5, "lng": -7.6},
        {"lat": 33.6, "lng": -7.5},
        {"lat": 33.5, "lng": -7.5},
    ]


def _good_payload(**overrides):
    payload = {
        "name": "Downtown",
        "city": "Casablanca",
        "polygon": _good_polygon(),
        "center_lat": 33.55,
        "center_lng": -7.55,
        "approx_radius_km": 5,
    }
    payload.update(overrides)
    return payload


# ── _validate_radius (A2-34) ──────────────────────────────────────────────────

class ValidateRadiusTests(SimpleTestCase):
    def test_bound_is_100_km(self):
        self.assertEqual(MAX_ZONE_RADIUS_KM, 100.0)

    def test_valid_values_pass_through(self):
        for value in (0.5, 5, 5.0, "5", 100, 100.0):
            radius, error = _validate_radius(value)
            self.assertIsNone(error, f"{value!r} should be valid")
            self.assertEqual(radius, float(value))

    def test_zero_and_negative_rejected(self):
        for value in (0, 0.0, -1, -0.5, "-3"):
            radius, error = _validate_radius(value)
            self.assertIsNone(radius)
            self.assertIn("greater than 0", error)

    def test_over_bound_rejected(self):
        for value in (100.01, 101, 250, 1000):
            radius, error = _validate_radius(value)
            self.assertIsNone(radius)
            self.assertIn("no more than 100", error)

    def test_non_numeric_rejected(self):
        for value in (None, "", "abc", True, [], {}):
            radius, error = _validate_radius(value)
            self.assertIsNone(radius)
            self.assertIn("must be a number", error)

    def test_nan_and_inf_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            radius, error = _validate_radius(value)
            self.assertIsNone(radius)
            self.assertIsNotNone(error)


# ── _valid_polygon (A2-35) ────────────────────────────────────────────────────

class ValidPolygonTests(SimpleTestCase):
    def test_good_polygon_accepted(self):
        self.assertTrue(_valid_polygon(_good_polygon()))

    def test_boundary_values_accepted(self):
        self.assertTrue(_valid_polygon([
            {"lat": -90, "lng": -180},
            {"lat": 90, "lng": 180},
            {"lat": 0, "lng": 0},
        ]))

    def test_lat_out_of_range_rejected(self):
        for lat in (90.01, 91, 999, -90.01, -100):
            self.assertFalse(_valid_polygon([
                {"lat": lat, "lng": -7.6},
                {"lat": 33.6, "lng": -7.5},
                {"lat": 33.5, "lng": -7.5},
            ]), f"lat {lat} should be rejected")

    def test_lng_out_of_range_rejected(self):
        for lng in (180.01, 181, 5000, -180.01, -5000):
            self.assertFalse(_valid_polygon([
                {"lat": 33.5, "lng": lng},
                {"lat": 33.6, "lng": -7.5},
                {"lat": 33.5, "lng": -7.5},
            ]), f"lng {lng} should be rejected")

    def test_nan_inf_bool_rejected(self):
        for bad in (float("nan"), float("inf"), True):
            self.assertFalse(_valid_polygon([
                {"lat": bad, "lng": -7.6},
                {"lat": 33.6, "lng": -7.5},
                {"lat": 33.5, "lng": -7.5},
            ]))

    def test_shape_rules_unchanged(self):
        # Still requires a list of >= 3 {lat, lng} dicts (pre-existing behaviour).
        self.assertFalse(_valid_polygon([{"lat": 33.5, "lng": -7.6}]))
        self.assertFalse(_valid_polygon("not a list"))
        self.assertFalse(_valid_polygon([{"lat": 33.5}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}]))
        self.assertFalse(_valid_polygon([[33.5, -7.6], [33.6, -7.5], [33.5, -7.5]]))


# ── POST /api/admin/delivery-zones/ ───────────────────────────────────────────

class ZoneCreateRadiusPolygonTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryZoneListCreateView.as_view()

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/delivery-zones/", data, format="json")
        req.user = user or _admin()
        return req

    def _create(self, data):
        """Run a POST with the model layer mocked; returns the response."""
        zone = _make_zone()
        with patch("accounts.models.DeliveryZone") as mock_dz, \
             patch("accounts.views.log_admin_action"):
            mock_dz.objects.create.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", side_effect=lambda z: {"id": z.id}):
                    return self.view(self._post(data))

    def test_post_radius_zero_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(approx_radius_km=0)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("greater than 0", resp.data["detail"])

    def test_post_radius_negative_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(approx_radius_km=-3)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_radius_over_bound_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(approx_radius_km=250)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no more than 100", resp.data["detail"])

    def test_post_radius_non_numeric_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(approx_radius_km="abc")))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_radius_at_bound_returns_201(self):
        resp = self._create(_good_payload(approx_radius_km=100))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_post_polygon_lat_out_of_range_returns_400(self):
        bad = _good_polygon()
        bad[0] = {"lat": 999, "lng": -7.6}
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(polygon=bad)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("-90..90", resp.data["detail"])

    def test_post_polygon_lng_out_of_range_returns_400(self):
        bad = _good_polygon()
        bad[1] = {"lat": 33.6, "lng": -5000}
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(polygon=bad)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("-180..180", resp.data["detail"])

    def test_post_polygon_at_boundary_returns_201(self):
        boundary = [
            {"lat": -90, "lng": -180},
            {"lat": 90, "lng": 180},
            {"lat": 0, "lng": 0},
        ]
        resp = self._create(_good_payload(polygon=boundary))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_post_center_lat_out_of_range_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(center_lat=100)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat", resp.data["detail"])

    def test_post_center_lng_out_of_range_returns_400(self):
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(self._post(_good_payload(center_lng=-200)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lng", resp.data["detail"])


# ── PATCH /api/admin/delivery-zones/<id>/ ─────────────────────────────────────

class ZonePatchRadiusPolygonTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryZoneDetailView.as_view()

    def _patch(self, zone_id, data, user=None):
        req = self.factory.patch(f"/api/admin/delivery-zones/{zone_id}/", data, format="json")
        req.user = user or _admin()
        return self.view(req, zone_id=zone_id)

    def _patch_with_zone(self, data):
        zone = _make_zone()
        with patch("accounts.models.DeliveryZone") as mock_dz, \
             patch("accounts.views.log_admin_action"):
            mock_dz.objects.get.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", return_value={"id": 1}):
                    return self._patch(1, data), zone

    def test_patch_radius_zero_returns_400(self):
        resp, zone = self._patch_with_zone({"approx_radius_km": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        zone.save.assert_not_called()

    def test_patch_radius_over_bound_returns_400(self):
        resp, zone = self._patch_with_zone({"approx_radius_km": 101})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        zone.save.assert_not_called()

    def test_patch_radius_valid_returns_200(self):
        resp, zone = self._patch_with_zone({"approx_radius_km": 50})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(zone.approx_radius_km, 50)
        zone.save.assert_called_once()

    def test_patch_polygon_lng_out_of_range_returns_400(self):
        bad = _good_polygon()
        bad[0] = {"lat": 33.5, "lng": 5000}
        resp, zone = self._patch_with_zone({"polygon": bad})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        zone.save.assert_not_called()

    def test_patch_center_lat_out_of_range_returns_400(self):
        resp, zone = self._patch_with_zone({"center_lat": -91})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        zone.save.assert_not_called()

    def test_patch_center_lng_valid_returns_200(self):
        resp, zone = self._patch_with_zone({"center_lng": -7.7})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(zone.center_lng, -7.7)
        zone.save.assert_called_once()
