from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import AdminTenantLifecycleView, AdminTenantListView


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _admin_user():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True)


def _domains_manager(primary_domain="demo.kepoli.com"):
    primary = SimpleNamespace(domain=primary_domain)
    primary_qs = SimpleNamespace(first=lambda: primary)
    fallback_qs = SimpleNamespace(first=lambda: primary)
    return SimpleNamespace(
        filter=lambda **kwargs: primary_qs,
        order_by=lambda *args, **kwargs: fallback_qs,
    )


def _tenant_stub(*, tenant_id=1, slug="demo", schema_name="demo", lifecycle_status="active", is_active=True):
    return SimpleNamespace(
        id=tenant_id,
        pk=tenant_id,
        name="Demo Restaurant",
        slug=slug,
        schema_name=schema_name,
        is_active=is_active,
        lifecycle_status=lifecycle_status,
        suspended_at=None,
        canceled_at=None,
        canceled_reason="",
        created_on=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        plan=SimpleNamespace(code="starter", name="Starter"),
        owner=SimpleNamespace(username="owner_demo"),
        domains=_domains_manager(),
        save=Mock(),
    )


class _TenantQuerySet:
    def __init__(self, rows):
        self.rows = list(rows)

    def select_related(self, *args, **kwargs):
        return self

    def prefetch_related(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def exclude(self, **kwargs):
        schema_name = kwargs.get("schema_name")
        if schema_name:
            filtered = [row for row in self.rows if getattr(row, "schema_name", None) != schema_name]
            return _TenantQuerySet(filtered)
        return self

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def count(self):
        return len(self.rows)

    def __getitem__(self, item):
        return self.rows[item]


class AdminTenantLifecycleTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.lifecycle_view = AdminTenantLifecycleView.as_view()
        self.list_view = AdminTenantListView.as_view()

    @patch("sales.views.log_admin_action")
    @patch("sales.views.get_object_or_404")
    @patch("sales.views.schema_context")
    def test_suspend_tenant(self, schema_context_mock, get_object_or_404_mock, log_admin_action_mock):
        schema_context_mock.return_value = _passthrough_cm()
        tenant = _tenant_stub(lifecycle_status="active", is_active=True)
        get_object_or_404_mock.return_value = tenant

        request = self.factory.put(
            "/api/admin-tenants/1/lifecycle/",
            {"action": "suspend", "reason": "invoice overdue"},
            format="json",
        )
        force_authenticate(request, user=_admin_user())
        response = self.lifecycle_view(request, tenant_id=1)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Tenant suspended.")
        self.assertFalse(tenant.is_active)
        self.assertEqual(tenant.lifecycle_status, "suspended")
        tenant.save.assert_called_once()
        log_admin_action_mock.assert_called_once()

    @patch("sales.views.get_object_or_404")
    @patch("sales.views.schema_context")
    def test_cancel_requires_reason(self, schema_context_mock, get_object_or_404_mock):
        schema_context_mock.return_value = _passthrough_cm()
        get_object_or_404_mock.return_value = _tenant_stub()

        request = self.factory.put(
            "/api/admin-tenants/1/lifecycle/",
            {"action": "cancel", "reason": ""},
            format="json",
        )
        force_authenticate(request, user=_admin_user())
        response = self.lifecycle_view(request, tenant_id=1)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    @patch("sales.views.log_admin_action")
    @patch("sales.views.get_object_or_404")
    @patch("sales.views.schema_context")
    def test_reactivate_tenant(self, schema_context_mock, get_object_or_404_mock, log_admin_action_mock):
        schema_context_mock.return_value = _passthrough_cm()
        tenant = _tenant_stub(lifecycle_status="suspended", is_active=False)
        tenant.suspended_at = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
        get_object_or_404_mock.return_value = tenant

        request = self.factory.put(
            "/api/admin-tenants/1/lifecycle/",
            {"action": "reactivate"},
            format="json",
        )
        force_authenticate(request, user=_admin_user())
        response = self.lifecycle_view(request, tenant_id=1)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Tenant reactivated.")
        self.assertTrue(tenant.is_active)
        self.assertEqual(tenant.lifecycle_status, "active")
        self.assertIsNone(tenant.suspended_at)
        tenant.save.assert_called_once()
        log_admin_action_mock.assert_called_once()

    @patch("sales.views.schema_context")
    @patch("sales.views.Tenant.objects")
    def test_list_returns_paginated_tenants(self, tenant_objects, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        rows = [
            _tenant_stub(tenant_id=1, slug="alpha", schema_name="alpha"),
            _tenant_stub(tenant_id=2, slug="beta", schema_name="beta"),
            _tenant_stub(tenant_id=3, slug="public", schema_name="public"),
        ]
        tenant_objects.select_related.return_value = _TenantQuerySet(rows)

        request = self.factory.get("/api/admin-tenants/?page=1&page_size=10")
        force_authenticate(request, user=_admin_user())
        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)
        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertEqual(len(response.data["results"]), 2)
