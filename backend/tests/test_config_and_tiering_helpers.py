"""
Tests for config utility helpers and tiering feature-flag functions:
  - config.exceptions._bool_env / _float_env
  - config.api._check_db / _check_cache / health_view
  - tenancy.tiering.normalize_plan_feature_flag_key
  - tenancy.tiering.is_valid_plan_feature_flag_key
  - tenancy.tiering.plan_feature_flag_catalog

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase

from config.exceptions import _bool_env, _float_env
from config import api as config_api
from tenancy.tiering import (
    normalize_plan_feature_flag_key,
    is_valid_plan_feature_flag_key,
    plan_feature_flag_catalog,
    PLAN_FEATURE_FLAG_CATALOG,
)


# ══════════════════════════════════════════════════════════════════════════════
# config.exceptions._bool_env
# ══════════════════════════════════════════════════════════════════════════════

class BoolEnvTests(SimpleTestCase):
    def test_returns_default_when_not_set(self):
        with patch.dict("os.environ", {}, clear=False):
            import os; os.environ.pop("_TEST_BOOL_FLAG", None)
            self.assertFalse(_bool_env("_TEST_BOOL_FLAG"))
            self.assertTrue(_bool_env("_TEST_BOOL_FLAG", default=True))

    def test_true_values(self):
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            with patch.dict("os.environ", {"_TBF": val}):
                self.assertTrue(_bool_env("_TBF"), f"Expected True for {val!r}")

    def test_false_values(self):
        for val in ("0", "false", "no", "off", "random"):
            with patch.dict("os.environ", {"_TBF": val}):
                self.assertFalse(_bool_env("_TBF"), f"Expected False for {val!r}")

    def test_whitespace_stripped(self):
        with patch.dict("os.environ", {"_TBF": "  true  "}):
            self.assertTrue(_bool_env("_TBF"))


# ══════════════════════════════════════════════════════════════════════════════
# config.exceptions._float_env
# ══════════════════════════════════════════════════════════════════════════════

class FloatEnvTests(SimpleTestCase):
    def test_returns_default_when_not_set(self):
        import os; os.environ.pop("_TEST_FLOAT", None)
        self.assertEqual(_float_env("_TEST_FLOAT"), 0.0)
        self.assertEqual(_float_env("_TEST_FLOAT", default=5.0), 5.0)

    def test_parses_float(self):
        with patch.dict("os.environ", {"_TFF": "3.14"}):
            self.assertAlmostEqual(_float_env("_TFF"), 3.14)

    def test_returns_default_on_non_numeric(self):
        with patch.dict("os.environ", {"_TFF": "abc"}):
            self.assertEqual(_float_env("_TFF", default=99.0), 99.0)

    def test_returns_default_on_empty_string(self):
        with patch.dict("os.environ", {"_TFF": ""}):
            self.assertEqual(_float_env("_TFF", default=7.0), 7.0)

    def test_returns_default_on_negative(self):
        with patch.dict("os.environ", {"_TFF": "-1.0"}):
            self.assertEqual(_float_env("_TFF", default=2.0), 2.0)

    def test_zero_is_valid(self):
        with patch.dict("os.environ", {"_TFF": "0"}):
            self.assertEqual(_float_env("_TFF", default=5.0), 0.0)

    def test_integer_string_parsed(self):
        with patch.dict("os.environ", {"_TFF": "30"}):
            self.assertEqual(_float_env("_TFF"), 30.0)


# ══════════════════════════════════════════════════════════════════════════════
# config.api._check_db / _check_cache / health_view
# ══════════════════════════════════════════════════════════════════════════════

class CheckDbTests(SimpleTestCase):
    def test_returns_ok_true_on_success(self):
        cursor_mock = MagicMock()
        cursor_mock.__enter__ = lambda s: cursor_mock
        cursor_mock.__exit__ = lambda s, *a: None
        with patch("config.api.connection") as conn_mock:
            conn_mock.cursor.return_value = cursor_mock
            result = config_api._check_db()
        self.assertTrue(result["ok"])
        self.assertIsNotNone(result["latency_ms"])
        self.assertIsInstance(result["latency_ms"], int)

    def test_returns_ok_false_on_exception(self):
        with patch("config.api.connection") as conn_mock:
            conn_mock.cursor.side_effect = Exception("db down")
            result = config_api._check_db()
        self.assertFalse(result["ok"])
        self.assertIsNone(result["latency_ms"])


class CheckCacheTests(SimpleTestCase):
    def test_returns_ok_true_when_value_round_trips(self):
        with patch("config.api.cache") as cache_mock:
            cache_mock.get.return_value = "1"
            result = config_api._check_cache()
        self.assertTrue(result["ok"])
        self.assertIsInstance(result["latency_ms"], int)

    def test_returns_ok_false_when_value_missing(self):
        with patch("config.api.cache") as cache_mock:
            cache_mock.get.return_value = None
            result = config_api._check_cache()
        self.assertFalse(result["ok"])

    def test_returns_ok_false_on_cache_exception(self):
        with patch("config.api.cache") as cache_mock:
            cache_mock.set.side_effect = Exception("redis down")
            result = config_api._check_cache()
        self.assertFalse(result["ok"])
        self.assertIsNone(result["latency_ms"])


class HealthViewTests(SimpleTestCase):
    def _request(self, tenant=None):
        req = SimpleNamespace(tenant=tenant)
        return req

    def _patch_both_ok(self):
        return (
            patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 5}),
            patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 2}),
        )

    def test_all_ok_returns_200(self):
        with patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 5}):
            with patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 2}):
                response = config_api.health_view(self._request())
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["status"], "ok")

    def test_db_down_returns_503(self):
        with patch.object(config_api, "_check_db", return_value={"ok": False, "latency_ms": None}):
            with patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 2}):
                response = config_api.health_view(self._request())
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.content)
        self.assertEqual(body["status"], "down")

    def test_cache_down_returns_200_degraded(self):
        with patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 5}):
            with patch.object(config_api, "_check_cache", return_value={"ok": False, "latency_ms": None}):
                response = config_api.health_view(self._request())
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["status"], "degraded")

    def test_response_includes_checks_key(self):
        with patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 1}):
            with patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 1}):
                response = config_api.health_view(self._request())
        body = json.loads(response.content)
        self.assertIn("db", body["checks"])
        self.assertIn("cache", body["checks"])

    def test_tenant_included_when_present(self):
        tenant = SimpleNamespace(id=42, slug="demo", name="Demo Resto")
        with patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 1}):
            with patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 1}):
                response = config_api.health_view(self._request(tenant=tenant))
        body = json.loads(response.content)
        self.assertEqual(body["tenant"]["id"], 42)
        self.assertEqual(body["tenant"]["slug"], "demo")

    def test_no_tenant_returns_null(self):
        with patch.object(config_api, "_check_db", return_value={"ok": True, "latency_ms": 1}):
            with patch.object(config_api, "_check_cache", return_value={"ok": True, "latency_ms": 1}):
                response = config_api.health_view(self._request(tenant=None))
        body = json.loads(response.content)
        self.assertIsNone(body["tenant"])


# ══════════════════════════════════════════════════════════════════════════════
# tenancy.tiering feature-flag helpers
# ══════════════════════════════════════════════════════════════════════════════

class NormalizePlanFeatureFlagKeyTests(SimpleTestCase):
    def test_strips_whitespace(self):
        self.assertEqual(normalize_plan_feature_flag_key("  customer_reservations  "), "customer_reservations")

    def test_lowercases(self):
        self.assertEqual(normalize_plan_feature_flag_key("CUSTOMER_RESERVATIONS"), "customer_reservations")

    def test_none_returns_empty(self):
        self.assertEqual(normalize_plan_feature_flag_key(None), "")

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_plan_feature_flag_key(""), "")

    def test_known_key_returned_as_is(self):
        self.assertEqual(normalize_plan_feature_flag_key("advanced_analytics"), "advanced_analytics")


class IsValidPlanFeatureFlagKeyTests(SimpleTestCase):
    def test_known_key_valid(self):
        for key in PLAN_FEATURE_FLAG_CATALOG:
            self.assertTrue(is_valid_plan_feature_flag_key(key), f"{key!r} should be valid")

    def test_unknown_key_invalid(self):
        self.assertFalse(is_valid_plan_feature_flag_key("unknown_feature"))

    def test_none_invalid(self):
        self.assertFalse(is_valid_plan_feature_flag_key(None))

    def test_empty_invalid(self):
        self.assertFalse(is_valid_plan_feature_flag_key(""))

    def test_whitespace_padded_known_key_valid(self):
        first_key = next(iter(PLAN_FEATURE_FLAG_CATALOG))
        self.assertTrue(is_valid_plan_feature_flag_key(f"  {first_key}  "))

    def test_uppercase_known_key_valid(self):
        first_key = next(iter(PLAN_FEATURE_FLAG_CATALOG))
        self.assertTrue(is_valid_plan_feature_flag_key(first_key.upper()))


class PlanFeatureFlagCatalogTests(SimpleTestCase):
    def test_returns_list(self):
        result = plan_feature_flag_catalog()
        self.assertIsInstance(result, list)

    def test_length_matches_catalog(self):
        result = plan_feature_flag_catalog()
        self.assertEqual(len(result), len(PLAN_FEATURE_FLAG_CATALOG))

    def test_each_entry_has_required_fields(self):
        for entry in plan_feature_flag_catalog():
            self.assertIn("key", entry)
            self.assertIn("label", entry)
            self.assertIn("description", entry)

    def test_keys_match_catalog(self):
        catalog_keys = set(PLAN_FEATURE_FLAG_CATALOG.keys())
        result_keys = {entry["key"] for entry in plan_feature_flag_catalog()}
        self.assertEqual(catalog_keys, result_keys)

    def test_labels_are_non_empty_strings(self):
        for entry in plan_feature_flag_catalog():
            self.assertIsInstance(entry["label"], str)
            self.assertTrue(entry["label"], f"label for {entry['key']!r} is empty")
