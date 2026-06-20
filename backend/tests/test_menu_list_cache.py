"""
Tests for the server-side menu list cache in PublishAccessMixin.

Covers:
  - Cache miss on first request → DB called, response cached
  - Cache hit on second request → DB bypassed
  - Owner/staff requests always bypass the cache
  - Writes (create/update/destroy) bust the version counter
  - OptionGroupViewSet writes also bust the cache
  - _bust_menu_cache is a no-op for empty slug

All tests are SimpleTestCase (no database, no Redis).
The Django cache backend and DRF internals are mocked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import (
    CategoryViewSet,
    OptionGroupViewSet,
    _bust_menu_cache,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 1
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    # _can_preview_unpublished() accesses user.Roles.* via instance; wire it to
    # the real enum so the comparison `user.role in {user.Roles.TENANT_OWNER, …}`
    # works correctly instead of comparing against MagicMock objects.
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _tenant(slug="demo", tid=1):
    return SimpleNamespace(id=tid, slug=slug, is_active=True)


def _public_list_request(factory, tenant_slug="demo"):
    """Unauthenticated GET /api/categories/ attached to a tenant."""
    req = factory.get("/api/categories/")
    req.tenant = _tenant(slug=tenant_slug)
    req.user = _anon()
    return req


def _owner_list_request(factory, tenant_slug="demo"):
    """Authenticated owner GET /api/categories/."""
    owner = _owner()
    req = factory.get("/api/categories/")
    force_authenticate(req, user=owner)
    req.user = owner
    req.tenant = _tenant(slug=tenant_slug)
    return req


# ── _bust_menu_cache unit tests ───────────────────────────────────────────────

class BustMenuCacheTests(SimpleTestCase):
    """Unit tests for the _bust_menu_cache module-level function."""

    @patch("menu.views.cache")
    def test_increments_version_key(self, mock_cache):
        mock_cache.incr.return_value = 2
        _bust_menu_cache("myslug")
        mock_cache.incr.assert_called_once_with("menu_ver:myslug")

    @patch("menu.views.cache")
    def test_sets_version_to_2_when_key_missing(self, mock_cache):
        """When incr raises ValueError (key absent), fall back to set(…, 2)."""
        mock_cache.incr.side_effect = ValueError
        _bust_menu_cache("newslug")
        mock_cache.set.assert_called_once_with("menu_ver:newslug", 2, timeout=None)

    @patch("menu.views.cache")
    def test_empty_slug_is_noop(self, mock_cache):
        _bust_menu_cache("")
        mock_cache.incr.assert_not_called()
        mock_cache.set.assert_not_called()


# ── Cache-aside list() tests ──────────────────────────────────────────────────

_CAT_PATCHES = [
    "menu.views.cache",
    "menu.views.Category.objects",
    "menu.views.Profile.objects",
]


class CategoryViewSetListCacheTests(SimpleTestCase):
    """
    Test the cache-aside logic in PublishAccessMixin.list() as exercised
    through CategoryViewSet.

    R14b: the actual list-cache GET/SET/lock now live in the shared single-flight helper
    (tenancy.cache_utils.get_or_build_single_flight), while the version-counter lookup
    stays in menu.views.cache (via _menu_list_cache_key). So the list-cache assertions
    patch ``tenancy.cache_utils.cache`` and the version counter patches ``menu.views.cache``.
    The response contract (hit → no DB; miss → DB + store; per-params distinct keys) is
    unchanged.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    def _list_view(self):
        return CategoryViewSet.as_view({"get": "list"})

    # Helper: wire up the minimum mocks for a 200 list response.
    def _wire_mocks(self, mock_profile, mock_cat, mock_ver_cache, mock_sf_cache, *, cache_hit=None):
        # Profile: published menu
        profile = MagicMock()
        profile.is_menu_published = True
        profile.is_menu_temporarily_disabled = False
        mock_profile.filter.return_value.first.return_value = profile

        # Category queryset: empty list
        qs = MagicMock()
        qs.select_related.return_value = qs
        qs.prefetch_related.return_value = qs
        qs.filter.return_value = qs
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.__iter__ = lambda s: iter([])
        qs.count.return_value = 0
        mock_cat.select_related.return_value = qs

        # Version-counter cache (menu.views.cache): return a fixed version int.
        mock_ver_cache.get.return_value = 1
        # Single-flight list cache (tenancy.cache_utils.cache): the hit/miss value, and
        # cache.add returns True so the request wins the (uncontended) build lock.
        mock_sf_cache.get.return_value = cache_hit  # None → miss, value → hit
        mock_sf_cache.add.return_value = True

    @patch("tenancy.cache_utils.cache")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Category.objects")
    @patch("menu.views.cache")
    def test_cache_miss_calls_db_and_stores_result(
        self, mock_cache, mock_cat, mock_profile, mock_sf_cache
    ):
        """On a cache miss (single-flight cache.get returns None), DB is queried and the
        built payload is stored under the list-cache key."""
        self._wire_mocks(mock_profile, mock_cat, mock_cache, mock_sf_cache, cache_hit=None)

        req = _public_list_request(self.factory)
        resp = self._list_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Version counter looked up via menu.views.cache.
        self.assertTrue(mock_cache.get.call_args_list[0][0][0].startswith("menu_ver:"))
        # List-cache lookup + store happen via the single-flight helper's cache.
        key_used = mock_sf_cache.get.call_args_list[0][0][0]
        self.assertTrue(key_used.startswith("menu:demo:"))
        mock_sf_cache.set.assert_called()
        self.assertEqual(mock_sf_cache.set.call_args[0][0], key_used)

    @patch("tenancy.cache_utils.cache")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Category.objects")
    @patch("menu.views.cache")
    def test_cache_hit_returns_cached_data_without_db(
        self, mock_cache, mock_cat, mock_profile, mock_sf_cache
    ):
        """On a cache hit, the cached list is returned and DB is NOT queried."""
        cached_data = [{"id": 1, "name": "Starters"}]
        self._wire_mocks(mock_profile, mock_cat, mock_cache, mock_sf_cache, cache_hit=cached_data)

        req = _public_list_request(self.factory)
        resp = self._list_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, cached_data)
        # DB was not touched
        mock_cat.select_related.assert_not_called()
        # No re-store on a hit (single-flight returns early before any set).
        mock_sf_cache.set.assert_not_called()

    @patch("tenancy.cache_utils.cache")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Category.objects")
    @patch("menu.views.cache")
    def test_owner_request_bypasses_cache(
        self, mock_cache, mock_cat, mock_profile, mock_sf_cache
    ):
        """Authenticated owner requests never touch the cache."""
        self._wire_mocks(mock_profile, mock_cat, mock_cache, mock_sf_cache, cache_hit=None)

        req = _owner_list_request(self.factory)
        resp = self._list_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # key is None for owner → neither the version counter nor the list cache is read.
        mock_cache.get.assert_not_called()
        mock_sf_cache.get.assert_not_called()
        mock_sf_cache.set.assert_not_called()

    @patch("tenancy.cache_utils.cache")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Category.objects")
    @patch("menu.views.cache")
    def test_different_query_params_produce_different_keys(
        self, mock_cache, mock_cat, mock_profile, mock_sf_cache
    ):
        """Requests with different ?super_category params must use distinct cache keys."""
        self._wire_mocks(mock_profile, mock_cat, mock_cache, mock_sf_cache, cache_hit=None)
        view = self._list_view()

        req_a = self.factory.get("/api/categories/", {"super_category": "burgers"})
        req_a.tenant = _tenant()
        req_a.user = _anon()
        view(req_a)
        key_a = mock_sf_cache.get.call_args_list[0][0][0]

        mock_sf_cache.reset_mock()
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True

        req_b = self.factory.get("/api/categories/", {"super_category": "salads"})
        req_b.tenant = _tenant()
        req_b.user = _anon()
        view(req_b)
        key_b = mock_sf_cache.get.call_args_list[0][0][0]

        self.assertNotEqual(key_a, key_b)


