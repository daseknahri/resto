"""
Tests for the social-crawler OG endpoint.

GET /api/og/?path=<original-request-uri>

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.test import RequestFactory

from accounts.og_views import OGView


def _make_request(path_param="/", host="example.com"):
    factory = RequestFactory()
    req = factory.get("/api/og/", {"path": path_param}, HTTP_HOST=host)
    return req


def _call(path_param="/", host="example.com", cache_hit=None):
    req = _make_request(path_param=path_param, host=host)
    view = OGView.as_view()
    with patch("accounts.og_views.cache") as mock_cache:
        mock_cache.get.return_value = cache_hit
        mock_cache.set = MagicMock()
        resp = view(req)
    return resp, mock_cache


# ── Host-based tenant resolution ──────────────────────────────────────────────

class TenantHostResolutionTests(SimpleTestCase):

    def _domain_lookup(self, tenant_name, tagline, hero_url=None, logo_url=None):
        """Return a (Domain mock, Profile mock) pair for a given tenant."""
        tenant = MagicMock()
        tenant.name = tenant_name
        tenant.is_active = True
        tenant.slug = "test-slug"

        domain_obj = MagicMock()
        domain_obj.tenant = tenant

        profile = MagicMock()
        profile.tagline = tagline
        profile.hero_url = hero_url or ""
        profile.logo_url = logo_url or ""

        return domain_obj, profile, tenant

    def test_tenant_name_is_escaped(self):
        """Tenant name containing <script> must appear as &lt;script&gt; in HTML."""
        domain_obj, profile, tenant = self._domain_lookup(
            tenant_name='Cafe <script>alert(1)</script>',
            tagline="Good food",
            hero_url="https://example.com/hero.png",
        )

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = _make_request(path_param="/", host="cafe.example.com")
            view = OGView.as_view()
            resp = view(req)

        html = resp.content.decode()
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertEqual(resp.status_code, 200)

    def test_tagline_used_as_description(self):
        """Profile.tagline becomes the og:description when present."""
        domain_obj, profile, _ = self._domain_lookup(
            tenant_name="Tacos House",
            tagline="Best tacos in town",
            hero_url="https://example.com/hero.png",
        )

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = _make_request(path_param="/", host="tacos.example.com")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertIn("Best tacos in town", html)

    def test_hero_url_used_as_image_when_valid(self):
        """A valid https hero_url is emitted as og:image."""
        domain_obj, profile, _ = self._domain_lookup(
            tenant_name="Tacos House",
            tagline="Best tacos in town",
            hero_url="https://cdn.example.com/hero.jpg",
        )

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = _make_request(path_param="/", host="tacos.example.com")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertIn("https://cdn.example.com/hero.jpg", html)


# ── Slug (path) resolution ────────────────────────────────────────────────────

class SlugPathResolutionTests(SimpleTestCase):

    def test_order_slug_path_resolves_tenant(self):
        """/order/<slug> in path param triggers slug-based tenant resolution."""
        tenant = MagicMock()
        tenant.name = "Tacos House"
        tenant.is_active = True
        tenant.slug = "tacos-house"

        profile = MagicMock()
        profile.tagline = "Finest tacos"
        profile.hero_url = "https://example.com/img.jpg"
        profile.logo_url = ""

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Tenant") as MockTenant, \
             patch("accounts.og_views.Profile") as MockProfile:
            # Domain lookup fails (not a tenant-specific host)
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("not found")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockTenant.objects.get.return_value = tenant
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = _make_request(path_param="/order/tacos-house", host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertIn("Tacos House", html)
        self.assertIn("Finest tacos", html)
        # Verify slug was used as the lookup key
        MockTenant.objects.get.assert_called_once_with(slug="tacos-house", is_active=True)

    def test_non_order_path_does_not_resolve_by_slug(self):
        """A random path that doesn't match /order/<slug> stays on platform defaults."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("not found")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/about", host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertIn("Kepoli", html)


# ── Platform fallback ─────────────────────────────────────────────────────────

