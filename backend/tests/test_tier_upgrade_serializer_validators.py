"""
Unit tests for untested validation methods in sales/serializers.py:

  TierUpgradeRequestSerializer
    - get_current_plan_code / get_current_plan_name
    - get_target_plan_code / get_target_plan_name

  TierUpgradeRequestCreateSerializer
    - validate_target_plan_code
    - validate (cross-field: tenant plan + upgrade check)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sales.serializers import (
    TierUpgradeRequestSerializer,
    TierUpgradeRequestCreateSerializer,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _plan(code="growth", name="Growth"):
    return SimpleNamespace(code=code, name=name)


def _upgrade_request(current_plan=None, target_plan=None):
    return SimpleNamespace(
        current_plan=current_plan,
        target_plan=target_plan,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TierUpgradeRequestSerializer — get_* plan code/name methods
# ══════════════════════════════════════════════════════════════════════════════

class TierUpgradeRequestSerializerGetMethodsTests(SimpleTestCase):
    """get_current/target_plan_code/name delegate to tiering helpers."""

    def _s(self):
        return TierUpgradeRequestSerializer()

    def test_get_current_plan_code_with_plan(self):
        obj = _upgrade_request(current_plan=_plan(code="growth"))
        result = self._s().get_current_plan_code(obj)
        # growth → external code (external_plan_code("growth") = "growth")
        self.assertIsNotNone(result)

    def test_get_current_plan_code_with_no_plan(self):
        obj = _upgrade_request(current_plan=None)
        result = self._s().get_current_plan_code(obj)
        # external_plan_code("") should return a string (not crash)
        self.assertIsInstance(result, str)

    def test_get_current_plan_name_with_plan(self):
        obj = _upgrade_request(current_plan=_plan(code="growth", name="Growth"))
        result = self._s().get_current_plan_name(obj)
        self.assertIsInstance(result, str)

    def test_get_current_plan_name_with_no_plan(self):
        obj = _upgrade_request(current_plan=None)
        result = self._s().get_current_plan_name(obj)
        self.assertIsInstance(result, str)

    def test_get_target_plan_code_with_plan(self):
        obj = _upgrade_request(target_plan=_plan(code="growth"))
        result = self._s().get_target_plan_code(obj)
        self.assertIsInstance(result, str)

    def test_get_target_plan_code_with_no_plan(self):
        obj = _upgrade_request(target_plan=None)
        result = self._s().get_target_plan_code(obj)
        self.assertIsInstance(result, str)

    def test_get_target_plan_name_with_plan(self):
        obj = _upgrade_request(target_plan=_plan(code="growth", name="Growth"))
        result = self._s().get_target_plan_name(obj)
        self.assertIsInstance(result, str)

    def test_get_target_plan_name_with_no_plan(self):
        obj = _upgrade_request(target_plan=None)
        result = self._s().get_target_plan_name(obj)
        self.assertIsInstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# TierUpgradeRequestCreateSerializer — validate_target_plan_code
# ══════════════════════════════════════════════════════════════════════════════

class ValidateTargetPlanCodeTests(SimpleTestCase):
    """validate_target_plan_code: normalises code, looks up Plan, or raises."""

    def _s(self):
        return TierUpgradeRequestCreateSerializer()

    def test_valid_plan_code_returns_plan_object(self):
        plan = _plan(code="growth")
        with patch("sales.serializers.Plan") as mock_plan_cls:
            mock_plan_cls.objects.get.return_value = plan
            result = self._s().validate_target_plan_code("growth")
        self.assertIs(result, plan)

    def test_invalid_plan_code_raises_validation_error(self):
        with patch("sales.serializers.Plan") as mock_plan_cls:
            mock_plan_cls.DoesNotExist = Exception
            mock_plan_cls.objects.get.side_effect = mock_plan_cls.DoesNotExist("not found")
            with self.assertRaises(ValidationError) as cm:
                self._s().validate_target_plan_code("nonexistent")
        self.assertIn("Invalid plan", str(cm.exception))

    def test_external_code_is_canonicalised_before_lookup(self):
        """'basic' → canonical 'starter' before Plan.objects.get."""
        plan = _plan(code="starter")
        with patch("sales.serializers.Plan") as mock_plan_cls, \
             patch("sales.serializers.canonical_plan_code", return_value="starter") as mock_canonical:
            mock_plan_cls.objects.get.return_value = plan
            self._s().validate_target_plan_code("basic")
        mock_canonical.assert_called_once_with("basic")
        mock_plan_cls.objects.get.assert_called_once_with(code="starter")


# ══════════════════════════════════════════════════════════════════════════════
# TierUpgradeRequestCreateSerializer — validate (cross-field)
# ══════════════════════════════════════════════════════════════════════════════

class TierUpgradeRequestCreateValidateTests(SimpleTestCase):
    """validate: checks tenant plan is set and target is an upgrade."""

    def _s(self, tenant=None):
        s = TierUpgradeRequestCreateSerializer()
        s.context["tenant"] = tenant
        return s

    def _tenant(self, plan=None):
        return SimpleNamespace(plan=plan)

    def test_valid_upgrade_passes(self):
        current_plan = _plan(code="starter")
        target_plan = _plan(code="growth")
        tenant = self._tenant(plan=current_plan)
        attrs = {"target_plan_code": target_plan, "payment_method": "cash"}
        with patch("sales.serializers.is_plan_upgrade", return_value=True):
            result = self._s(tenant=tenant).validate(attrs)
        self.assertIn("target_plan", result)
        self.assertNotIn("target_plan_code", result)

    def test_missing_target_plan_raises(self):
        """target_plan_code missing from attrs → raises."""
        tenant = self._tenant(plan=_plan(code="starter"))
        attrs = {"payment_method": "cash"}  # no target_plan_code
        with self.assertRaises(ValidationError):
            self._s(tenant=tenant).validate(attrs)

    def test_missing_current_plan_raises(self):
        """Tenant has no plan → raises."""
        tenant = self._tenant(plan=None)
        target_plan = _plan(code="growth")
        attrs = {"target_plan_code": target_plan}
        with self.assertRaises(ValidationError):
            self._s(tenant=tenant).validate(attrs)

    def test_same_tier_not_an_upgrade_raises(self):
        """is_plan_upgrade=False → raises."""
        current_plan = _plan(code="growth")
        target_plan = _plan(code="growth")
        tenant = self._tenant(plan=current_plan)
        attrs = {"target_plan_code": target_plan}
        with patch("sales.serializers.is_plan_upgrade", return_value=False):
            with self.assertRaises(ValidationError) as cm:
                self._s(tenant=tenant).validate(attrs)
        self.assertIn("higher tier", str(cm.exception))

    def test_target_plan_moved_to_target_plan_key(self):
        """After validation, attrs contains 'target_plan' not 'target_plan_code'."""
        current_plan = _plan(code="starter")
        target_plan = _plan(code="growth")
        tenant = self._tenant(plan=current_plan)
        attrs = {"target_plan_code": target_plan}
        with patch("sales.serializers.is_plan_upgrade", return_value=True):
            result = self._s(tenant=tenant).validate(attrs)
        self.assertIs(result["target_plan"], target_plan)
        self.assertNotIn("target_plan_code", result)
