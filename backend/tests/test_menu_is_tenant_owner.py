"""
Unit tests for menu.views._is_tenant_owner(request).

The function returns True only when the request's tenant matches the user's tenant
and the role is TENANT_OWNER, OR the user is a superuser / platform admin. TENANT_STAFF
(waiters) are intentionally excluded — owner-exclusive endpoints must reject staff;
staff capabilities go through the perm-specific helpers instead.

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.views import _is_tenant_owner


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(
    *,
    authenticated=True,
    superuser=False,
    staff=False,
    platform_admin=False,
    role="tenant_owner",
    tenant_id=1,
):
    from accounts.models import User

    class Roles:
        TENANT_OWNER = "tenant_owner"
        TENANT_STAFF = "tenant_staff"

    u = SimpleNamespace(
        is_authenticated=authenticated,
        is_superuser=superuser,
        is_staff=staff,
        is_platform_admin=platform_admin,
        role=role,
        tenant_id=tenant_id,
        Roles=Roles,
    )
    return u


def _tenant(id=1):
    return SimpleNamespace(id=id)


def _request(user=None, tenant=None):
    req = SimpleNamespace(user=user or _user(), tenant=tenant)
    return req


# ══════════════════════════════════════════════════════════════════════════════
# menu.views._is_tenant_owner
# ══════════════════════════════════════════════════════════════════════════════

class MenuIsTenantOwnerTests(SimpleTestCase):

    # ── unauthenticated ───────────────────────────────────────────────────────

    def test_unauthenticated_returns_false(self):
        req = _request(user=_user(authenticated=False), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    def test_no_user_returns_false(self):
        req = SimpleNamespace(user=None, tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    # ── privileged users always pass regardless of tenant ─────────────────────

    def test_superuser_returns_true(self):
        req = _request(user=_user(superuser=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(_is_tenant_owner(req))

    def test_staff_alone_returns_false(self):
        # OPS-5d: a Django is_staff flag is no longer a cross-tenant owner bypass.
        req = _request(user=_user(staff=True, tenant_id=99), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    def test_platform_admin_returns_true(self):
        req = _request(user=_user(platform_admin=True, tenant_id=99), tenant=_tenant(1))
        self.assertTrue(_is_tenant_owner(req))

    # ── no tenant on request ──────────────────────────────────────────────────

    def test_no_tenant_on_request_returns_false(self):
        req = _request(user=_user(tenant_id=1), tenant=None)
        self.assertFalse(_is_tenant_owner(req))

    # ── tenant ID mismatch ────────────────────────────────────────────────────

    def test_wrong_tenant_id_returns_false(self):
        req = _request(user=_user(tenant_id=99), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    # ── matching tenant, correct roles ────────────────────────────────────────

    def test_tenant_owner_role_returns_true(self):
        req = _request(user=_user(role="tenant_owner", tenant_id=1), tenant=_tenant(1))
        self.assertTrue(_is_tenant_owner(req))

    def test_tenant_staff_role_returns_false(self):
        """TENANT_STAFF must NOT pass the owner-only gate (security fix)."""
        req = _request(user=_user(role="tenant_staff", tenant_id=1), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    def test_unrecognised_role_returns_false(self):
        req = _request(user=_user(role="platform_superadmin", tenant_id=1), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))
