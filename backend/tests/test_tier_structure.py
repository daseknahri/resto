from django.test import SimpleTestCase, TestCase
from unittest.mock import Mock, patch

from sales.models import Lead
from sales.serializers import LeadSerializer
from sales.services import provision_lead
from tenancy.models import Plan
from tenancy.tiering import (
    canonical_plan_code,
    external_plan_code,
    is_plan_upgrade,
    plan_display_name,
    plan_entitlements,
    plan_tier_order,
)


class TieringUtilsTests(SimpleTestCase):
    def test_canonical_and_external_plan_codes(self):
        self.assertEqual(canonical_plan_code("basic"), "starter")
        self.assertEqual(canonical_plan_code("starter"), "starter")
        self.assertEqual(external_plan_code("starter"), "basic")
        self.assertEqual(external_plan_code("growth"), "growth")

    def test_plan_display_name_and_entitlements(self):
        growth = type(
            "GrowthPlan",
            (),
            {
                "code": "growth",
                "name": "Growth",
                "can_checkout": False,
                "can_whatsapp_order": True,
                "max_languages": 2,
                "is_active": False,
            },
        )()
        self.assertEqual(plan_display_name("starter"), "Basic")
        entitlements = plan_entitlements(growth)
        self.assertEqual(entitlements["tier_code"], "growth")
        self.assertEqual(entitlements["ordering_mode"], "whatsapp")
        self.assertTrue(entitlements["can_order"])
        self.assertFalse(entitlements["is_active"])

    def test_tier_order_upgrade_logic(self):
        self.assertEqual(plan_tier_order("basic"), 1)
        self.assertEqual(plan_tier_order("growth"), 2)
        self.assertEqual(plan_tier_order("pro"), 3)
        self.assertTrue(is_plan_upgrade("starter", "growth"))
        self.assertFalse(is_plan_upgrade("growth", "basic"))

    @patch("sales.services.ProvisioningJob")
    @patch("sales.services.schema_context")
    @patch("sales.services.transaction.atomic")
    def test_provision_blocks_inactive_plan(self, atomic_mock, schema_context_mock, provisioning_job_mock):
        # Provide no-op context managers for schema/transaction wrappers.
        schema_cm = Mock()
        schema_cm.__enter__ = Mock(return_value=None)
        schema_cm.__exit__ = Mock(return_value=False)
        schema_context_mock.return_value = schema_cm

        atomic_cm = Mock()
        atomic_cm.__enter__ = Mock(return_value=None)
        atomic_cm.__exit__ = Mock(return_value=False)
        atomic_mock.return_value = atomic_cm

        provisioning_job_mock.objects.filter.return_value.exists.return_value = False

        inactive_plan = type("InactivePlan", (), {"code": "growth", "is_active": False})()
        lead = type("LeadStub", (), {"id": 7, "plan": inactive_plan})()

        with self.assertRaisesMessage(ValueError, "not launched yet"):
            provision_lead(lead, domain_suffix="localhost")


class LeadSerializerTierTests(TestCase):
    def setUp(self):
        self.basic_plan = Plan.objects.create(
            code="starter",
            name="Basic",
            can_checkout=False,
            can_whatsapp_order=True,
            max_languages=1,
            is_active=True,
        )

    def test_accepts_basic_alias_for_starter_plan(self):
        serializer = LeadSerializer(
            data={
                "name": "Demo Resto",
                "email": "owner@example.com",
                "plan_code": "basic",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["plan"].code, "starter")

    def test_represent_starter_plan_as_basic_code(self):
        lead = Lead(name="Demo", email="owner@example.com", plan=self.basic_plan)
        serializer = LeadSerializer(instance=lead)
        self.assertEqual(serializer.data["plan_code"], "basic")