class PlatformFallbackTests(SimpleTestCase):

    def test_platform_defaults_when_nothing_matches(self):
        """When no tenant is found, the platform Kepoli defaults are used."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/", host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertIn("Kepoli", html)
        self.assertIn("Order food, shop local", html)
        self.assertIn("icon-512.png", html)

    def test_platform_fallback_og_tags_present(self):
        """Platform fallback HTML contains required OG meta tags."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/", host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        for tag in [
            'og:type', 'og:site_name', 'og:title', 'og:description',
            'og:image', 'og:url', 'twitter:card', 'twitter:title',
            'twitter:description', 'twitter:image',
        ]:
            self.assertIn(tag, html, f"Missing tag: {tag}")


# ── Non-http image URL fallback ───────────────────────────────────────────────

class ImageUrlFallbackTests(SimpleTestCase):

    def _setup(self, hero_url, logo_url, host="tacos.example.com"):
        tenant = MagicMock()
        tenant.name = "Tacos House"
        tenant.is_active = True

        domain_obj = MagicMock()
        domain_obj.tenant = tenant

        profile = MagicMock()
        profile.tagline = "Good tacos"
        profile.hero_url = hero_url
        profile.logo_url = logo_url

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = _make_request(path_param="/", host=host)
            resp = OGView.as_view()(req)

        return resp.content.decode()

    def test_non_http_hero_falls_back_to_icon(self):
        """A hero_url like 'data:...' must fall back to the platform icon."""
        html = self._setup(hero_url="data:image/png;base64,abc", logo_url="")
        self.assertIn("icon-512.png", html)
        self.assertNotIn("data:image", html)

    def test_non_http_logo_falls_back_to_icon(self):
        """A logo_url with no scheme falls back to the platform icon."""
        html = self._setup(hero_url="", logo_url="/static/logo.png")
        self.assertIn("icon-512.png", html)

    def test_logo_used_when_hero_absent(self):
        """When hero is empty, logo is used if it's a valid http URL."""
        html = self._setup(hero_url="", logo_url="https://cdn.example.com/logo.png")
        self.assertIn("https://cdn.example.com/logo.png", html)
        self.assertNotIn("icon-512.png", html)

    def test_both_missing_uses_icon(self):
        """When both hero and logo are empty, fall back to icon."""
        html = self._setup(hero_url="", logo_url="")
        self.assertIn("icon-512.png", html)


# ── Path normalisation ────────────────────────────────────────────────────────

class PathNormalisationTests(SimpleTestCase):

    def test_path_without_leading_slash_normalised(self):
        """A ?path value not starting with '/' is treated as '/'."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="order/tacos-house", host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        # The normalised "/" should appear in the canonical URL and refresh tag
        self.assertIn('content="0;url=/"', html)

    def test_path_is_html_escaped_in_output(self):
        """Dangerous characters in path are escaped in the HTML."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param='/"onmouseover="alert(1)"', host="kepoli.app")
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        self.assertNotIn('"onmouseover=', html)


# ── Response headers ──────────────────────────────────────────────────────────

class ResponseHeaderTests(SimpleTestCase):

    def test_content_type_is_html(self):
        """Response Content-Type must be text/html; charset=utf-8."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/", host="kepoli.app")
            resp = OGView.as_view()(req)

        self.assertIn("text/html", resp["Content-Type"])
        self.assertIn("utf-8", resp["Content-Type"])

    def test_cache_control_header_present(self):
        """Response must include Cache-Control: public, max-age=600."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/", host="kepoli.app")
            resp = OGView.as_view()(req)

        self.assertEqual(resp["Cache-Control"], "public, max-age=600")

    def test_cache_hit_skips_db_and_still_returns_html(self):
        """A cache hit must return the cached HTML without touching DB."""
        cached_html = "<html>cached</html>"
        with patch("accounts.og_views.cache") as mock_cache:
            mock_cache.get.return_value = cached_html

            req = _make_request(path_param="/", host="kepoli.app")
            resp = OGView.as_view()(req)

        self.assertEqual(resp.content.decode(), cached_html)
        self.assertIn("text/html", resp["Content-Type"])
        self.assertEqual(resp["Cache-Control"], "public, max-age=600")

    def test_cache_key_stored_on_miss(self):
        """On a cache miss, the rendered HTML must be stored under the correct key."""
        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            req = _make_request(path_param="/menu", host="kepoli.app")
            OGView.as_view()(req)

        expected_key = "ogpage:kepoli.app:/menu"
        call_args = mock_cache.set.call_args
        self.assertEqual(call_args[0][0], expected_key)
        self.assertEqual(call_args[0][2], 600)
