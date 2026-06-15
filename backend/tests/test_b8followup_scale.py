"""
B8-followup (scale) — bust the public list cache on rating change + min_rating index.

Two contracts:

  Public list cache versioning (accounts.views)
    - _public_list_cache_key embeds the CURRENT global version and changes when the
      version is bumped (so a stale entry can never be hit again).
    - _bust_public_list_cache increments the global version counter, seeding it to 2
      on the key-missing (ValueError) path — mirrors menu/views._bust_menu_cache.

  recompute_tenant_rating (menu.ratings)
    - busts the public list cache AFTER updating the public Profile, so the
      directory/marketplace listing refreshes immediately instead of waiting out the
      90s list-cache TTL.

  Profile index (tenancy.models)
    - the composite (directory_opt_in, is_menu_published, rating_avg) index backing
      the B8 min_rating SQL filter is present in Meta.indexes.

House style: SimpleTestCase + MagicMock, no real DB or schema switch.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from urllib.parse import urlencode

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from accounts.views import (
    _PUBLIC_LIST_VER_KEY,
    _bust_public_list_cache,
    _public_list_cache_key,
)


def _req(params=None):
    """A minimal request stub exposing the DRF .query_params.urlencode() the cache
    key helper relies on (a bare WSGIRequest has no .query_params)."""
    req = MagicMock()
    req.query_params.urlencode.return_value = urlencode(params or {})
    return req


def _tenant(schema_name="bistro", tid=1):
    t = MagicMock()
    t.id = tid
    t.schema_name = schema_name
    t.name = "Bistro"
    t.slug = "bistro"
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# _public_list_cache_key — version-embedded key
# ═══════════════════════════════════════════════════════════════════════════════

@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PublicListCacheKeyTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _key(self, params=None):
        return _public_list_cache_key("marketplace", _req(params))

    def test_key_defaults_to_v1_when_unset(self):
        """No version in cache → key uses v1 (cache.get(...) or 1)."""
        key = self._key()
        self.assertIn(":v1:", key)

    def test_key_embeds_current_version(self):
        """Setting the version counter is reflected in the key."""
        cache.set(_PUBLIC_LIST_VER_KEY, 5, timeout=None)
        key = self._key()
        self.assertIn(":v5:", key)

    def test_key_changes_when_version_bumped(self):
        """A version bump produces a different key for the SAME params (busting old)."""
        before = self._key({"city": "Paris"})
        _bust_public_list_cache()
        after = self._key({"city": "Paris"})
        self.assertNotEqual(before, after)
        # Same param hash, different version segment.
        self.assertEqual(before.rsplit(":", 1)[-1], after.rsplit(":", 1)[-1])

    def test_same_params_same_version_stable(self):
        """Identical params at the same version yield an identical key."""
        self.assertEqual(self._key({"q": "pizza"}), self._key({"q": "pizza"}))


# ═══════════════════════════════════════════════════════════════════════════════
# _bust_public_list_cache — increment / seed-to-2
# ═══════════════════════════════════════════════════════════════════════════════

@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class BustPublicListCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_seeds_to_2_when_key_missing(self):
        """First bust (no key yet) seeds the counter to 2 (the ValueError path)."""
        self.assertIsNone(cache.get(_PUBLIC_LIST_VER_KEY))
        _bust_public_list_cache()
        self.assertEqual(cache.get(_PUBLIC_LIST_VER_KEY), 2)

    def test_increments_existing_version(self):
        """A subsequent bust increments the existing counter."""
        cache.set(_PUBLIC_LIST_VER_KEY, 4, timeout=None)
        _bust_public_list_cache()
        self.assertEqual(cache.get(_PUBLIC_LIST_VER_KEY), 5)

    def test_seed_uses_no_timeout(self):
        """The seeded counter is persistent (timeout=None) so it isn't silently lost."""
        with patch("accounts.views.cache") as mock_cache:
            mock_cache.incr.side_effect = ValueError("missing")
            _bust_public_list_cache()
        mock_cache.set.assert_called_once_with(_PUBLIC_LIST_VER_KEY, 2, timeout=None)


