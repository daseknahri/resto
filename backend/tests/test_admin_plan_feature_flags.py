from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import AdminPlanFeatureFlagListView, AdminPlanFeatureFlagUpdateView


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _admin_user():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True, pk=1, id=1)


def _plan_stub(plan_id: int, *, code: str, name: str, is_active: bool = True):
    return SimpleNamespace(id=plan_id, code=code, name=name, is_active=is_active)


class AdminPlanFeatureFlagViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.list_view = AdminPlanFeatureFlagListView.as_view()
        self.update_view = AdminPlanFeatureFlagUpdateView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views.FeatureFlag.objects")
    @patch("sales.views.Plan.objects")
    def test_list_returns_catalog_and_plan_rows(self, plan_objects, feature_flag_objects, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        starter = _plan_stub(1, code="starter", name="Basic")
        growth = _plan_stub(2, code="growth", name="Growth")
        plan_objects.order_by.return_value = [starter, growth]

        feature_flag_objects.filter.return_value.order_by.return_value = [
            SimpleNamespace(plan_id=1, key="owner_table_management", enabled=True, config={"max_tables": 40}),
            SimpleNamespace(plan_id=2, key="checkout_payments", enabled=False, config=None),
        ]

        request = self.factory.get("/api/admin-plan-feature-flags/")
        force_authenticate(request, user=_admin_user())
        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("catalog", response.data)
        self.assertIn("plans", response.data)
        self.assertEqual(len(response.data["plans"]), 2)
        self.assertEqual(response.data["plans"][0]["plan_code"], "basic")
        basic_flag = next(
            row for row in response.data["plans"][0]["feature_flags"] if row["key"] == "owner_table_management"
        )
        self.assertTrue(basic_flag["enabled"])
        self.assertEqual(basic_flag["config"], {"max_tables": 40})

    @patch("sales.views.log_admin_action")
    @patch("sales.views.schema_context")
    @patch("sales.views.FeatureFlag.objects")
    @patch("sales.views.get_object_or_404")
    def test_update_upserts_flags_for_plan(
        self,
        get_object_or_404_mock,
        feature_flag_objects,
        schema_context_mock,
        log_admin_action_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        plan = _plan_stub(11, code="starter", name="Basic")
        get_object_or_404_mock.return_value = plan
        feature_flag_objects.filter.return_value.order_by.return_value = [
            SimpleNamespace(
                plan_id=11,
                key="multi_language_content",
                enabled=True,
                config={"max_languages": 2},
            )
        ]

        request = self.factory.put(
            "/api/admin-plan-feature-flags/basic/",
            {
                "feature_flags": [
                    {
                        "key": "multi_language_content",
                        "enabled": True,
                        "config": {"max_languages": 2},
                    }
                ]
            },
            format="json",
        )
        force_authenticate(request, user=_admin_user())
        response = self.update_view(request, plan_code="basic")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        feature_flag_objects.update_or_create.assert_called_once_with(
            plan=plan,
            key="multi_language_content",
            defaults={
                "enabled": True,
                "config": {"max_languages": 2},
            },
        )
        self.assertEqual(response.data["plan"]["plan_code"], "basic")
        log_admin_action_mock.assert_called_once()

    def test_update_rejects_unknown_feature_flag_key(self):
        request = self.factory.put(
            "/api/admin-plan-feature-flags/basic/",
            {"feature_flags": [{"key": "unknown_flag", "enabled": True}]},
            format="json",
        )
        force_authenticate(request, user=_admin_user())
        response = self.update_view(request, plan_code="basic")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("feature_flags", response.data)
