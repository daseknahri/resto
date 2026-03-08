from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.models import TierUpgradeRequest
from sales.services import create_tier_upgrade_request, decide_tier_upgrade_request
from sales.views import TierUpgradeTargetsView


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


class TierUpgradeServiceTests(SimpleTestCase):
    @patch("sales.services.transaction.atomic")
    @patch("sales.services.schema_context")
    @patch("sales.services.TierUpgradeRequest.objects")
    @patch("sales.services.Plan.objects")
    @patch("sales.services.Tenant.objects")
    def test_create_upgrade_request_success(
        self,
        tenant_objects,
        plan_objects,
        upgrade_objects,
        schema_context_mock,
        atomic_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        atomic_mock.return_value = _passthrough_cm()

        current_plan = Mock(code="starter")
        target_plan = Mock(code="growth")
        tenant_obj = Mock(id=12, plan=current_plan)
        requester = Mock(is_authenticated=True)

        tenant_objects.select_related.return_value.get.return_value = tenant_obj
        plan_objects.get.return_value = target_plan
        upgrade_objects.filter.return_value.exists.return_value = False

        created = Mock()
        upgrade_objects.create.return_value = created

        result = create_tier_upgrade_request(
            tenant=tenant_obj,
            requester=requester,
            target_plan_code="growth",
            payment_method="cash",
            payment_reference="ref-1",
            customer_note="Please upgrade",
        )

        self.assertIs(result, created)
        upgrade_objects.create.assert_called_once()
        create_kwargs = upgrade_objects.create.call_args.kwargs
        self.assertEqual(create_kwargs["tenant"], tenant_obj)
        self.assertEqual(create_kwargs["current_plan"], current_plan)
        self.assertEqual(create_kwargs["target_plan"], target_plan)
        self.assertEqual(create_kwargs["payment_method"], "cash")
        self.assertEqual(create_kwargs["payment_reference"], "ref-1")

    @patch("sales.services.transaction.atomic")
    @patch("sales.services.schema_context")
    @patch("sales.services.TierUpgradeRequest.objects")
    @patch("sales.services.Plan.objects")
    @patch("sales.services.Tenant.objects")
    def test_create_upgrade_request_rejects_if_pending_exists(
        self,
        tenant_objects,
        plan_objects,
        upgrade_objects,
        schema_context_mock,
        atomic_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        atomic_mock.return_value = _passthrough_cm()

        current_plan = Mock(code="starter")
        target_plan = Mock(code="growth")
        tenant_obj = Mock(id=44, plan=current_plan)

        tenant_objects.select_related.return_value.get.return_value = tenant_obj
        plan_objects.get.return_value = target_plan
        upgrade_objects.filter.return_value.exists.return_value = True

        with self.assertRaisesMessage(ValueError, "pending upgrade request already exists"):
            create_tier_upgrade_request(
                tenant=tenant_obj,
                requester=Mock(is_authenticated=True),
                target_plan_code="growth",
            )

    @patch("sales.services.transaction.atomic")
    @patch("sales.services.schema_context")
    @patch("sales.services.Subscription.objects")
    @patch("sales.services.TierUpgradeRequest.objects")
    def test_decide_upgrade_approve_updates_tenant_plan(
        self,
        upgrade_objects,
        subscription_objects,
        schema_context_mock,
        atomic_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        atomic_mock.return_value = _passthrough_cm()

        current_plan = Mock(code="starter", name="Basic")
        target_plan = Mock(code="growth", name="Growth", is_active=True)
        tenant_obj = Mock(id=8, slug="demo", plan=current_plan)
        request_obj = Mock(
            id=3,
            status=TierUpgradeRequest.Status.PENDING,
            tenant=tenant_obj,
            current_plan=current_plan,
            target_plan=target_plan,
            payment_reference="",
        )
        upgrade_objects.select_for_update.return_value.select_related.return_value.get.return_value = request_obj

        actor = Mock(is_authenticated=True)
        result = decide_tier_upgrade_request(
            request_id=3,
            decision="approve",
            actor=actor,
            admin_note="cash confirmed",
            payment_reference="cash-2026-03-06",
        )

        self.assertEqual(request_obj.status, TierUpgradeRequest.Status.APPROVED)
        self.assertEqual(request_obj.approved_by, actor)
        tenant_obj.save.assert_called_once()
        subscription_objects.filter.assert_called_once()
        subscription_objects.update_or_create.assert_called_once()
        self.assertEqual(result.previous_plan, current_plan)
        self.assertEqual(result.new_plan, target_plan)

    @patch("sales.services.transaction.atomic")
    @patch("sales.services.schema_context")
    @patch("sales.services.Subscription.objects")
    @patch("sales.services.TierUpgradeRequest.objects")
    def test_decide_upgrade_reject_does_not_change_subscription(
        self,
        upgrade_objects,
        subscription_objects,
        schema_context_mock,
        atomic_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        atomic_mock.return_value = _passthrough_cm()

        current_plan = Mock(code="starter", name="Basic")
        target_plan = Mock(code="growth", name="Growth", is_active=True)
        tenant_obj = Mock(id=8, slug="demo", plan=current_plan)
        request_obj = Mock(
            id=9,
            status=TierUpgradeRequest.Status.PENDING,
            tenant=tenant_obj,
            current_plan=current_plan,
            target_plan=target_plan,
            payment_reference="",
        )
        upgrade_objects.select_for_update.return_value.select_related.return_value.get.return_value = request_obj

        actor = Mock(is_authenticated=True)
        result = decide_tier_upgrade_request(
            request_id=9,
            decision="reject",
            actor=actor,
            admin_note="payment not received",
        )

        self.assertEqual(request_obj.status, TierUpgradeRequest.Status.REJECTED)
        tenant_obj.save.assert_not_called()
        subscription_objects.filter.assert_not_called()
        subscription_objects.update_or_create.assert_not_called()
        self.assertEqual(result.previous_plan, current_plan)
        self.assertEqual(result.new_plan, current_plan)


class TierUpgradeTargetsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TierUpgradeTargetsView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    def test_returns_upgrade_targets_for_tenant_owner(
        self,
        tenant_objects,
        plan_objects,
        upgrade_objects,
        schema_context_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()

        current_plan = type(
            "CurrentPlan",
            (),
            {
                "code": "starter",
                "name": "Basic",
                "can_checkout": False,
                "can_whatsapp_order": True,
                "max_languages": 1,
                "is_active": True,
            },
        )()
        growth = type(
            "GrowthPlan",
            (),
            {
                "code": "growth",
                "name": "Growth",
                "can_checkout": False,
                "can_whatsapp_order": True,
                "max_languages": 2,
                "is_active": True,
            },
        )()
        pro = type(
            "ProPlan",
            (),
            {
                "code": "pro",
                "name": "Pro",
                "can_checkout": True,
                "can_whatsapp_order": True,
                "max_languages": 3,
                "is_active": False,
            },
        )()
        tenant_obj = Mock(id=77, plan=current_plan)
        tenant_objects.select_related.return_value.get.return_value = tenant_obj
        plan_objects.all.return_value = [current_plan, growth, pro]
        upgrade_objects.filter.return_value.exists.return_value = False

        request = self.factory.get("/api/tier-upgrade-targets/")
        request.tenant = Mock(id=77)
        owner = Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=False)
        owner.role = "tenant_owner"
        owner.tenant_id = 77
        owner.pk = 1
        force_authenticate(request, user=owner)

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_tier_code"], "basic")
        self.assertEqual([row["code"] for row in response.data["targets"]], ["growth", "pro"])
        self.assertTrue(response.data["targets"][0]["can_request"])
        self.assertFalse(response.data["targets"][1]["is_active"])
