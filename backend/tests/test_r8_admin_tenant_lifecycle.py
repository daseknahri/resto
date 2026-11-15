"""Run 8 G2 — A-38: TenantAdmin.save_model no longer silently rewrites lifecycle."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib import admin as django_admin
from django.test import RequestFactory, SimpleTestCase

from sales.models import AdminAuditLog
from tenancy.admin import TenantAdmin
from tenancy.models import Plan, Tenant


def _request():
    request = RequestFactory().post("/admin/")
    request.user = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True, pk=1)
    return request


class TenantAdminSaveModelTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = TenantAdmin(Tenant, django_admin.site)
        self.request = _request()

    def _tenant(self, *, is_active, lifecycle_status):
        plan = Plan(name="Test", code="test")
        tenant = Tenant(
            name="Demo",
            slug="demo",
            schema_name="demo",
            plan=plan,
            is_active=is_active,
            lifecycle_status=lifecycle_status,
        )
        tenant.save = MagicMock()
        return tenant

    def _save(self, tenant, previous):
        qs = MagicMock()
        qs.values_list.return_value.first.return_value = previous
        with (
            patch.object(Tenant.objects, "filter", return_value=qs),
            patch("tenancy.admin.log_admin_action") as log_action,
            patch.object(self.model_admin, "message_user") as message_user,
        ):
            self.model_admin.save_model(self.request, tenant, None, True)
        return log_action, message_user

    def test_explicit_canceled_lifecycle_is_respected(self):
        tenant = self._tenant(is_active=True, lifecycle_status="canceled")
        log_action, message_user = self._save(tenant, (True, "active"))
        self.assertEqual(tenant.lifecycle_status, "canceled")
        self.assertFalse(tenant.is_active)
        message_user.assert_called_once()
        self.assertIn("Canceled", message_user.call_args.args[1])
        log_action.assert_called_once()
        self.assertEqual(
            log_action.call_args.kwargs["action"],
            AdminAuditLog.Actions.TENANT_DEACTIVATED,
        )

    def test_explicit_active_lifecycle_reactivates(self):
        tenant = self._tenant(is_active=False, lifecycle_status="active")
        log_action, message_user = self._save(tenant, (False, "suspended"))
        self.assertEqual(tenant.lifecycle_status, "active")
        self.assertTrue(tenant.is_active)
        message_user.assert_called_once()
        self.assertIn("Active", message_user.call_args.args[1])
        log_action.assert_called_once()
        self.assertEqual(
            log_action.call_args.kwargs["action"],
            AdminAuditLog.Actions.TENANT_REACTIVATED,
        )

    def test_untouched_lifecycle_derived_from_deactivation_with_message(self):
        tenant = self._tenant(is_active=False, lifecycle_status="active")
        _log_action, message_user = self._save(tenant, (True, "active"))
        self.assertEqual(tenant.lifecycle_status, "suspended")
        message_user.assert_called_once()
        self.assertIn("Suspended because the tenant was deactivated", message_user.call_args.args[1])

    def test_untouched_lifecycle_derived_from_reactivation_with_message(self):
        tenant = self._tenant(is_active=True, lifecycle_status="suspended")
        _log_action, message_user = self._save(tenant, (False, "suspended"))
        self.assertEqual(tenant.lifecycle_status, "active")
        self.assertIsNone(tenant.suspended_at)
        self.assertIsNone(tenant.canceled_at)
        message_user.assert_called_once()
        self.assertIn("Active because the tenant was reactivated", message_user.call_args.args[1])

    def test_no_rewrite_or_message_when_nothing_changed(self):
        tenant = self._tenant(is_active=True, lifecycle_status="active")
        _log_action, message_user = self._save(tenant, (True, "active"))
        self.assertEqual(tenant.lifecycle_status, "active")
        self.assertTrue(tenant.is_active)
        message_user.assert_not_called()