# ── Cache bust on write ───────────────────────────────────────────────────────

class CategoryViewSetCacheBustTests(SimpleTestCase):
    """Writes through CategoryViewSet must invalidate the version counter."""

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("menu.views._bust_menu_cache")
    @patch("menu.views.Category.objects")
    def test_perform_create_busts_cache(self, mock_cat, mock_bust):
        """A successful create triggers _bust_menu_cache with the tenant slug."""
        view = CategoryViewSet()
        view.request = MagicMock()
        view.request.tenant = _tenant(slug="myrestaurant")
        # Simulate perform_create calling super() and then bust
        serializer = MagicMock()
        with patch.object(type(view).__mro__[2], "perform_create"):
            view.perform_create(serializer)
        mock_bust.assert_called_once_with("myrestaurant")

    @patch("menu.views._bust_menu_cache")
    @patch("menu.views.Category.objects")
    def test_perform_update_busts_cache(self, mock_cat, mock_bust):
        view = CategoryViewSet()
        view.request = MagicMock()
        view.request.tenant = _tenant(slug="myrestaurant")
        serializer = MagicMock()
        with patch.object(type(view).__mro__[2], "perform_update"):
            view.perform_update(serializer)
        mock_bust.assert_called_once_with("myrestaurant")

    @patch("menu.views._bust_menu_cache")
    @patch("menu.views.Category.objects")
    def test_perform_destroy_busts_cache(self, mock_cat, mock_bust):
        view = CategoryViewSet()
        view.request = MagicMock()
        view.request.tenant = _tenant(slug="myrestaurant")
        instance = MagicMock()
        with patch.object(type(view).__mro__[2], "perform_destroy"):
            view.perform_destroy(instance)
        mock_bust.assert_called_once_with("myrestaurant")


# ── OptionGroupViewSet bust ───────────────────────────────────────────────────

class OptionGroupViewSetCacheBustTests(SimpleTestCase):
    """OptionGroupViewSet writes must also bust the menu cache."""

    @patch("menu.views._bust_menu_cache")
    def test_perform_create_busts_cache(self, mock_bust):
        view = OptionGroupViewSet()
        view.request = MagicMock()
        view.request.tenant = _tenant(slug="bistro")
        serializer = MagicMock()
        with patch.object(type(view).__mro__[1], "perform_create"):
            view.perform_create(serializer)
        mock_bust.assert_called_once_with("bistro")

    @patch("menu.views._bust_menu_cache")
    def test_perform_destroy_busts_cache(self, mock_bust):
        view = OptionGroupViewSet()
        view.request = MagicMock()
        view.request.tenant = _tenant(slug="bistro")
        instance = MagicMock()
        with patch.object(type(view).__mro__[1], "perform_destroy"):
            view.perform_destroy(instance)
        mock_bust.assert_called_once_with("bistro")
