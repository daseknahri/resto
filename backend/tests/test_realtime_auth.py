"""Tests for the shared owner/staff authorization rule and the broadcast guard.

user_can_edit_tenant is the single source of truth for both HTTP edit permission
and the WebSocket OwnerConsumer, so these lock down exactly who may act as a
tenant editor (and therefore who may join the owner socket).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from accounts.models import User
from menu.permissions import user_can_edit_tenant
from realtime.broadcast import broadcast

_TENANT = SimpleNamespace(id=1)


def _user(**overrides):
    base = dict(
        is_authenticated=True,
        is_superuser=False,
        is_staff=False,
        is_platform_admin=False,
        tenant_id=1,
        role=User.Roles.TENANT_OWNER,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TenantEditAuthTests(SimpleTestCase):
    def test_owner_of_tenant_allowed(self):
        self.assertTrue(user_can_edit_tenant(_user(role=User.Roles.TENANT_OWNER), _TENANT))

    def test_staff_of_tenant_allowed(self):
        self.assertTrue(user_can_edit_tenant(_user(role=User.Roles.TENANT_STAFF), _TENANT))

    def test_user_of_other_tenant_denied(self):
        self.assertFalse(user_can_edit_tenant(_user(tenant_id=999), _TENANT))

    def test_non_staff_role_denied(self):
        # A customer (or any non owner/staff role) on this tenant must be denied —
        # this is what keeps customers off the owner socket.
        self.assertFalse(user_can_edit_tenant(_user(role="customer"), _TENANT))

    def test_unauthenticated_denied(self):
        self.assertFalse(user_can_edit_tenant(_user(is_authenticated=False), _TENANT))
        self.assertFalse(user_can_edit_tenant(None, _TENANT))

    def test_platform_admin_allowed_across_tenants(self):
        self.assertTrue(user_can_edit_tenant(_user(is_platform_admin=True, tenant_id=999), _TENANT))
        self.assertTrue(user_can_edit_tenant(_user(is_superuser=True, tenant_id=999), _TENANT))

    def test_regular_user_without_tenant_denied(self):
        self.assertFalse(user_can_edit_tenant(_user(), None))


class BroadcastGuardTests(SimpleTestCase):
    def test_broadcast_never_raises_and_returns_bool(self):
        # The HTTP request path must never break because of realtime — broadcast
        # always returns a bool and swallows any error (no channel layer here).
        result = broadcast("resto_a", "owner", "order.new", {"order_number": "X"})
        self.assertIsInstance(result, bool)
