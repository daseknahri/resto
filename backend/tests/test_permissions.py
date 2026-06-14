"""
Direct unit tests for DRF permission classes:
  - menu.permissions.IsTenantEditorOrReadOnly
  - sales.permissions.IsPlatformAdmin
  - sales.permissions.IsTenantEditor

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from accounts.models import User
from menu.permissions import IsTenantEditorOrReadOnly
from sales.permissions import IsPlatformAdmin, IsTenantEditor


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(*, authenticated=True, superuser=False, staff=False, platform_admin=False,
          role=None, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.is_staff = staff
    u.is_platform_admin = platform_admin
    u.role = role or User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1, is_active=True):
    return SimpleNamespace(id=tenant_id, is_active=is_active)


def _request(method="GET", user=None, tenant=None):
    req = SimpleNamespace(
        method=method,
        user=user or _user(),
        tenant=tenant,
    )
    return req


# ══════════════════════════════════════════════════════════════════════════════
# IsPlatformAdmin
# ══════════════════════════════════════════════════════════════════════════════

class IsPlatformAdminTests(SimpleTestCase):
    perm = IsPlatformAdmin()
    view = None

    def test_superuser_allowed(self):
        req = _request(user=_user(superuser=True))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_staff_only_denied(self):
        """is_staff alone does not grant platform-admin access (OPS-5b PRIV-ESC hardening)."""
        req = _request(user=_user(staff=True))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_platform_admin_allowed(self):
        req = _request(user=_user(platform_admin=True))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_regular_user_denied(self):
        req = _request(user=_user())
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_unauthenticated_denied(self):
        req = _request(user=_user(authenticated=False))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_no_user_attribute_denied(self):
        req = SimpleNamespace(method="GET")
        self.assertFalse(self.perm.has_permission(req, self.view))


# ══════════════════════════════════════════════════════════════════════════════
# IsTenantEditor
# ══════════════════════════════════════════════════════════════════════════════

class IsTenantEditorTests(SimpleTestCase):
    perm = IsTenantEditor()
    view = None

    def test_tenant_owner_with_matching_tenant_allowed(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_tenant_staff_with_matching_tenant_allowed(self):
        req = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_wrong_tenant_denied(self):
        req = _request(user=_user(tenant_id=99), tenant=_tenant(1))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_no_tenant_denied(self):
        req = _request(user=_user(tenant_id=1), tenant=None)
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_unauthenticated_denied(self):
        req = _request(user=_user(authenticated=False), tenant=_tenant(1))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_superuser_bypasses_tenant_check(self):
        req = _request(user=_user(superuser=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_platform_admin_bypasses_tenant_check(self):
        req = _request(user=_user(platform_admin=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_inactive_tenant_denied(self):
        req = _request(user=_user(tenant_id=1), tenant=_tenant(1, is_active=False))
        self.assertFalse(self.perm.has_permission(req, self.view))


# ══════════════════════════════════════════════════════════════════════════════
# IsTenantEditorOrReadOnly
# ══════════════════════════════════════════════════════════════════════════════

class IsTenantEditorOrReadOnlyTests(SimpleTestCase):
    perm = IsTenantEditorOrReadOnly()
    view = None

    def test_safe_method_allows_anyone(self):
        """GET, HEAD, OPTIONS always allowed."""
        for method in ("GET", "HEAD", "OPTIONS"):
            req = _request(method=method, user=_user(authenticated=False))
            self.assertTrue(self.perm.has_permission(req, self.view), f"SAFE {method} denied")

    def test_write_requires_authenticated_editor(self):
        req = _request(method="POST", user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_write_denied_for_unauthenticated(self):
        req = _request(method="POST", user=_user(authenticated=False))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_write_denied_for_wrong_tenant(self):
        req = _request(method="POST", user=_user(tenant_id=99), tenant=_tenant(1))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_write_denied_when_no_tenant(self):
        req = _request(method="POST", user=_user(tenant_id=1), tenant=None)
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_write_allowed_for_superuser_on_any_tenant(self):
        req = _request(method="PUT", user=_user(superuser=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_write_allowed_for_platform_admin(self):
        req = _request(method="DELETE", user=_user(platform_admin=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_tenant_staff_can_write(self):
        req = _request(method="PATCH", user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))
