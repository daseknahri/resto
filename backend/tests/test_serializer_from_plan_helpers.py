"""
Unit tests for the two @staticmethod from_plan builders in sales/serializers.py:

  AdminPlanFeatureFlagPlanSerializer.from_plan(plan, *, flags=None)
    Renders catalog feature flags merged with the plan's actual flag state;
    appends legacy (uncatalogued) flags at the end.

  TierUpgradeTargetSerializer.from_plan(plan, *, can_request=True)
    Wraps plan_entitlements() into the serialiser's payload shape.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from sales.serializers import AdminPlanFeatureFlagPlanSerializer, TierUpgradeTargetSerializer


# ── plan helper ───────────────────────────────────────────────────────────────

def _plan(code="growth", name="Growth", is_active=True):
    return SimpleNamespace(code=code, name=name, is_active=is_active)


def _flag_obj(key="online_ordering", enabled=True, config=None):
    return SimpleNamespace(key=key, enabled=enabled, config=config)


# ══════════════════════════════════════════════════════════════════════════════
# TierUpgradeTargetSerializer.from_plan
# ══════════════════════════════════════════════════════════════════════════════

_BASE_ENTITLEMENTS = {
    "tier_code": "growth",
    "tier_name": "Growth",
    "is_active": True,
    "ordering_mode": "direct",
    "can_order": True,
    "can_checkout": True,
    "can_whatsapp_order": True,
    "max_languages": 3,
    "max_dishes": 200,
    "max_staff_accounts": 5,
}


class TierUpgradeTargetSerializerFromPlanTests(SimpleTestCase):
    """TierUpgradeTargetSerializer.from_plan builds the correct shape."""

    def _call(self, plan=None, can_request=True, entitlements=None):
        ents = entitlements or _BASE_ENTITLEMENTS.copy()
        with patch("sales.serializers.plan_entitlements", return_value=ents):
            return TierUpgradeTargetSerializer.from_plan(
                plan or _plan(), can_request=can_request
            )

    def test_result_contains_expected_keys(self):
        result = self._call()
        for key in ("code", "name", "is_active", "ordering_mode", "can_order",
                    "can_checkout", "can_whatsapp_order", "max_languages",
                    "max_dishes", "max_staff_accounts", "can_request"):
            self.assertIn(key, result)

    def test_can_request_true_reflected(self):
        result = self._call(can_request=True)
        self.assertTrue(result["can_request"])

    def test_can_request_false_reflected(self):
        result = self._call(can_request=False)
        self.assertFalse(result["can_request"])

    def test_entitlement_values_passed_through(self):
        result = self._call()
        self.assertEqual(result["code"], "growth")
        self.assertEqual(result["name"], "Growth")
        self.assertTrue(result["is_active"])
        self.assertEqual(result["max_languages"], 3)

    def test_max_dishes_defaults_to_zero_when_absent(self):
        """entitlements.get('max_dishes', 0) is used — missing key → 0."""
        ents = {k: v for k, v in _BASE_ENTITLEMENTS.items() if k != "max_dishes"}
        result = self._call(entitlements=ents)
        self.assertEqual(result["max_dishes"], 0)

    def test_max_staff_accounts_defaults_to_zero_when_absent(self):
        ents = {k: v for k, v in _BASE_ENTITLEMENTS.items() if k != "max_staff_accounts"}
        result = self._call(entitlements=ents)
        self.assertEqual(result["max_staff_accounts"], 0)


# ══════════════════════════════════════════════════════════════════════════════
# PlanFeatureFlagsSerializer.from_plan
# ══════════════════════════════════════════════════════════════════════════════

_CATALOG = [
    {"key": "online_ordering", "label": "Online Ordering", "description": "Enable order flow"},
    {"key": "whatsapp_notifications", "label": "WhatsApp Notifications", "description": ""},
]


class PlanFeatureFlagsSerializerFromPlanTests(SimpleTestCase):
    """AdminPlanFeatureFlagPlanSerializer.from_plan merges catalog with existing flags."""

    def _call(self, plan=None, flags=None, catalog=None):
        with patch("sales.serializers.plan_feature_flag_catalog", return_value=catalog or _CATALOG):
            return AdminPlanFeatureFlagPlanSerializer.from_plan(plan or _plan(), flags=flags)

    # ── output shape ──────────────────────────────────────────────────────────
    def test_result_contains_feature_flags_list(self):
        result = self._call()
        self.assertIn("feature_flags", result)
        self.assertIsInstance(result["feature_flags"], list)

    def test_result_contains_plan_code_and_name(self):
        result = self._call(plan=_plan(code="growth", name="Growth"))
        self.assertIn("plan_code", result)
        self.assertIn("plan_name", result)

    # ── empty flags → all disabled from catalog ───────────────────────────────
    def test_empty_flags_gives_catalog_length_rendered_flags(self):
        result = self._call(flags=[])
        self.assertEqual(len(result["feature_flags"]), len(_CATALOG))

    def test_empty_flags_all_disabled(self):
        result = self._call(flags=[])
        for flag in result["feature_flags"]:
            self.assertFalse(flag["enabled"])

    def test_empty_flags_config_is_none(self):
        result = self._call(flags=[])
        for flag in result["feature_flags"]:
            self.assertIsNone(flag["config"])

    # ── existing flag merged ──────────────────────────────────────────────────
    def test_enabled_flag_in_catalog_shows_enabled(self):
        flags = [_flag_obj(key="online_ordering", enabled=True)]
        result = self._call(flags=flags)
        rendered = {f["key"]: f for f in result["feature_flags"]}
        self.assertTrue(rendered["online_ordering"]["enabled"])

    def test_disabled_flag_in_catalog_shows_disabled(self):
        flags = [_flag_obj(key="online_ordering", enabled=False)]
        result = self._call(flags=flags)
        rendered = {f["key"]: f for f in result["feature_flags"]}
        self.assertFalse(rendered["online_ordering"]["enabled"])

    def test_flag_config_preserved(self):
        cfg = {"limit": 100}
        flags = [_flag_obj(key="online_ordering", enabled=True, config=cfg)]
        result = self._call(flags=flags)
        rendered = {f["key"]: f for f in result["feature_flags"]}
        self.assertEqual(rendered["online_ordering"]["config"], cfg)

    # ── legacy (uncatalogued) flags ───────────────────────────────────────────
    def test_legacy_flag_not_in_catalog_appended_at_end(self):
        """A flag whose key is not in the catalog is appended as a legacy entry."""
        flags = [_flag_obj(key="legacy_custom_flag", enabled=True)]
        result = self._call(flags=flags)
        # Should have catalog flags + 1 legacy
        self.assertEqual(len(result["feature_flags"]), len(_CATALOG) + 1)
        last = result["feature_flags"][-1]
        self.assertEqual(last["key"], "legacy_custom_flag")
        self.assertTrue(last["enabled"])

    def test_legacy_flag_has_custom_legacy_description(self):
        flags = [_flag_obj(key="old_beta_feature", enabled=False)]
        result = self._call(flags=flags)
        legacy_flags = [f for f in result["feature_flags"] if f["key"] == "old_beta_feature"]
        self.assertEqual(len(legacy_flags), 1)
        self.assertIn("legacy", legacy_flags[0]["description"].lower())

    # ── plan is_active field ──────────────────────────────────────────────────
    def test_plan_is_active_true_reflected(self):
        result = self._call(plan=_plan(is_active=True))
        self.assertTrue(result["plan_is_active"])

    def test_plan_is_active_false_reflected(self):
        result = self._call(plan=_plan(is_active=False))
        self.assertFalse(result["plan_is_active"])
