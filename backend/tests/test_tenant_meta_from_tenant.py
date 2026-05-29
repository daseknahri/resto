"""
Unit tests for TenantMetaSerializer.from_tenant in tenancy/serializers.py.

The static factory method assembles a TenantMetaSerializer from a tenant object.
Pure-logic branches:

  - tenant.plan is None → entitlements={}, feature_flags=[]
  - tenant.plan has no feature_flags attr → plan_flags=[]
  - tenant.plan has feature_flags → each flag serialized as {key, enabled, config}
  - tenant has no profile attr → profile=None
  - tenant has profile → it is passed through
  - grace_period_days is always 7
  - payment_overdue_since / deletion_requested_at forwarded from tenant

All tests are unit-level (SimpleTestCase — _rating_summary is mocked,
feature_flags.all() is mocked).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from tenancy.serializers import TenantMetaSerializer

_RATING_PATH = "tenancy.serializers.TenantMetaSerializer._rating_summary"


def _tenant(*, name="Demo", slug="demo", plan=None, has_profile=True,
             payment_overdue_since=None, deletion_requested_at=None):
    t = SimpleNamespace(
        name=name,
        slug=slug,
        plan=plan,
        payment_overdue_since=payment_overdue_since,
        deletion_requested_at=deletion_requested_at,
    )
    if has_profile:
        t.profile = SimpleNamespace(tagline="Great food")
    return t


def _plan_with_flags(*flag_items):
    """Build a fake Plan whose feature_flags.all() returns *flag_items."""
    flags_qs = MagicMock()
    flags_qs.all.return_value = flag_items
    return SimpleNamespace(code="starter", name="Starter", feature_flags=flags_qs)


def _call(tenant, *, request=None):
    """Call from_tenant with _rating_summary mocked out."""
    with patch(_RATING_PATH, return_value={"average": None, "count": 0}):
        return TenantMetaSerializer.from_tenant(tenant, request=request)


class FromTenantNoPlanTests(SimpleTestCase):

    def test_no_plan_entitlements_is_empty_dict(self):
        ser = _call(_tenant(plan=None))
        self.assertEqual(ser.instance["entitlements"], {})

    def test_no_plan_feature_flags_is_empty_list(self):
        ser = _call(_tenant(plan=None))
        self.assertEqual(ser.instance["feature_flags"], [])

    def test_no_plan_name_and_slug_forwarded(self):
        ser = _call(_tenant(name="My Restaurant", slug="my-restaurant", plan=None))
        self.assertEqual(ser.instance["name"], "My Restaurant")
        self.assertEqual(ser.instance["slug"], "my-restaurant")


class FromTenantWithFlagsTests(SimpleTestCase):

    def test_feature_flags_serialized_correctly(self):
        flag = SimpleNamespace(key="whatsapp_order", enabled=True, config=None)
        plan = _plan_with_flags(flag)
        ser = _call(_tenant(plan=plan))
        self.assertEqual(len(ser.instance["feature_flags"]), 1)
        self.assertEqual(ser.instance["feature_flags"][0], {
            "key": "whatsapp_order",
            "enabled": True,
            "config": None,
        })

    def test_plan_without_feature_flags_attr_results_in_empty_list(self):
        """If the plan has no feature_flags attribute, plan_flags stays []."""
        plan = SimpleNamespace(code="basic", name="Basic")  # no feature_flags attr
        ser = _call(_tenant(plan=plan))
        self.assertEqual(ser.instance["feature_flags"], [])

    def test_multiple_flags_all_collected(self):
        flags = [
            SimpleNamespace(key="key_a", enabled=True, config={"x": 1}),
            SimpleNamespace(key="key_b", enabled=False, config=None),
        ]
        plan = _plan_with_flags(*flags)
        ser = _call(_tenant(plan=plan))
        self.assertEqual(len(ser.instance["feature_flags"]), 2)


class FromTenantProfileTests(SimpleTestCase):

    def test_profile_passed_through_when_present(self):
        ser = _call(_tenant(has_profile=True))
        self.assertIsNotNone(ser.instance["profile"])

    def test_profile_is_none_when_absent(self):
        ser = _call(_tenant(has_profile=False))
        self.assertIsNone(ser.instance["profile"])


class FromTenantMetaTests(SimpleTestCase):

    def test_grace_period_days_is_always_seven(self):
        ser = _call(_tenant())
        self.assertEqual(ser.instance["grace_period_days"], 7)

    def test_payment_overdue_since_forwarded(self):
        from datetime import datetime
        dt = datetime(2026, 1, 1)
        ser = _call(_tenant(payment_overdue_since=dt))
        self.assertEqual(ser.instance["payment_overdue_since"], dt)

    def test_deletion_requested_at_forwarded(self):
        from datetime import datetime
        dt = datetime(2026, 3, 15)
        ser = _call(_tenant(deletion_requested_at=dt))
        self.assertEqual(ser.instance["deletion_requested_at"], dt)

    def test_rating_summary_included(self):
        ser = _call(_tenant())
        self.assertIn("rating_summary", ser.instance)
