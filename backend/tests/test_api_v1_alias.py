"""
RISK API-1 (first slice) — /api/v1/ alias, zero behavior change.

Verifies that a representative set of existing endpoints resolve to the
EXACT same view callable under both the legacy `/api/...` path and the new
`/api/v1/...` alias, in both the tenant urlconf (config.urls) and the public
urlconf (config.public_urls). Also checks that reverse() for existing
(un-namespaced) route names still returns the legacy `/api/...` URL, and
that the v1 alias is additionally reachable via the "v1:" namespace.

All DB-free (SimpleTestCase + django.urls.resolve/reverse only).
"""
from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse


class TenantApiV1AliasTests(SimpleTestCase):
    """config.urls (ROOT_URLCONF) — tenant-schema API routes."""

    @override_settings(ROOT_URLCONF="config.urls")
    def test_tenant_meta_alias_resolves_to_same_view(self):
        legacy = resolve("/api/meta/")
        v1 = resolve("/api/v1/meta/")
        self.assertEqual(legacy.func, v1.func)
        self.assertEqual(legacy.view_name, "tenant-meta")

    @override_settings(ROOT_URLCONF="config.urls")
    def test_tenant_place_order_alias_resolves_to_same_view(self):
        legacy = resolve("/api/place-order/")
        v1 = resolve("/api/v1/place-order/")
        self.assertEqual(legacy.func, v1.func)

    @override_settings(ROOT_URLCONF="config.urls")
    def test_tenant_router_viewset_alias_resolves_to_same_view(self):
        # DRF DefaultRouter-registered viewset (tenant_router), list + detail.
        legacy_list = resolve("/api/dishes/")
        v1_list = resolve("/api/v1/dishes/")
        self.assertEqual(legacy_list.func, v1_list.func)

        legacy_detail = resolve("/api/dishes/1/")
        v1_detail = resolve("/api/v1/dishes/1/")
        self.assertEqual(legacy_detail.func, v1_detail.func)

    @override_settings(ROOT_URLCONF="config.urls")
    def test_tenant_shared_route_alias_resolves_to_same_view(self):
        # A route defined once in shared_api_urlpatterns and included into
        # both the tenant and public urlconfs — must alias identically here.
        legacy = resolve("/api/login/")
        v1 = resolve("/api/v1/login/")
        self.assertEqual(legacy.func, v1.func)

    @override_settings(ROOT_URLCONF="config.urls")
    def test_reverse_of_existing_name_is_unchanged(self):
        # Existing reverse() calls anywhere in the app must keep pointing at
        # the legacy /api/ URL, not silently switch to /api/v1/.
        self.assertEqual(reverse("tenant-meta"), "/api/meta/")
        self.assertEqual(reverse("v1:tenant-meta"), "/api/v1/meta/")


class PublicApiV1AliasTests(SimpleTestCase):
    """config.public_urls (PUBLIC_SCHEMA_URLCONF) — public-schema API routes."""

    @override_settings(ROOT_URLCONF="config.public_urls")
    def test_public_health_alias_resolves_to_same_view(self):
        legacy = resolve("/api/health/")
        v1 = resolve("/api/v1/health/")
        self.assertEqual(legacy.func, v1.func)
        self.assertEqual(legacy.view_name, "health")

    @override_settings(ROOT_URLCONF="config.public_urls")
    def test_public_router_viewset_alias_resolves_to_same_view(self):
        # DRF DefaultRouter-registered viewset (shared_api_router).
        legacy = resolve("/api/leads/")
        v1 = resolve("/api/v1/leads/")
        self.assertEqual(legacy.func, v1.func)

    @override_settings(ROOT_URLCONF="config.public_urls")
    def test_public_only_route_alias_resolves_to_same_view(self):
        # Defined directly in public_urls.py (not shared), still gets aliased.
        legacy = resolve("/api/unsubscribe/sometoken/")
        v1 = resolve("/api/v1/unsubscribe/sometoken/")
        self.assertEqual(legacy.func, v1.func)

    @override_settings(ROOT_URLCONF="config.public_urls")
    def test_non_api_routes_are_not_aliased(self):
        # Sanity check: sitemap.xml has no api/ prefix, so it must NOT gain a
        # /api/v1/sitemap.xml twin, and admin is untouched too.
        from django.urls.exceptions import Resolver404

        with self.assertRaises(Resolver404):
            resolve("/api/v1/sitemap.xml")

    @override_settings(ROOT_URLCONF="config.public_urls")
    def test_reverse_of_existing_name_is_unchanged(self):
        self.assertEqual(reverse("health"), "/api/health/")
        self.assertEqual(reverse("v1:health"), "/api/v1/health/")
