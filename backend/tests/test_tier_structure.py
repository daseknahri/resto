from django.test import SimpleTestCase
from unittest.mock import Mock, patch
from types import SimpleNamespace

from sales.serializers import LeadSerializer
from sales.services import provision_lead
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
        # Per-plan gating: this plan has WhatsApp ordering (but not checkout) → in_app mode.
        self.assertEqual(entitlements["ordering_mode"], "in_app")
        self.assertTrue(entitlements["can_order"])
        self.assertTrue(entitlements["can_whatsapp_order"])
        self.assertFalse(entitlements["is_active"])

    def test_entitlements_gate_browse_only_plan(self):
        """A plan with no ordering channels is browse/menu-only (gating turned on)."""
        basic = SimpleNamespace(
            code="starter", name="Basic", can_checkout=False,
            can_whatsapp_order=False, max_languages=1, is_active=True,
        )
        ents = plan_entitlements(basic)
        self.assertEqual(ents["ordering_mode"], "menu_only")
        self.assertFalse(ents["can_order"])
        self.assertFalse(ents["can_whatsapp_order"])
        self.assertFalse(ents["can_in_app_order"])

    def test_entitlements_checkout_plan(self):
        """Checkout-capable plan reports checkout mode and all channels open."""
        pro = SimpleNamespace(
            code="pro", name="Pro", can_checkout=True,
            can_whatsapp_order=True, max_languages=3, is_active=True,
        )
        ents = plan_entitlements(pro)
        self.assertEqual(ents["ordering_mode"], "checkout")
        self.assertTrue(ents["can_order"])
        self.assertTrue(ents["can_checkout"])
        self.assertTrue(ents["can_in_app_order"])

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


class LeadSerializerTierTests(SimpleTestCase):
    """Test LeadSerializer plan_code aliasing without touching the database."""

    def test_accepts_basic_alias_for_starter_plan(self):
        # Validate that "basic" is canonicalized to the Plan with code "starter".
        starter_plan = SimpleNamespace(code="starter", name="Basic")
        with patch("sales.serializers.Plan.objects.get", return_value=starter_plan):
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
        # Patch ModelSerializer.to_representation (the nearest ancestor that owns
        # it) so we exercise only LeadSerializer's own plan_code override logic,
        # without needing a fully-wired Lead model graph (tenant, stats, etc.).
        starter_plan = SimpleNamespace(code="starter")
        base_data = {"name": "Demo", "plan_code": "starter"}
        with patch(
            "rest_framework.serializers.ModelSerializer.to_representation",
            return_value=dict(base_data),
        ):
            lead = Mock()
            lead.plan = starter_plan
            serializer = LeadSerializer(instance=lead)
            data = serializer.to_representation(lead)
            self.assertEqual(data["plan_code"], "basic")
