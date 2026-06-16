"""
Tests for the Redis-backed server-side cache on TenantMetaView and the
invalidation logic in ProfileView.perform_update().

All tests are SimpleTestCase (no database).  The Django cache and DRF
serializer are both mocked so the suite never touches Redis or Postgres.

R14c NOTE: the actual cache GET/SET/lock operations now live in the shared
single-flight helper (tenancy.cache_utils.get_or_build_single_flight), so
cache-hit/miss assertions patch ``tenancy.cache_utils.cache`` (the module-
level cache reference used by the helper).  _bust_tenant_meta_cache still
calls ``cache.delete_many`` via its own module-level import (tenancy.api.cache),
so bust tests continue to patch ``tenancy.api.cache``.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from tenancy.api import (
    LISTING_RELEVANT_FIELDS,
    ProfileView,
    TenantMetaView,
    _META_CACHE_LOCALE_VARIANTS,
    _META_ISOPEN_RAW_KEY,
    _bust_tenant_meta_cache,
    _meta_cache_key,
    _refresh_meta_is_open_now,
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
# R14c: single-flight GET/SET/lock live in tenancy.cache_utils, so we patch
# ``tenancy.cache_utils.cache`` to control cache hits/misses.  On a miss we
# also stub ``cache.add`` to return True (the winner acquires the build lock
# uncontested in these single-request unit tests).

class TenantMetaCacheHitTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_returns_cached_data_without_calling_serializer(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """A warm cache returns the stored dict directly; serializer is never called."""
        mock_sf_cache.get.return_value = _fake_meta_data()

        req = _anon_request(self.factory)
        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "demo")
        mock_serializer_cls.from_tenant.assert_not_called()

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_does_not_call_cache_set(self, mock_serializer_cls, mock_sf_cache):
        """On a cache hit we must not write back to the cache (no double-set)."""
        mock_sf_cache.get.return_value = _fake_meta_data()

        req = _anon_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_sf_cache.set.assert_not_called()

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_uses_correct_key_for_lang_param(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Cache lookup uses the ?lang= query param in the key."""
        mock_sf_cache.get.return_value = _fake_meta_data()

        req = self.factory.get("/api/meta/?lang=ar")
        req.tenant = _make_tenant()
        TenantMetaView.as_view()(req)

        mock_sf_cache.get.assert_called_once_with("meta:v1:demo:ar")

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_uses_auth_key_for_authenticated_users(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Authenticated owner requests are keyed with '_auth' locale scope."""
        mock_sf_cache.get.return_value = _fake_meta_data()

        req = _auth_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_sf_cache.get.assert_called_once_with("meta:v1:demo:_auth")


# ── TenantMetaView cache-miss tests ────────────────────────────────────────────
# R14c: patch ``tenancy.cache_utils.cache`` (single-flight helper's cache).
# On a miss, also stub ``cache.add`` to return True so this request wins the
# (uncontested) build lock.  cache.set is called positionally by the helper:
# cache.set(key, value, ttl) — no ``timeout=`` keyword.

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

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_calls_serializer(self, mock_serializer_cls, mock_sf_cache):
        """On a miss the serializer is called once with the correct tenant."""
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True  # wins the build lock
        self._mock_serializer(mock_serializer_cls)

        req = _anon_request(self.factory)
        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_serializer_cls.from_tenant.assert_called_once()
        call_kwargs = mock_serializer_cls.from_tenant.call_args
        self.assertEqual(call_kwargs.args[0].slug, "demo")

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_stores_result_with_ttl(self, mock_serializer_cls, mock_sf_cache):
        """After a miss, the computed result is written to cache with the correct TTL."""
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True  # wins the build lock
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = _anon_request(self.factory)
        TenantMetaView.as_view()(req)

        # Single-flight calls cache.set(key, value, ttl) positionally (no timeout= kwarg).
        mock_sf_cache.set.assert_called_once_with("meta:v1:demo:", fake_data, 300)

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_with_lang_param_uses_lang_in_key(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Cache set uses the same key that was looked up — including ?lang=."""
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True  # wins the build lock
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = self.factory.get("/api/meta/?lang=fr")
        req.tenant = _make_tenant()
        TenantMetaView.as_view()(req)

        mock_sf_cache.set.assert_called_once_with("meta:v1:demo:fr", fake_data, 300)

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_miss_authenticated_uses_auth_key(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Authenticated miss stores under the '_auth' key."""
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True  # wins the build lock
        fake_data = self._mock_serializer(mock_serializer_cls)

        req = _auth_request(self.factory)
        TenantMetaView.as_view()(req)

        mock_sf_cache.set.assert_called_once_with("meta:v1:demo:_auth", fake_data, 300)

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_no_tenant_returns_400_without_touching_cache(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Missing tenant → 400 response; cache must not be read or written."""
        req = self.factory.get("/api/meta/")
        # req.tenant is deliberately not set

        response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_sf_cache.get.assert_not_called()
        mock_sf_cache.set.assert_not_called()


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


# ── CHANGE 1: ProfileView busts the PUBLIC LIST cache on listing-relevant edits ──

def _run_profile_update(validated_data):
    """Drive ProfileView.perform_update with a serializer whose validated_data is the
    given dict, returning the patched accounts.views._bust_public_list_cache mock."""
    factory = APIRequestFactory()
    req = factory.patch("/api/profile/", {}, format="json")
    req.tenant = _make_tenant("demo")
    req.user = SimpleNamespace(is_authenticated=True, id=1)

    view = ProfileView()
    view.request = req
    view.kwargs = {}
    view.format_kwarg = None

    serializer = MagicMock()
    serializer.validated_data = validated_data

    with patch("tenancy.api.Profile.objects") as mock_profile_objects, \
            patch("tenancy.api._bust_tenant_meta_cache"), \
            patch("accounts.views._bust_public_list_cache") as mock_list_bust:
        mock_profile_objects.get_or_create.return_value = (MagicMock(), False)
        view.perform_update(serializer)
    return mock_list_bust


class ProfileViewPublicListBustTests(SimpleTestCase):
    """A Profile save that touches a listing field must bust the public list cache;
    a save touching only unrelated config must NOT (it would needlessly invalidate
    every restaurant's listing)."""

    def test_listing_field_edit_busts_public_list_cache(self):
        """directory_opt_in is a listing field → the public list cache is busted once."""
        mock_list_bust = _run_profile_update({"directory_opt_in": False})
        mock_list_bust.assert_called_once_with()

    def test_other_listing_field_edit_busts(self):
        """A city change (filter + facet + serialized) also busts."""
        mock_list_bust = _run_profile_update({"city": "Marrakech", "cuisine_type": "Moroccan"})
        mock_list_bust.assert_called_once_with()

    def test_non_listing_field_edit_does_not_bust(self):
        """A notification-only save must leave the public listing cache untouched."""
        mock_list_bust = _run_profile_update({"sms_notifications_enabled": True})
        mock_list_bust.assert_not_called()

    def test_mixed_edit_busts_once(self):
        """A save mixing a listing field with unrelated config still busts (exactly once)."""
        mock_list_bust = _run_profile_update(
            {"price_tier": 3, "sms_notifications_enabled": True}
        )
        mock_list_bust.assert_called_once_with()

    def test_empty_validated_data_does_not_bust(self):
        mock_list_bust = _run_profile_update({})
        mock_list_bust.assert_not_called()

    def test_bust_failure_is_swallowed(self):
        """A list-cache bust that raises must not break the profile save (best-effort)."""
        factory = APIRequestFactory()
        req = factory.patch("/api/profile/", {}, format="json")
        req.tenant = _make_tenant("demo")
        req.user = SimpleNamespace(is_authenticated=True, id=1)

        view = ProfileView()
        view.request = req
        view.kwargs = {}
        view.format_kwarg = None

        serializer = MagicMock()
        serializer.validated_data = {"is_open": False}

        with patch("tenancy.api.Profile.objects") as mock_profile_objects, \
                patch("tenancy.api._bust_tenant_meta_cache"), \
                patch("accounts.views._bust_public_list_cache",
                      side_effect=RuntimeError("cache down")):
            mock_profile_objects.get_or_create.return_value = (MagicMock(), False)
            # Must not raise.
            view.perform_update(serializer)

    @override_settings(CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_listing_edit_bumps_real_version_counter(self):
        """End-to-end: a listing-field save increments the REAL _PUBLIC_LIST_VER_KEY,
        orphaning every cached directory/marketplace entry; an unrelated save does not."""
        from accounts.views import _PUBLIC_LIST_VER_KEY

        factory = APIRequestFactory()

        def _do_update(validated):
            req = factory.patch("/api/profile/", {}, format="json")
            req.tenant = _make_tenant("demo")
            req.user = SimpleNamespace(is_authenticated=True, id=1)
            view = ProfileView()
            view.request = req
            view.kwargs = {}
            view.format_kwarg = None
            serializer = MagicMock()
            serializer.validated_data = validated
            with patch("tenancy.api.Profile.objects") as mpo, \
                    patch("tenancy.api._bust_tenant_meta_cache"):
                mpo.get_or_create.return_value = (MagicMock(), False)
                view.perform_update(serializer)

        cache.clear()
        cache.set(_PUBLIC_LIST_VER_KEY, 4, timeout=None)

        # Unrelated save: version unchanged.
        _do_update({"sms_notifications_enabled": True})
        self.assertEqual(cache.get(_PUBLIC_LIST_VER_KEY), 4)

        # Listing save: version bumped.
        _do_update({"directory_opt_in": False})
        self.assertEqual(cache.get(_PUBLIC_LIST_VER_KEY), 5)


class ListingRelevantFieldsContractTests(SimpleTestCase):
    """The derived field set must cover the documented listing dependencies and must
    NOT include fields with their own denorm bust paths / unrelated config."""

    def test_includes_documented_listing_fields(self):
        for f in (
            "directory_opt_in", "is_menu_published", "is_open",
            "is_menu_temporarily_disabled", "business_hours_schedule", "city",
            "cuisine_type", "delivery_enabled", "price_tier", "tags",
            "business_type", "logo_url", "tagline",
        ):
            self.assertIn(f, LISTING_RELEVANT_FIELDS)

    def test_excludes_denorm_and_unrelated_fields(self):
        for f in ("rating_avg", "rating_count", "marketplace_promos",
                  "sms_notifications_enabled", "winback_enabled",
                  "marketplace_commission_pct"):
            self.assertNotIn(f, LISTING_RELEVANT_FIELDS)


# ══════════════════════════════════════════════════════════════════════════════
# Live is_open_now recompute on the cached meta payload (freshness fix)
# ══════════════════════════════════════════════════════════════════════════════

import datetime as dt_module  # noqa: E402
from datetime import timezone as dt_timezone  # noqa: E402

from tenancy.serializers import ProfileSerializer  # noqa: E402


def _tz_aware_mock_dt(fixed_utc):
    """datetime stand-in whose .now(tz) converts a FIXED UTC instant into the asked
    tz — mirrors the helper in test_profile_is_open_now so the recompute reads the
    tenant wall-clock at a controllable instant. The recompute does
    `from datetime import datetime as _dt; _dt.now(ZoneInfo(tz))`, which re-resolves
    datetime.datetime at call time, so patching `datetime.datetime` is picked up."""
    class _M(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)
    return _M


def _meta_payload_with_raw(*, is_open=True, menu_disabled=False, schedule=None,
                           timezone="UTC", closure_today=False, baked_is_open_now=None):
    """A cached meta payload carrying _isopen_raw, with profile.is_open_now baked in.

    baked_is_open_now defaults to is_open so a freshly-built payload looks consistent;
    a test can set it to a STALE value to prove the recompute overrides the baked one.
    """
    if baked_is_open_now is None:
        baked_is_open_now = is_open
    return {
        "name": "Demo Restaurant",
        "slug": "demo",
        "plan": {},
        "profile": {"is_open_now": baked_is_open_now, "name": "Demo"},
        _META_ISOPEN_RAW_KEY: {
            "is_open": is_open,
            "menu_disabled": menu_disabled,
            "schedule": schedule,
            "timezone": timezone,
            "closure_today": closure_today,
        },
    }


def _profile_for_serializer(*, is_open=True, schedule=None, timezone="UTC",
                            is_menu_temporarily_disabled=False):
    return SimpleNamespace(
        is_open=is_open,
        business_hours_schedule=schedule,
        timezone=timezone,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
    )


# 2024-06-03 is a Monday. Schedule open 09:00–22:00 in tenant-local time.
_MON_SCHEDULE = {"mon": {"enabled": True, "open": "09:00", "close": "22:00"}}
_MON_OPEN_INSTANT = dt_module.datetime(2024, 6, 3, 12, 0, 0, tzinfo=dt_timezone.utc)   # inside window
_MON_CLOSED_INSTANT = dt_module.datetime(2024, 6, 3, 23, 0, 0, tzinfo=dt_timezone.utc)  # past close


class MetaIsOpenNowRecomputeTests(SimpleTestCase):
    """profile.is_open_now is recomputed from _isopen_raw + the current time on every
    /api/meta/ read, so a cached payload never freezes the open/closed verdict."""

    def test_recompute_flips_at_later_clock_cached_object_unchanged(self):
        """(a) The SAME cached payload yields open at one instant and closed at a later
        instant; the cached object itself is never mutated (deepcopy isolation)."""
        payload = _meta_payload_with_raw(schedule=_MON_SCHEDULE, timezone="UTC")
        snapshot = copy_deep(payload)

        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_OPEN_INSTANT)):
            open_copy = _refresh_meta_is_open_now(payload)
        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_CLOSED_INSTANT)):
            closed_copy = _refresh_meta_is_open_now(payload)

        self.assertTrue(open_copy["profile"]["is_open_now"])
        self.assertFalse(closed_copy["profile"]["is_open_now"])
        # The cached object is byte-for-byte unchanged (raw inputs intact for next hit).
        self.assertEqual(payload, snapshot)
        self.assertIn(_META_ISOPEN_RAW_KEY, payload)

    def test_recompute_overrides_stale_baked_verdict(self):
        """A payload baked OPEN but evaluated past close now reports closed."""
        payload = _meta_payload_with_raw(
            schedule=_MON_SCHEDULE, timezone="UTC", baked_is_open_now=True
        )
        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_CLOSED_INSTANT)):
            out = _refresh_meta_is_open_now(payload)
        self.assertFalse(out["profile"]["is_open_now"])

    def test_recompute_equals_serializer_at_same_instant(self):
        """(b) At any instant the recompute equals ProfileSerializer.get_is_open_now for
        the equivalent inputs — proving the SAME single-source rule, not a fork."""
        ser = ProfileSerializer.__new__(ProfileSerializer)

        def _no_closure():
            qset = MagicMock()
            qset.exists.return_value = False
            cls = MagicMock()
            cls.objects.filter.return_value = qset
            return cls

        for instant in (_MON_OPEN_INSTANT, _MON_CLOSED_INSTANT):
            payload = _meta_payload_with_raw(schedule=_MON_SCHEDULE, timezone="UTC")
            prof = _profile_for_serializer(is_open=True, schedule=_MON_SCHEDULE, timezone="UTC")
            with patch("datetime.datetime", _tz_aware_mock_dt(instant)):
                recomputed = _refresh_meta_is_open_now(payload)["profile"]["is_open_now"]
                with patch("menu.models.ClosureDate", _no_closure()):
                    serializer_value = ser.get_is_open_now(prof)
            self.assertEqual(recomputed, serializer_value,
                             f"mismatch at {instant}: recompute={recomputed} serializer={serializer_value}")

    def test_closure_today_forces_closed_in_recompute(self):
        """The cached closure_today bool short-circuits to closed (day-stable guard)."""
        payload = _meta_payload_with_raw(
            schedule=_MON_SCHEDULE, timezone="UTC", closure_today=True
        )
        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_OPEN_INSTANT)):
            out = _refresh_meta_is_open_now(payload)
        self.assertFalse(out["profile"]["is_open_now"])

    def test_manual_closed_and_menu_disabled_force_closed(self):
        """Guard order mirrors get_is_open_now: manual off → closed; temp-disable → closed."""
        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_OPEN_INSTANT)):
            manual_off = _refresh_meta_is_open_now(
                _meta_payload_with_raw(is_open=False, schedule=_MON_SCHEDULE))
            disabled = _refresh_meta_is_open_now(
                _meta_payload_with_raw(menu_disabled=True, schedule=_MON_SCHEDULE))
        self.assertFalse(manual_off["profile"]["is_open_now"])
        self.assertFalse(disabled["profile"]["is_open_now"])

    def test_isopen_raw_stripped_from_recomputed_copy(self):
        """(d) The internal _isopen_raw key never appears in the returned (response) copy."""
        payload = _meta_payload_with_raw(schedule=_MON_SCHEDULE)
        with patch("datetime.datetime", _tz_aware_mock_dt(_MON_OPEN_INSTANT)):
            out = _refresh_meta_is_open_now(payload)
        self.assertNotIn(_META_ISOPEN_RAW_KEY, out)

    def test_payload_without_raw_is_noop_safe(self):
        """A payload with profile=None and no _isopen_raw (e.g. mocked tests) is returned
        as a clean copy without error."""
        payload = {"name": "X", "slug": "demo", "plan": {}, "profile": None}
        out = _refresh_meta_is_open_now(payload)
        self.assertEqual(out, payload)
        self.assertIsNot(out, payload)


