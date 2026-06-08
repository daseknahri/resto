"""Tests for tenancy.routing.road_distance_km — the pluggable road-distance seam.

Covers the default road-factor fallback, env tuning, and the opt-in OSRM path
(mocked) including caching and graceful fallback on failure. Unit-level
(SimpleTestCase + mocks). Run with DJANGO_DEBUG=True.
"""
import os
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from tenancy.delivery_pricing import haversine_km
from tenancy.routing import DEFAULT_ROAD_FACTOR, road_distance_km, road_factor

# Two real Casablanca→Rabat-ish points with a known non-zero straight-line distance.
A = (33.5731, -7.5898)
B = (34.0209, -6.8416)


def _no_osrm_env():
    # Force the factor path: empty OSRM url, default factor.
    return patch.dict(os.environ, {"DELIVERY_OSRM_URL": "", "DELIVERY_ROAD_FACTOR": ""})


class RoadFactorTests(SimpleTestCase):
    def test_default_factor(self):
        with patch.dict(os.environ, {"DELIVERY_ROAD_FACTOR": ""}):
            self.assertEqual(road_factor(), DEFAULT_ROAD_FACTOR)

    def test_env_override(self):
        with patch.dict(os.environ, {"DELIVERY_ROAD_FACTOR": "1.5"}):
            self.assertEqual(road_factor(), 1.5)

    def test_garbage_falls_back(self):
        with patch.dict(os.environ, {"DELIVERY_ROAD_FACTOR": "abc"}):
            self.assertEqual(road_factor(), DEFAULT_ROAD_FACTOR)

    def test_below_one_clamped(self):
        # Road distance is never shorter than crow-flies → never < 1.0.
        with patch.dict(os.environ, {"DELIVERY_ROAD_FACTOR": "0.5"}):
            self.assertEqual(road_factor(), DEFAULT_ROAD_FACTOR)


class RoadDistanceFactorPathTests(SimpleTestCase):
    def test_distance_is_haversine_times_factor(self):
        with _no_osrm_env():
            expected = round(haversine_km(*A, *B) * DEFAULT_ROAD_FACTOR, 2)
            self.assertEqual(road_distance_km(*A, *B), expected)

    def test_factor_makes_it_longer_than_straight_line(self):
        with _no_osrm_env():
            self.assertGreater(road_distance_km(*A, *B), haversine_km(*A, *B))

    def test_same_point_is_zero(self):
        with _no_osrm_env():
            self.assertEqual(road_distance_km(33.5, -7.5, 33.5, -7.5), 0.0)

    def test_unparseable_coords_zero(self):
        with _no_osrm_env():
            self.assertEqual(road_distance_km(None, None, 1, 1), 0.0)

    def test_custom_factor_applied(self):
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "", "DELIVERY_ROAD_FACTOR": "2.0"}):
            expected = round(haversine_km(*A, *B) * 2.0, 2)
            self.assertEqual(road_distance_km(*A, *B), expected)


class RoadDistanceOsrmPathTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _osrm_response(self, meters):
        resp = Mock()
        resp.ok = True
        resp.json.return_value = {"code": "Ok", "routes": [{"distance": meters}]}
        return resp

    def test_uses_osrm_distance_when_configured(self):
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "http://osrm:5000"}):
            with patch("requests.get", return_value=self._osrm_response(5000.0)) as g:
                self.assertEqual(road_distance_km(*A, *B), 5.0)
                g.assert_called_once()

    def test_result_is_cached(self):
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "http://osrm:5000"}):
            with patch("requests.get", return_value=self._osrm_response(7300.0)) as g:
                first = road_distance_km(*A, *B)
                second = road_distance_km(*A, *B)
                self.assertEqual(first, 7.3)
                self.assertEqual(second, 7.3)
                g.assert_called_once()  # second call served from cache

    def test_osrm_error_falls_back_to_factor(self):
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "http://osrm:5000", "DELIVERY_ROAD_FACTOR": ""}):
            with patch("requests.get", side_effect=Exception("boom")):
                expected = round(haversine_km(*A, *B) * DEFAULT_ROAD_FACTOR, 2)
                self.assertEqual(road_distance_km(*A, *B), expected)

    def test_osrm_non_ok_code_falls_back(self):
        bad = Mock()
        bad.ok = True
        bad.json.return_value = {"code": "NoRoute", "routes": []}
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "http://osrm:5000", "DELIVERY_ROAD_FACTOR": ""}):
            with patch("requests.get", return_value=bad):
                expected = round(haversine_km(*A, *B) * DEFAULT_ROAD_FACTOR, 2)
                self.assertEqual(road_distance_km(*A, *B), expected)

    def test_osrm_http_error_falls_back(self):
        bad = Mock()
        bad.ok = False
        with patch.dict(os.environ, {"DELIVERY_OSRM_URL": "http://osrm:5000", "DELIVERY_ROAD_FACTOR": ""}):
            with patch("requests.get", return_value=bad):
                expected = round(haversine_km(*A, *B) * DEFAULT_ROAD_FACTOR, 2)
                self.assertEqual(road_distance_km(*A, *B), expected)
