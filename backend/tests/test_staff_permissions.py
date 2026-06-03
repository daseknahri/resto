"""Security tests for the waiter/owner permission split (no DB).

Verifies that tenant STAFF (waiters) are confined to their granted capabilities:
  - owner-only endpoints reject staff (_is_tenant_owner)
  - order/revenue/menu helpers honor the per-account effective permission flags
  - the menu-builder write permission requires 'edit menu'
  - serialize_user_session emits the correct effective permissions
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from accounts.models import User
from menu.views import (
    _is_tenant_owner,
    _can_edit_tenant_order,
    _can_view_revenue,
    _can_edit_menu,
)
from menu.permissions import user_can_edit_menu
from accounts.views import serialize_user_session


def _staff(*, manage_orders=True, view_revenue=False, edit_menu=False, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.Roles = User.Roles
    u.tenant_id = tenant_id
    u.perm_manage_orders = manage_orders
    u.perm_view_revenue = view_revenue
    u.perm_edit_menu = edit_menu
    u.effective_perm_manage_orders.return_value = manage_orders
    u.effective_perm_view_revenue.return_value = view_revenue
    u.effective_perm_edit_menu.return_value = edit_menu
    return u


def _req(user, tenant_id=1):
    return SimpleNamespace(user=user, tenant=SimpleNamespace(id=tenant_id))


class StaffExcludedFromOwnerOnly(SimpleTestCase):
    def test_staff_cannot_pass_owner_only_gate(self):
        self.assertFalse(_is_tenant_owner(_req(_staff())))

    def test_owner_passes_owner_only_gate(self):
        u = _staff()
        u.role = User.Roles.TENANT_OWNER
        self.assertTrue(_is_tenant_owner(_req(u)))


class OrderPermissionGating(SimpleTestCase):
    def test_staff_with_manage_orders_can_handle_orders(self):
        self.assertTrue(_can_edit_tenant_order(_req(_staff(manage_orders=True))))

    def test_staff_without_manage_orders_cannot(self):
        self.assertFalse(_can_edit_tenant_order(_req(_staff(manage_orders=False))))


class RevenuePermissionGating(SimpleTestCase):
    def test_staff_with_view_revenue_can(self):
        self.assertTrue(_can_view_revenue(_req(_staff(view_revenue=True))))

    def test_staff_without_view_revenue_cannot(self):
        self.assertFalse(_can_view_revenue(_req(_staff(view_revenue=False))))


class MenuPermissionGating(SimpleTestCase):
    def test_staff_with_edit_menu_can_via_view_helper(self):
        self.assertTrue(_can_edit_menu(_req(_staff(edit_menu=True))))

    def test_staff_without_edit_menu_cannot_via_view_helper(self):
        self.assertFalse(_can_edit_menu(_req(_staff(edit_menu=False))))

    def test_menu_builder_permission_requires_edit_menu(self):
        tenant = SimpleNamespace(id=1)
        self.assertTrue(user_can_edit_menu(_staff(edit_menu=True), tenant))
        self.assertFalse(user_can_edit_menu(_staff(edit_menu=False), tenant))


class SessionSerialization(SimpleTestCase):
    def _user(self, *, owner, manage=True, revenue=False, menu=False):
        u = MagicMock(spec=User)
        u.id = 1
        u.username = "u"
        u.email = "u@example.com"
        u.role = User.Roles.TENANT_OWNER if owner else User.Roles.TENANT_STAFF
        u.is_staff = False
        u.is_superuser = False
        u.is_platform_admin = False
        u.is_tenant_owner = owner
        u.perm_manage_orders = manage
        u.perm_view_revenue = revenue
        u.perm_edit_menu = menu
        u.tenant = None
        return u

    def test_owner_session_grants_all_permissions(self):
        data = serialize_user_session(self._user(owner=True, manage=False, revenue=False, menu=False))
        self.assertEqual(data["permissions"], {"manage_orders": True, "view_revenue": True, "edit_menu": True})
        self.assertTrue(data["can_edit_tenant_menu"])

    def test_staff_session_reflects_flags(self):
        data = serialize_user_session(self._user(owner=False, manage=True, revenue=False, menu=False))
        self.assertEqual(data["permissions"], {"manage_orders": True, "view_revenue": False, "edit_menu": False})
        self.assertFalse(data["can_edit_tenant_menu"])
