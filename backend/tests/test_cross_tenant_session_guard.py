"""AUTHZ-1 backstop: CrossTenantSessionGuardMiddleware.

A staff/owner session rides the shared cookie onto every tenant subdomain; the
middleware must downgrade it to anonymous on a FOREIGN tenant's host (fail-closed
for every owner/staff endpoint whose hand-written tenant check was forgotten),
while leaving matched staff, platform superadmins, customers, and public-host
requests untouched.

All tests are mock-based (SimpleTestCase, unsaved model instances) — no DB.
"""
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from accounts.models import User
from config.middleware import CrossTenantSessionGuardMiddleware


def _tenant(tenant_id=2, schema_name="resto_b"):
    return SimpleNamespace(id=tenant_id, schema_name=schema_name)


def _user(role=User.Roles.TENANT_OWNER, tenant_id=1, user_id=10):
    user = User(id=user_id, username=f"u{user_id}", role=role)
    user.tenant_id = tenant_id
    return user


class CrossTenantSessionGuardTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.seen_request = None

        def get_response(request):
            self.seen_request = request
            return SimpleNamespace(status_code=200)

        self.middleware = CrossTenantSessionGuardMiddleware(get_response)

    def _run(self, *, user, tenant, path="/api/owner/z-report/"):
        request = self.factory.get(path)
        if tenant is not None:
            request.tenant = tenant
        request.user = user
        request.session = {"customer_id": 777}
        self.middleware(request)
        return self.seen_request

    # ── The leak class dies ────────────────────────────────────────────────

    def test_mismatched_owner_is_downgraded_to_anonymous(self):
        seen = self._run(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(tenant_id=2))
        self.assertIsInstance(seen.user, AnonymousUser)

    def test_mismatched_staff_is_downgraded_to_anonymous(self):
        seen = self._run(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(tenant_id=2))
        self.assertIsInstance(seen.user, AnonymousUser)

    def test_tenant_bound_role_with_null_tenant_is_downgraded(self):
        """Fail-closed: an owner/staff user with no tenant owns no staff identity anywhere."""
        seen = self._run(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=None), tenant=_tenant(tenant_id=2))
        self.assertIsInstance(seen.user, AnonymousUser)

    def test_downgrade_is_logged_with_both_tenant_ids(self):
        with self.assertLogs("app.request", level="WARNING") as captured:
            self._run(user=_user(tenant_id=1, user_id=42), tenant=_tenant(tenant_id=2))
        structured = captured.records[0].structured
        self.assertEqual(structured["event"], "cross_tenant_session_downgraded")
        self.assertEqual(structured["user_id"], 42)
        self.assertEqual(structured["user_tenant_id"], 1)
        self.assertEqual(structured["request_tenant_id"], 2)

    # ── Legitimate identities pass through untouched ───────────────────────

    def test_matched_owner_keeps_identity(self):
        user = _user(role=User.Roles.TENANT_OWNER, tenant_id=2)
        seen = self._run(user=user, tenant=_tenant(tenant_id=2))
        self.assertIs(seen.user, user)

    def test_platform_superadmin_is_exempt_on_any_tenant_host(self):
        user = _user(role=User.Roles.PLATFORM_SUPERADMIN, tenant_id=None)
        seen = self._run(user=user, tenant=_tenant(tenant_id=2))
        self.assertIs(seen.user, user)

    def test_django_superuser_is_exempt_despite_default_owner_role(self):
        """createsuperuser accounts carry role=tenant_owner + tenant=None; the
        is_superuser bypass must match the existing guards or they lock out."""
        user = _user(role=User.Roles.TENANT_OWNER, tenant_id=None)
        user.is_superuser = True
        seen = self._run(user=user, tenant=_tenant(tenant_id=2))
        self.assertIs(seen.user, user)

    def test_anonymous_user_passes_through(self):
        user = AnonymousUser()
        seen = self._run(user=user, tenant=_tenant(tenant_id=2))
        self.assertIs(seen.user, user)

    def test_public_host_without_tenant_attr_is_skipped(self):
        """TenantAwareMainMiddleware never sets request.tenant on the main host."""
        user = _user(tenant_id=1)
        seen = self._run(user=user, tenant=None)
        self.assertIs(seen.user, user)

    def test_public_schema_tenant_is_skipped(self):
        user = _user(tenant_id=1)
        seen = self._run(user=user, tenant=_tenant(tenant_id=99, schema_name="public"))
        self.assertIs(seen.user, user)

    # ── Collateral-damage guards ───────────────────────────────────────────

    def test_downgrade_preserves_the_session(self):
        """The same browser session may carry a customer identity — never flush it."""
        seen = self._run(user=_user(tenant_id=1), tenant=_tenant(tenant_id=2))
        self.assertEqual(seen.session.get("customer_id"), 777)

    def test_downgrade_only_affects_this_request(self):
        """The middleware swaps request.user; it must not mutate or persist anything else."""
        user = _user(tenant_id=1)
        self._run(user=user, tenant=_tenant(tenant_id=2))
        # The original user object is untouched (no role/tenant rewrites).
        self.assertEqual(user.tenant_id, 1)
        self.assertEqual(user.role, User.Roles.TENANT_OWNER)


class MiddlewareRegistrationTests(SimpleTestCase):
    """A backstop that isn't installed protects nothing — pin its registration."""

    def test_guard_is_registered_after_authentication_middleware(self):
        from django.conf import settings

        middleware = settings.MIDDLEWARE
        guard = "config.middleware.CrossTenantSessionGuardMiddleware"
        auth = "django.contrib.auth.middleware.AuthenticationMiddleware"
        self.assertIn(guard, middleware)
        self.assertIn(auth, middleware)
        self.assertGreater(middleware.index(guard), middleware.index(auth))