# ═══════════════════════════════════════════════════════════════════════════════
# recompute_tenant_rating — busts the public list cache after the Profile update
# ═══════════════════════════════════════════════════════════════════════════════

class RecomputeBustsListCacheTests(SimpleTestCase):
    """recompute_tenant_rating must bust the public list cache after writing Profile."""

    def _run(self, agg, schema_name="bistro"):
        from menu import ratings as ratings_mod

        tenant = _tenant(schema_name=schema_name)

        mock_rating = MagicMock()
        mock_rating.objects.aggregate.return_value = agg
        mock_profile = MagicMock()

        @contextmanager
        def _sc(*a, **k):
            yield

        fake_menu_models = MagicMock()
        fake_menu_models.Rating = mock_rating

        import sys
        original = sys.modules.get("menu.models")
        sys.modules["menu.models"] = fake_menu_models
        try:
            with patch("django_tenants.utils.schema_context", _sc), \
                    patch("tenancy.models.Profile", mock_profile), \
                    patch("accounts.views._bust_public_list_cache") as mock_bust:
                ratings_mod.recompute_tenant_rating(tenant)
        finally:
            if original is None:
                sys.modules.pop("menu.models", None)
            else:
                sys.modules["menu.models"] = original
        return mock_profile, mock_bust

    def test_busts_after_profile_update(self):
        """A recompute that updates the Profile then busts the public list cache once."""
        mock_profile, mock_bust = self._run({"avg": 4.2, "cnt": 5})
        mock_profile.objects.filter.return_value.update.assert_called_once()
        mock_bust.assert_called_once_with()

    def test_busts_even_when_no_ratings(self):
        """The listing changes (rating cleared) on the last-delete edge too → still busts."""
        _, mock_bust = self._run({"avg": None, "cnt": 0})
        mock_bust.assert_called_once_with()

    def test_no_bust_on_public_schema(self):
        """The public-schema short-circuit never reaches the Profile update or the bust."""
        from menu import ratings as ratings_mod
        from django_tenants.utils import get_public_schema_name

        tenant = _tenant(schema_name=get_public_schema_name())
        with patch("accounts.views._bust_public_list_cache") as mock_bust, \
                patch("tenancy.models.Profile") as mock_profile:
            ratings_mod.recompute_tenant_rating(tenant)
        mock_profile.objects.filter.assert_not_called()
        mock_bust.assert_not_called()

    def test_bust_failure_does_not_propagate(self):
        """A bust that raises must be swallowed (recompute stays best-effort)."""
        from menu import ratings as ratings_mod

        tenant = _tenant()
        mock_rating = MagicMock()
        mock_rating.objects.aggregate.return_value = {"avg": 4.0, "cnt": 1}

        @contextmanager
        def _sc(*a, **k):
            yield

        fake_menu_models = MagicMock()
        fake_menu_models.Rating = mock_rating

        import sys
        original = sys.modules.get("menu.models")
        sys.modules["menu.models"] = fake_menu_models
        try:
            with patch("django_tenants.utils.schema_context", _sc), \
                    patch("tenancy.models.Profile"), \
                    patch("accounts.views._bust_public_list_cache",
                          side_effect=RuntimeError("cache down")):
                # Must not raise.
                ratings_mod.recompute_tenant_rating(tenant)
        finally:
            if original is None:
                sys.modules.pop("menu.models", None)
            else:
                sys.modules["menu.models"] = original


# ═══════════════════════════════════════════════════════════════════════════════
# Profile index — min_rating SQL filter backing index
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileRatingIndexTests(SimpleTestCase):
    def test_composite_rating_index_present(self):
        """A composite index on (directory_opt_in, is_menu_published, rating_avg) exists."""
        from tenancy.models import Profile

        target = ["directory_opt_in", "is_menu_published", "rating_avg"]
        matches = [ix for ix in Profile._meta.indexes if list(ix.fields) == target]
        self.assertEqual(
            len(matches), 1,
            "expected exactly one composite index backing the min_rating SQL filter",
        )
        self.assertEqual(matches[0].name, "profile_marketplace_rate_idx")
