"""
Tests for the Redis-backed server-side cache on TenantMetaView and the
invalidation logic in ProfileView.perform_update().

All tests are SimpleTestCase (no database).  The Django cache and DRF
serializer are both mocked so the suite never touches Redis or Postgres.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from tenancy.api import (
    ProfileView,
    TenantMetaView,
    _META_CACHE_LOCALE_VARIANTS,
    _bust_tenant_meta_cache,
    _meta_cache_key,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _fake_meta_data(slug="demo"):
    return {"name": "Demo Restaurant", "slug": slug, "plan": {}, "profile": None}


def _make_tenant(slug="demo"):
    return SimpleNamespace(id=1, name="Demo Restaurant", slug=slug)


def _anon_request(factory, path="/api/meta/", **kwargs):
    req = factory.get(path, **kwargs)
    req.tenant = _make_tenant()
    return req


def _auth_request(factory, path="/api/meta/", **kwargs):
    req = factory.get(path, **kwargs)
    req.tenant = _make_tenant()
    # Use MagicMock so DRF's SessionAuthentication (.is_active) and throttles
    # (.pk) resolve without AttributeError.  CSRF is skipped for safe methods.
    user = MagicMock()
    user.is_authenticated = True
    user.is_active = True
    user.pk = 1
    req.user = user
    return req


# ── TenantMetaView cache-hit tests ─────────────────────────────────────────────

class TenantMetaCacheHitTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_returns_cached_data_without_calling_serializer(
        self, mock_serializer_cls, mock_cache
    ):
        """A warm cache returns the stored dict directly; serializer is never called."""
        mock_cache.get.return_value = _fake_meta_data()

        req = _anon_request(self.factory)
        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "demo")
        mock_serializer_cls.from_tenant.assert_not_called()

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_does_not_call_cache_set(self, mock_serializer_cls, mock_cache):
        """On a cache hit we must not write back to the cache (no double-set)."""
        mock_cache.get.return_value = _fake_meta_data()

        req = _anon_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_cache.set.assert_not_called()

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_uses_correct_key_for_lang_param(
        self, mock_serializer_cls, mock_cache
    ):
        """Cache lookup uses the ?lang= query param in the key."""
        mock_cache.get.return_value = _fake_meta_data()

        req = self.factory.get("/api/meta/?lang=ar")
        req.tenant = _make_tenant()
        TenantMetaView.as_view()(req)

        mock_cache.get.assert_called_once_with("meta:v1:demo:ar")

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_uses_auth_key_for_authenticated_users(
        self, mock_serializer_cls, mock_cache
    ):
        """Authenticated owner requests are keyed with '_auth' locale scope."""
        mock_cache.get.return_value = _fake_meta_data()

        req = _auth_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_cache.get.assert_called_once_with("meta:v1:demo:_auth")


# ── TenantMetaView cache-miss tests ────────────────────────────────────────────

class TenantMetaCacheMissTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _mock_serializer(self, mock_cls, slug="demo"):
        """Configure the TenantMetaSerializer mock to return fresh data."""
        fake_data = _fake_meta_data(slug)
        instance = MagicMock()
        instance.data = fake_data
        mock_cls.from_tenant.return_value = instance
        return fake_data

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_calls_serializer(self, mock_serializer_cls, mock_cache):
        """On a miss the serializer is called once with the correct tenant."""
        mock_cache.get.return_value = None
        self._mock_serializer(mock_serializer_cls)

        req = _anon_request(self.factory)
        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_serializer_cls.from_tenant.assert_called_once()
        call_kwargs = mock_serializer_cls.from_tenant.call_args
        self.assertEqual(call_kwargs.args[0].slug, "demo")

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_stores_result_with_ttl(self, mock_serializer_cls, mock_cache):
        """After a miss, the computed result is written to cache with the correct TTL."""
        mock_cache.get.return_value = None
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = _anon_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_cache.set.assert_called_once_with("meta:v1:demo:", fake_data, timeout=300)

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_with_lang_param_uses_lang_in_key(
        self, mock_serializer_cls, mock_cache
    ):
        """Cache set uses the same key that was looked up — including ?lang=."""
        mock_cache.get.return_value = None
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = self.factory.get("/api/meta/?lang=fr")
        req.tenant = _make_tenant()
        TenantMetaView.as_view()(req)

        mock_cache.set.assert_called_once_with("meta:v1:demo:fr", fake_data, timeout=300)

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_authenticated_uses_auth_key(
        self, mock_serializer_cls, mock_cache
    ):
        """Authenticated miss stores under the '_auth' key."""
        mock_cache.get.return_value = None
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = _auth_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_cache.set.assert_called_once_with("meta:v1:demo:_auth", fake_data, timeout=300)

    @patch("tenancy.api.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_no_tenant_returns_400_without_touching_cache(
        self, mock_serializer_cls, mock_cache
    ):
        """Missing tenant → 400 response; cache must not be read or written."""
        req = self.factory.get("/api/meta/")
        # req.tenant is deliberately not set

        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()


# ── Cache key helper tests ──────────────────────────────────────────────────────

class MetaCacheKeyTests(SimpleTestCase):
    def test_key_includes_version_slug_and_locale(self):
        key = _meta_cache_key("myslug", "fr")
        self.assertEqual(key, "meta:v1:myslug:fr")

    def test_empty_locale_produces_valid_key(self):
        key = _meta_cache_key("myslug", "")
        self.assertEqual(key, "meta:v1:myslug:")

    def test_different_tenants_produce_different_keys(self):
        self.assertNotEqual(
            _meta_cache_key("tenant-a", "en"),
            _meta_cache_key("tenant-b", "en"),
        )

    def test_different_locales_produce_different_keys(self):
        self.assertNotEqual(
            _meta_cache_key("demo", "en"),
            _meta_cache_key("demo", "ar"),
        )


# ── Cache invalidation helper tests ────────────────────────────────────────────

class BustTenantMetaCacheTests(SimpleTestCase):
    @patch("tenancy.api.cache")
    def test_bust_deletes_all_known_locale_variants(self, mock_cache):
        """_bust_tenant_meta_cache must evict every locale variant in one call."""
        _bust_tenant_meta_cache("demo")

        expected_keys = [f"meta:v1:demo:{loc}" for loc in _META_CACHE_LOCALE_VARIANTS]
        mock_cache.delete_many.assert_called_once_with(expected_keys)

    @patch("tenancy.api.cache")
    def test_bust_with_empty_slug_is_a_no_op(self, mock_cache):
        """An empty slug means no tenant — no cache key to evict."""
        _bust_tenant_meta_cache("")
        mock_cache.delete_many.assert_not_called()

    @patch("tenancy.api.cache")
    def test_bust_covers_all_declared_variants(self, mock_cache):
        """Every entry in _META_CACHE_LOCALE_VARIANTS is included in the eviction."""
        _bust_tenant_meta_cache("slug")
        evicted = mock_cache.delete_many.call_args.args[0]
        for variant in _META_CACHE_LOCALE_VARIANTS:
            self.assertIn(f"meta:v1:slug:{variant}", evicted)


# ── ProfileView cache invalidation tests ───────────────────────────────────────

class ProfileViewCacheInvalidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("tenancy.api._bust_tenant_meta_cache")
    @patch("tenancy.api.Profile.objects")
    def test_profile_update_busts_meta_cache(
        self, mock_profile_objects, mock_bust
    ):
        """PUT /api/profile/ must invalidate the tenant meta cache after save."""
        profile_instance = MagicMock()
        mock_profile_objects.get_or_create.return_value = (profile_instance, False)

        req = self.factory.patch("/api/profile/", {}, format="json")
        req.tenant = _make_tenant("demo")
        req.user = SimpleNamespace(is_authenticated=True, id=1)

        view = ProfileView()
        view.request = req
        view.kwargs = {}
        view.format_kwarg = None

        mock_serializer = MagicMock()
        mock_serializer.save.return_value = profile_instance

        view.perform_update(mock_serializer)

        mock_bust.assert_called_once_with("demo")

    @patch("tenancy.api._bust_tenant_meta_cache")
    def test_profile_update_bust_passes_correct_slug(self, mock_bust):
        """The slug forwarded to _bust_tenant_meta_cache matches request.tenant.slug."""
        req = self.factory.patch("/api/profile/", {}, format="json")
        req.tenant = _make_tenant("bistro-paris")
        req.user = SimpleNamespace(is_authenticated=True, id=1)

        view = ProfileView()
        view.request = req
        view.kwargs = {}
        view.format_kwarg = None

        with patch("tenancy.api.Profile.objects") as mock_profile_objects:
            mock_profile_objects.get_or_create.return_value = (MagicMock(), False)
            mock_serializer = MagicMock()
            view.perform_update(mock_serializer)

        mock_bust.assert_called_once_with("bistro-paris")
