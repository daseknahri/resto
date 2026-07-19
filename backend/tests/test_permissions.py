"""
Direct unit tests for DRF permission classes:
  - menu.permissions.IsTenantEditorOrReadOnly
  - sales.permissions.IsPlatformAdmin
  - sales.permissions.IsTenantEditor
  - sales.permissions.IsTenantOwner

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from accounts.models import User
from menu.permissions import IsTenantEditorOrReadOnly
from sales.permissions import (
    IsPlatformAdmin,
    IsTenantEditor,
    IsTenantOwner,
    IsTenantOwnerAccessDenied,
    IsTenantOwnerForbidden,
    IsTenantOwnerStaffForbidden,
    user_owns_tenant_id,
)


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
# IsTenantOwner
# ══════════════════════════════════════════════════════════════════════════════

class IsTenantOwnerTests(SimpleTestCase):
    perm = IsTenantOwner()
    view = None

    def test_tenant_owner_with_matching_tenant_allowed(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(self.perm.has_permission(req, self.view))

    def test_tenant_staff_with_matching_tenant_denied(self):
        """Owner-exclusive: staff with a matching tenant must still be denied."""
        req = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_wrong_tenant_owner_denied(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=99), tenant=_tenant(1))
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_no_tenant_denied(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=None)
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

    # ── has_object_permission ──────────────────────────────────────────────

    def test_object_matching_tenant_owner_allowed(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=1)
        self.assertTrue(self.perm.has_object_permission(req, self.view, obj))

    def test_object_mismatched_tenant_denied(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=99)
        self.assertFalse(self.perm.has_object_permission(req, self.view, obj))

    def test_object_staff_with_matching_tenant_denied(self):
        req = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=1)
        self.assertFalse(self.perm.has_object_permission(req, self.view, obj))

    def test_object_superuser_bypasses_tenant_check(self):
        req = _request(user=_user(superuser=True, tenant_id=99), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=1)
        self.assertTrue(self.perm.has_object_permission(req, self.view, obj))

    def test_object_platform_admin_bypasses_tenant_check(self):
        req = _request(user=_user(platform_admin=True, tenant_id=99), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=1)
        self.assertTrue(self.perm.has_object_permission(req, self.view, obj))

    # ── RISK AUTHZ-1: exact-body preservation for the call-site migration ────────
    # DRF renders `permission.message` as the 403 {"detail": ...} when has_permission
    # returns False for an authenticated non-owner. These lock the exact legacy bodies
    # the inline _is_tenant_owner guards returned, so migrating a view to these classes
    # is byte-for-byte behavior-preserving.

    def test_message_is_the_legacy_owner_body(self):
        self.assertEqual(IsTenantOwner.message, "Owner access required.")

    def test_access_denied_variant_same_policy_different_body(self):
        # Same owner policy (subclass), only the 403 text differs.
        self.assertTrue(issubclass(IsTenantOwnerAccessDenied, IsTenantOwner))
        self.assertEqual(IsTenantOwnerAccessDenied.message, "Access denied.")
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(IsTenantOwnerAccessDenied().has_permission(req, None))
        staff = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertFalse(IsTenantOwnerAccessDenied().has_permission(staff, None))

    def test_forbidden_variant_same_policy_different_body(self):
        self.assertTrue(issubclass(IsTenantOwnerForbidden, IsTenantOwner))
        self.assertEqual(IsTenantOwnerForbidden.message, "Forbidden.")
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(IsTenantOwnerForbidden().has_permission(req, None))
        staff = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertFalse(IsTenantOwnerForbidden().has_permission(staff, None))

    def test_staff_forbidden_variant_carries_code_in_dict_message(self):
        # The staff endpoints' body uniquely includes a `code`. A dict message is what DRF
        # renders verbatim as the response body (integration-covered in test_owner_staff_views).
        self.assertTrue(issubclass(IsTenantOwnerStaffForbidden, IsTenantOwner))
        self.assertEqual(
            IsTenantOwnerStaffForbidden.message,
            {"detail": "Owner access required.", "code": "forbidden"},
        )
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(IsTenantOwnerStaffForbidden().has_permission(req, None))
        staff = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertFalse(IsTenantOwnerStaffForbidden().has_permission(staff, None))

    def test_object_unauthenticated_denied(self):
        req = _request(user=_user(authenticated=False), tenant=_tenant(1))
        obj = SimpleNamespace(tenant_id=1)
        self.assertFalse(self.perm.has_object_permission(req, self.view, obj))

    def test_object_no_obj_tenant_id_denied(self):
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        obj = SimpleNamespace()
        self.assertFalse(self.perm.has_object_permission(req, self.view, obj))


# ══════════════════════════════════════════════════════════════════════════════
# user_owns_tenant_id — the single owner-check shared by IsTenantOwner and the two
# _is_tenant_owner view helpers (RISK AUTHZ-1 consolidation)
# ══════════════════════════════════════════════════════════════════════════════

class UserOwnsTenantIdTests(SimpleTestCase):
    def test_owner_with_matching_tenant_allowed(self):
        self.assertTrue(user_owns_tenant_id(_user(role=User.Roles.TENANT_OWNER, tenant_id=1), 1))

    def test_staff_with_matching_tenant_denied(self):
        self.assertFalse(user_owns_tenant_id(_user(role=User.Roles.TENANT_STAFF, tenant_id=1), 1))

    def test_owner_wrong_tenant_denied(self):
        self.assertFalse(user_owns_tenant_id(_user(role=User.Roles.TENANT_OWNER, tenant_id=99), 1))

    def test_none_tenant_id_denied_for_owner(self):
        self.assertFalse(user_owns_tenant_id(_user(role=User.Roles.TENANT_OWNER, tenant_id=1), None))

    def test_unauthenticated_denied(self):
        self.assertFalse(user_owns_tenant_id(_user(authenticated=False), 1))

    def test_none_user_denied(self):
        self.assertFalse(user_owns_tenant_id(None, 1))

    def test_superuser_bypasses_tenant(self):
        # superuser is allowed even with a mismatched / absent tenant id
        self.assertTrue(user_owns_tenant_id(_user(superuser=True, tenant_id=99), 1))
        self.assertTrue(user_owns_tenant_id(_user(superuser=True, tenant_id=99), None))

    def test_platform_admin_bypasses_tenant(self):
        self.assertTrue(user_owns_tenant_id(_user(platform_admin=True, tenant_id=99), None))


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
