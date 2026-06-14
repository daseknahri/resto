"""
Unit tests for remaining private helpers in accounts/views.py:
  - _is_tenant_owner(request, tenant)  [two-arg form in accounts.views]
  - _serialize_address
  - build_frontend_base_url

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from accounts.views import (
    _is_tenant_owner,
    _serialize_address,
    build_frontend_base_url,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(
    *,
    authenticated=True,
    superuser=False,
    staff=False,
    platform_admin=False,
    role=None,
    tenant_id=1,
    tenant=None,
):
    from accounts.models import User as UserModel
    u = MagicMock(spec=UserModel)
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.is_staff = staff
    u.is_platform_admin = platform_admin
    u.role = role or UserModel.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.tenant = tenant
    u.Roles = UserModel.Roles
    return u


def _tenant_ns(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _request(user=None, tenant=None):
    return SimpleNamespace(user=user or _user(), tenant=tenant)


# ══════════════════════════════════════════════════════════════════════════════
# _is_tenant_owner(request, tenant)  — accounts.views, two-arg form
# ══════════════════════════════════════════════════════════════════════════════

class IsTenantOwnerAccountsTests(SimpleTestCase):
    """
    The accounts.views._is_tenant_owner takes (request, tenant) unlike the
    menu.views version that takes only (request).  It also only grants access
    to TENANT_OWNER role (not TENANT_STAFF), unless the user is a superuser/admin.
    """

    def test_unauthenticated_returns_false(self):
        req = _request(user=_user(authenticated=False))
        self.assertFalse(_is_tenant_owner(req, _tenant_ns(1)))

    def test_superuser_returns_true_regardless_of_tenant(self):
        req = _request(user=_user(superuser=True, tenant_id=99))
        self.assertTrue(_is_tenant_owner(req, _tenant_ns(1)))

    def test_staff_alone_returns_false(self):
        # OPS-5d: a Django is_staff flag is no longer a cross-tenant owner bypass.
        req = _request(user=_user(staff=True, tenant_id=99))
        self.assertFalse(_is_tenant_owner(req, _tenant_ns(1)))

    def test_platform_admin_returns_true(self):
        req = _request(user=_user(platform_admin=True, tenant_id=99))
        self.assertTrue(_is_tenant_owner(req, _tenant_ns(1)))

    def test_none_tenant_returns_false(self):
        req = _request(user=_user(tenant_id=1))
        self.assertFalse(_is_tenant_owner(req, None))

    def test_wrong_tenant_id_returns_false(self):
        req = _request(user=_user(tenant_id=99))
        self.assertFalse(_is_tenant_owner(req, _tenant_ns(1)))

    def test_tenant_owner_matching_tenant_returns_true(self):
        from accounts.models import User as UserModel
        req = _request(user=_user(role=UserModel.Roles.TENANT_OWNER, tenant_id=1))
        self.assertTrue(_is_tenant_owner(req, _tenant_ns(1)))

    def test_tenant_staff_with_matching_tenant_returns_false(self):
        """Staff role is explicitly excluded from this check (owner only)."""
        from accounts.models import User as UserModel
        req = _request(user=_user(role=UserModel.Roles.TENANT_STAFF, tenant_id=1))
        self.assertFalse(_is_tenant_owner(req, _tenant_ns(1)))

    def test_no_user_attribute_returns_false(self):
        req = SimpleNamespace(tenant=_tenant_ns(1))
        self.assertFalse(_is_tenant_owner(req, _tenant_ns(1)))


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_address
# ══════════════════════════════════════════════════════════════════════════════

class SerializeAddressTests(SimpleTestCase):
    def _addr(self, *, label="Home", location_url="", lat=None, lng=None):
        return SimpleNamespace(
            pk=42,
            label=label,
            address="123 Main Street",
            location_url=location_url,
            lat=lat,
            lng=lng,
            created_at=SimpleNamespace(isoformat=lambda: "2025-06-01T12:00:00"),
        )

    def test_required_keys_present(self):
        result = _serialize_address(self._addr())
        for key in ("id", "label", "address", "location_url", "lat", "lng", "created_at"):
            self.assertIn(key, result)

    def test_id_is_pk(self):
        result = _serialize_address(self._addr())
        self.assertEqual(result["id"], 42)

    def test_none_label_returns_empty_string(self):
        result = _serialize_address(self._addr(label=None))
        self.assertEqual(result["label"], "")

    def test_none_location_url_returns_empty_string(self):
        result = _serialize_address(self._addr(location_url=None))
        self.assertEqual(result["location_url"], "")

    def test_lat_lng_preserved(self):
        result = _serialize_address(self._addr(lat=33.5, lng=-7.6))
        self.assertEqual(result["lat"], 33.5)
        self.assertEqual(result["lng"], -7.6)

    def test_created_at_isoformat(self):
        result = _serialize_address(self._addr())
        self.assertEqual(result["created_at"], "2025-06-01T12:00:00")


# ══════════════════════════════════════════════════════════════════════════════
# build_frontend_base_url
# ══════════════════════════════════════════════════════════════════════════════

def _req(host="demo.example.com"):
    req = MagicMock()
    req.get_host.return_value = host
    return req


def _user_with_tenant(domain="demo.example.com"):
    primary = SimpleNamespace(domain=domain)
    domains_qs = MagicMock()
    domains_qs.filter.return_value.first.return_value = primary
    tenant = SimpleNamespace(domains=domains_qs)
    u = MagicMock()
    u.tenant = tenant
    return u


def _user_no_tenant():
    u = MagicMock()
    u.tenant = None
    return u


class BuildFrontendBaseUrlTests(SimpleTestCase):
    # OPS-5f: the no-tenant fallback no longer honours request.get_host() (it is
    # attacker-controlled → host-header poisoning of the password-reset link). It now
    # uses a server-authoritative canonical host (BRAND_DOMAIN / PUBLIC_MENU_BASE_URL /
    # TENANT_DOMAIN_SUFFIX, falling back to localhost in dev).

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_no_tenant_uses_brand_domain_not_request_host(self):
        # The request claims a spoofed host; the link must NOT use it.
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://app.kepoli.com")

    @override_settings(BRAND_DOMAIN="", PUBLIC_MENU_BASE_URL="https://menu.kepoli.com", TENANT_DOMAIN_SUFFIX="")
    def test_no_tenant_falls_back_to_public_menu_base_url(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://menu.kepoli.com")

    @override_settings(BRAND_DOMAIN="", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="kepoli.app")
    def test_no_tenant_falls_back_to_tenant_domain_suffix(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "https://kepoli.app")

    @override_settings(BRAND_DOMAIN="localhost", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_localhost_brand_uses_http_with_port_5173(self):
        result = build_frontend_base_url(_req("evil.attacker.com"), _user_no_tenant())
        self.assertEqual(result, "http://localhost:5173")

    def test_tenant_primary_domain_overrides_request_host(self):
        result = build_frontend_base_url(
            _req("api.example.com"),
            _user_with_tenant("demo.example.com"),
        )
        self.assertEqual(result, "https://demo.example.com")

    def test_tenant_localhost_domain_returns_http(self):
        result = build_frontend_base_url(
            _req("api.example.com"),
            _user_with_tenant("demo.localhost"),
        )
        self.assertEqual(result, "http://demo.localhost:5173")

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_no_primary_domain_uses_canonical_not_request_host(self):
        # Tenant exists but has no primary domain → still must NOT use the spoofable host.
        u = MagicMock()
        tenant = MagicMock()
        tenant.domains.filter.return_value.first.return_value = None
        u.tenant = tenant
        result = build_frontend_base_url(_req("evil.attacker.com"), u)
        self.assertEqual(result, "https://app.kepoli.com")