def copy_deep(obj):
    import copy
    return copy.deepcopy(obj)


class MetaViewLiveRecomputeIntegrationTests(SimpleTestCase):
    """End-to-end through TenantMetaView: both return paths recompute is_open_now and
    never leak _isopen_raw; the cache-hit path does NO DB query for the recompute.

    R14c: patch ``tenancy.cache_utils.cache`` (single-flight helper's cache).
    On a miss, stub ``cache.add`` to return True (wins build lock uncontested).
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_recompute_does_no_db_and_no_leak(self, mock_serializer_cls, mock_sf_cache):
        """(c)+(d) On a warm cache the view recomputes is_open_now WITHOUT a DB query and
        without leaking _isopen_raw. We assert no ClosureDate query is issued on the hit
        path (closure_today is cached) and the serializer is never invoked."""
        mock_sf_cache.get.return_value = _meta_payload_with_raw(
            schedule=_MON_SCHEDULE, timezone="UTC", closure_today=False)

        req = _anon_request(self.factory)
        with patch("menu.models.ClosureDate") as mock_closure, \
                patch("datetime.datetime", _tz_aware_mock_dt(_MON_CLOSED_INSTANT)):
            response = TenantMetaView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No DB query for the recompute on the cache-hit path.
        mock_closure.objects.filter.assert_not_called()
        # Serializer (the expensive build) is not invoked on a hit.
        mock_serializer_cls.from_tenant.assert_not_called()
        # Recomputed live: past close → closed.
        self.assertFalse(response.data["profile"]["is_open_now"])
        # Internal key never leaks to the client.
        self.assertNotIn(_META_ISOPEN_RAW_KEY, response.data)

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_cache_hit_recomputes_open_at_open_instant(self, mock_serializer_cls, mock_sf_cache):
        """Same warm payload, an in-window instant → open (proves it is live, not baked)."""
        mock_sf_cache.get.return_value = _meta_payload_with_raw(
            schedule=_MON_SCHEDULE, timezone="UTC", baked_is_open_now=False)

        req = _anon_request(self.factory)
        with patch("menu.models.ClosureDate"), \
                patch("datetime.datetime", _tz_aware_mock_dt(_MON_OPEN_INSTANT)):
            response = TenantMetaView.as_view()(req)

        self.assertTrue(response.data["profile"]["is_open_now"])

    @patch("tenancy.cache_utils.cache")
    @patch("tenancy.api.TenantMetaSerializer")
    def test_fresh_build_attaches_raw_caches_with_it_and_strips_from_response(
        self, mock_serializer_cls, mock_sf_cache
    ):
        """Cache miss: the view attaches _isopen_raw from the profile, caches the payload
        WITH it, computes closure_today ONCE, and returns a stripped recomputed copy."""
        mock_sf_cache.get.return_value = None
        mock_sf_cache.add.return_value = True  # wins the build lock
        fresh = {"name": "Demo", "slug": "demo", "plan": {},
                 "profile": {"is_open_now": True, "name": "Demo"}}
        instance = MagicMock()
        instance.data = fresh
        mock_serializer_cls.from_tenant.return_value = instance

        # Tenant WITH a profile model so _isopen_raw is attached.
        tenant = SimpleNamespace(
            id=1, name="Demo", slug="demo",
            profile=SimpleNamespace(
                is_open=True, is_menu_temporarily_disabled=False,
                business_hours_schedule=_MON_SCHEDULE, timezone="UTC"),
        )
        req = self.factory.get("/api/meta/")
        req.tenant = tenant

        def _no_closure():
            qset = MagicMock()
            qset.exists.return_value = False
            cls = MagicMock()
            cls.objects.filter.return_value = qset
            return cls

        with patch("menu.models.ClosureDate", _no_closure()), \
                patch("django.utils.timezone.localdate",
                      return_value=dt_module.date(2024, 6, 3)), \
                patch("datetime.datetime", _tz_aware_mock_dt(_MON_CLOSED_INSTANT)):
            response = TenantMetaView.as_view()(req)

        # The CACHED object carries _isopen_raw (so later hits can recompute).
        # Single-flight calls cache.set(key, value, ttl) positionally.
        cached_arg = mock_sf_cache.set.call_args.args[1]
        self.assertIn(_META_ISOPEN_RAW_KEY, cached_arg)
        self.assertEqual(cached_arg[_META_ISOPEN_RAW_KEY]["timezone"], "UTC")
        self.assertIs(cached_arg[_META_ISOPEN_RAW_KEY]["schedule"], _MON_SCHEDULE)
        # The HTTP RESPONSE is the stripped, recomputed copy (past close → closed).
        self.assertNotIn(_META_ISOPEN_RAW_KEY, response.data)
        self.assertFalse(response.data["profile"]["is_open_now"])
