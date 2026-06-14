"""
Tests for the public SEO sitemap view: GET /sitemap.xml (config.sitemap).

Unit-level (SimpleTestCase + mocks — no real DB or schema switch). The view
iterates tenants cross-schema via tenancy.models.Profile, exactly like
DirectoryView, so we mock the chained queryset's .iterator().
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from config.sitemap import sitemap_view


def _fake_profile(slug, name):
    tenant = SimpleNamespace(slug=slug, name=name)
    return SimpleNamespace(tenant=tenant)


def _patch_profiles(active_rows):
    """Patch tenancy.models.Profile so the chained query yields *active_rows*.

    The view calls
        Profile.objects.filter(...).select_related(...).order_by(...).iterator()
    The returned MagicMock records the .filter(...) kwargs (so a test can assert
    the active-lifecycle filter is applied) and yields the supplied rows.
    """
    mock_profile = MagicMock()
    chain = mock_profile.objects.filter.return_value.select_related.return_value.order_by.return_value
    chain.iterator.return_value = iter(active_rows)
    return patch("tenancy.models.Profile", mock_profile), mock_profile


class SitemapViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self):
        req = self.factory.get("/sitemap.xml")
        return sitemap_view(req)

    @override_settings(BRAND_DOMAIN="kepoli.example")
    def test_static_pages_present(self):
        patcher, _ = _patch_profiles([])
        with patcher:
            resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/xml")
        body = resp.content.decode()
        # XML sitemap envelope
        self.assertIn("<urlset", body)
        self.assertIn("sitemaps.org/schemas/sitemap/0.9", body)
        # Each static public page appears as an absolute URL on the brand host
        for path in ("/", "/browse", "/directory", "/privacy", "/terms", "/contact"):
            self.assertIn(f"<loc>https://kepoli.example{path}</loc>", body)
        # /reserve is a noindex form (see useSeoMeta INDEXABLE_ROUTE_NAMES) and
        # must NOT be advertised — listing it would be a contradictory signal.
        self.assertNotIn("<loc>https://kepoli.example/reserve</loc>", body)

    @override_settings(BRAND_DOMAIN="kepoli.example")
    def test_active_tenants_listed_suspended_excluded(self):
        # The mocked query (like the real DB filter) returns ONLY active tenants.
        rows = [_fake_profile("bistro", "Bistro"), _fake_profile("souk", "Souk")]
        patcher, mock_profile = _patch_profiles(rows)
        with patcher:
            resp = self._get()
        body = resp.content.decode()

        # Both active tenants' storefronts appear.
        self.assertIn("<loc>https://kepoli.example/order/bistro</loc>", body)
        self.assertIn("<loc>https://kepoli.example/order/souk</loc>", body)

        # The query is constrained to ACTIVE, directory-opted-in, published tenants
        # — which is what excludes a suspended tenant from ever reaching the loop.
        _, filter_kwargs = mock_profile.objects.filter.call_args
        self.assertEqual(filter_kwargs.get("tenant__lifecycle_status"), "active")
        self.assertTrue(filter_kwargs.get("directory_opt_in"))
        self.assertTrue(filter_kwargs.get("is_menu_published"))

        # A tenant that is NOT in the returned (active) set must not appear.
        self.assertNotIn("/order/suspended-resto", body)

    @override_settings(BRAND_DOMAIN="kepoli.example")
    def test_cache_header_set(self):
        patcher, _ = _patch_profiles([])
        with patcher:
            resp = self._get()
        self.assertIn("max-age=", resp["Cache-Control"])

    @override_settings(BRAND_DOMAIN="kepoli.example")
    def test_resilient_when_tenant_query_raises(self):
        # A total failure of the cross-schema query must NOT 500 the sitemap —
        # it degrades to static pages only.
        mock_profile = MagicMock()
        mock_profile.objects.filter.side_effect = RuntimeError("schema boom")
        with patch("tenancy.models.Profile", mock_profile):
            resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("<loc>https://kepoli.example/</loc>", body)
        # No tenant URLs, but the document is still valid.
        self.assertIn("</urlset>", body)

    @override_settings(BRAND_DOMAIN="kepoli.example")
    def test_one_bad_tenant_row_skipped(self):
        good = _fake_profile("good", "Good")
        # A row whose .tenant access blows up must be skipped, not fatal.
        bad = MagicMock()
        type(bad).tenant = property(lambda self: (_ for _ in ()).throw(ValueError("bad row")))
        patcher, _ = _patch_profiles([bad, good])
        with patcher:
            resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("<loc>https://kepoli.example/order/good</loc>", body)
