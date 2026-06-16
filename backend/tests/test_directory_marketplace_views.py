"""
Tests for marketplace / directory public views:
  - DirectoryView              GET /api/directory/
  - MarketplaceView            GET /api/marketplace/
  - MarketplaceMenuView        GET /api/marketplace/menu/<slug>/
  - MarketplacePlaceOrderView  POST /api/marketplace/order/
  - MarketplaceOrderStatusView GET /api/marketplace/order/<order_number>/

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema switch).
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    DirectoryView,
    MarketplaceView,
    MarketplaceMenuView,
    MarketplacePlaceOrderView,
    MarketplaceOrderStatusView,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

# Reusable fake DoesNotExist — keeps the except clause working correctly
class _FakeDNE(Exception):
    pass


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _make_profile(**kwargs):
    p = MagicMock()
    p.directory_opt_in = True
    p.is_menu_published = True
    p.is_open = True
    p.is_menu_temporarily_disabled = False
    # Time-sensitive raw inputs carried into the cached payload (must be real, picklable
    # values — the list-cache pickles the payload). Default: no schedule configured (so
    # is_open falls back to the manual toggle), UTC tz, no promos.
    p.timezone = "UTC"
    p.business_hours_schedule = {}
    p.marketplace_promos = []
    p.tagline = "Great food"
    p.logo_url = "https://example.com/logo.png"
    p.cuisine_type = "Italian"
    p.business_type = "restaurant"
    p.city = "Paris"
    p.delivery_enabled = True
    p.lat = 48.8566
    p.lng = 2.3522
    p.delivery_fee = "2.00"
    p.delivery_minimum_order = "15.00"
    p.price_tier = 2
    p.tags = ["halal"]
    p.address = "1 Rue de la Paix"
    p.phone = "+33123456789"
    p.currency = "EUR"
    # B8: ratings are denormalized onto the public Profile (read directly by the
    # directory/marketplace views — no per-tenant schema switch). Default unrated.
    p.rating_avg = None
    p.rating_count = 0
    tenant = MagicMock()
    tenant.slug = "bistro"
    tenant.name = "Bistro Paris"
    tenant.schema_name = "bistro"
    p.tenant = tenant
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def _sc_mock():
    """Context manager that does nothing."""
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


# ── DirectoryView ─────────────────────────────────────────────────────────────

def _make_sliceable_qs(rows):
    """Return a MagicMock queryset whose __getitem__ yields *rows* when sliced."""
    qs = MagicMock()
    # list() calls __iter__ (via __getitem__ with a slice); MagicMock's default
    # __iter__ raises TypeError, so we override __getitem__ to return the list
    # regardless of the key/slice used (the view always slices with [:N]).
    qs.__getitem__ = lambda s, k: rows
    return qs


class DirectoryViewTests(SimpleTestCase):
    def setUp(self):
        cache.clear()  # responses are cached by query params — isolate each test
        self.factory = APIRequestFactory()
        self.view = DirectoryView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/directory/", params or {})
        req.user = _anon()
        return self.view(req)

    def test_returns_200_with_empty_qs(self):
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([])
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("restaurants", resp.data)
        self.assertIn("filters", resp.data)

    def test_returns_restaurant_list(self):
        profile = _make_profile()
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Rating") as mock_rating:
                    mock_rating.objects.aggregate.return_value = {"avg": None, "cnt": 0}
                    resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["restaurants"]), 1)
        r = resp.data["restaurants"][0]
        self.assertEqual(r["slug"], "bistro")
        self.assertEqual(r["name"], "Bistro Paris")

    def test_filters_structure_has_cities_and_cuisines(self):
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([])
            resp = self._get()
        self.assertIn("cities", resp.data["filters"])
        self.assertIn("cuisines", resp.data["filters"])

    def test_filters_derived_from_fetched_rows(self):
        """Cities/cuisines come from the profiles in the queryset page (no extra DB call)."""
        profile = _make_profile(city="Casablanca", cuisine_type="Moroccan")
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Rating") as mock_rating:
                    mock_rating.objects.aggregate.return_value = {"avg": None, "cnt": 0}
                    resp = self._get()
        self.assertIn("Casablanca", resp.data["filters"]["cities"])
        self.assertIn("Moroccan", resp.data["filters"]["cuisines"])

    def test_city_filter_applied(self):
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = _make_sliceable_qs([])
            qs.__getitem__ = lambda s, k: []
            resp = self._get(params={"city": "Paris"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cuisine_filter_applied(self):
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = _make_sliceable_qs([])
            qs.__getitem__ = lambda s, k: []
            resp = self._get(params={"cuisine": "Italian"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_is_open_honors_schedule_like_marketplace(self):
        """CHANGE 3a: DirectoryView derives is_open via the schedule-aware rule, so a
        profile that is currently closed reports is_open=False — identical to
        MarketplaceView. The verdict is recomputed LIVE at request time (post-cache) from
        the row's raw inputs, so the manual toggle off → False is reflected in the response."""
        profile = _make_profile(is_open=False)  # manual toggle off → closed
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["restaurants"][0]["is_open"])

    def test_is_open_true_when_schedule_says_open(self):
        """The same rule reports is_open=True when the restaurant is open (manual toggle on,
        no schedule restriction → open). Recomputed live at request time from raw inputs."""
        profile = _make_profile()  # is_open=True, empty schedule → open
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["restaurants"][0]["is_open"])


# ── MarketplaceView ───────────────────────────────────────────────────────────

# Patch targets for the batch flash-sale lookups (imported inside the view
# as `from .models import PlatformFlashSale, PlatformFlashSaleOptIn`).
_OPTIN_PATCH = "accounts.models.PlatformFlashSaleOptIn"
_FS_PATCH = "accounts.models.PlatformFlashSale"
# The view accesses them via `from .models import ...` inside accounts.views, so
# we patch at the accounts.views module level using the actual import path.
_OPTIN_VIEW_PATCH = "accounts.views.PlatformFlashSaleOptIn"
_FS_VIEW_PATCH = "accounts.views.PlatformFlashSale"


def _patch_flash_sales(opted_rows=None, live_fs_objs=None):
    """
    Return a context manager pair that patches PlatformFlashSaleOptIn.objects.values()
    and PlatformFlashSale.objects.filter() used by the batch pre-fetch in MarketplaceView.
    opted_rows: list of dicts like [{"tenant_id": 1, "flash_sale_id": 10}]
    live_fs_objs: list of mock PlatformFlashSale instances (each with .id, .is_active, .is_live())
    """
    from contextlib import ExitStack
    from unittest.mock import patch, MagicMock

    optin_mock = MagicMock()
    optin_mock.objects.values.return_value = opted_rows or []

    fs_mock = MagicMock()
    fs_mock.objects.filter.return_value = live_fs_objs or []

    return optin_mock, fs_mock


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class MarketplaceViewTests(SimpleTestCase):
    def setUp(self):
        cache.clear()  # responses are cached by query params — isolate each test
        self.factory = APIRequestFactory()
        self.view = MarketplaceView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/marketplace/", params or {})
        req.user = _anon()
        return self.view(req)

    def _empty_qs_mock(self, mock_p):
        """Configure mock Profile so the view sees an empty queryset page."""
        qs = MagicMock()
        mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
        qs.filter.return_value = qs
        # list(qs[:200]) — __getitem__ with a slice must return an iterable.
        qs.__getitem__ = lambda s, k: []

    def _with_flash_patches(self, fn, *args, **kwargs):
        """Run fn with the flash-sale batch queries patched to return nothing.

        The view does `from .models import PlatformFlashSale, PlatformFlashSaleOptIn`
        inside a local try block, so we must patch at accounts.models (the source).
        """
        optin_m = MagicMock()
        optin_m.objects.values.return_value = []
        fs_m = MagicMock()
        fs_m.objects.filter.return_value = []
        with patch("accounts.models.PlatformFlashSaleOptIn", optin_m):
            with patch("accounts.models.PlatformFlashSale", fs_m):
                return fn(*args, **kwargs)

    def test_returns_200_empty_results(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("restaurants", resp.data)
        self.assertIn("filters", resp.data)

    def test_filters_structure_includes_tags(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get)
        self.assertIn("tags", resp.data["filters"])

    def test_filters_derived_from_fetched_rows(self):
        """cities/cuisines/tags come from in-memory profile rows, not extra DB queries."""
        profile = _make_profile(city="Marrakech", cuisine_type="Moroccan", tags=["halal"])
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            with patch("accounts.views._compute_is_open_now", return_value=True):
                with patch("django_tenants.utils.schema_context", _sc_mock()):
                    with patch("menu.models.Rating") as mock_rating:
                        mock_rating.objects.aggregate.return_value = {"avg": None, "cnt": 0}
                        with patch("menu.models.Promotion") as mock_promo:
                            mock_promo.objects.filter.return_value.order_by.return_value.__getitem__ = \
                                lambda s, k: []
                            optin_m = MagicMock()
                            optin_m.objects.values.return_value = []
                            fs_m = MagicMock()
                            fs_m.objects.filter.return_value = []
                            with patch("accounts.models.PlatformFlashSaleOptIn", optin_m):
                                with patch("accounts.models.PlatformFlashSale", fs_m):
                                    resp = self._get()
        self.assertIn("Marrakech", resp.data["filters"]["cities"])
        self.assertIn("Moroccan", resp.data["filters"]["cuisines"])
        self.assertIn("halal", resp.data["filters"]["tags"])

    def test_flash_sale_active_set_when_opted_in_and_live(self):
        """flash_sale_active=True when tenant is opted-in to a live flash sale."""
        profile = _make_profile()
        profile.tenant.id = 42
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            with patch("accounts.views._compute_is_open_now", return_value=True):
                with patch("django_tenants.utils.schema_context", _sc_mock()):
                    with patch("menu.models.Rating") as mock_rating:
                        mock_rating.objects.aggregate.return_value = {"avg": None, "cnt": 0}
                        with patch("menu.models.Promotion") as mock_promo:
                            mock_promo.objects.filter.return_value.order_by.return_value.__getitem__ = \
                                lambda s, k: []
                            # Opt-in: tenant 42 → flash_sale 7
                            optin_m = MagicMock()
                            optin_m.objects.values.return_value = [
                                {"tenant_id": 42, "flash_sale_id": 7}
                            ]
                            # Live flash sale with id=7. Carry REAL is_live() inputs
                            # (datetimes + ints) — the view caches these into the payload's
                            # flash window for the request-time recompute, and they must be
                            # picklable + comparable to now.
                            from django.utils import timezone as _tz
                            from datetime import timedelta as _td
                            live_fs = MagicMock()
                            live_fs.id = 7
                            live_fs.is_active = True
                            live_fs.active_from = _tz.now() - _td(hours=1)
                            live_fs.active_until = _tz.now() + _td(hours=1)
                            live_fs.max_redemptions = None
                            live_fs.redemption_count = 0
                            live_fs.is_live.return_value = True
                            fs_m = MagicMock()
                            fs_m.objects.filter.return_value = [live_fs]
                            with patch("accounts.models.PlatformFlashSaleOptIn", optin_m):
                                with patch("accounts.models.PlatformFlashSale", fs_m):
                                    resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["restaurants"][0]["flash_sale_active"])

    def test_flash_sale_inactive_when_not_opted_in(self):
        """flash_sale_active=False when tenant has no opt-in."""
        profile = _make_profile()
        profile.tenant.id = 99
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            with patch("accounts.views._compute_is_open_now", return_value=True):
                with patch("django_tenants.utils.schema_context", _sc_mock()):
                    with patch("menu.models.Rating") as mock_rating:
                        mock_rating.objects.aggregate.return_value = {"avg": None, "cnt": 0}
                        with patch("menu.models.Promotion") as mock_promo:
                            mock_promo.objects.filter.return_value.order_by.return_value.__getitem__ = \
                                lambda s, k: []
                            # No opt-ins for this tenant
                            optin_m = MagicMock()
                            optin_m.objects.values.return_value = []
                            fs_m = MagicMock()
                            fs_m.objects.filter.return_value = []
                            with patch("accounts.models.PlatformFlashSaleOptIn", optin_m):
                                with patch("accounts.models.PlatformFlashSale", fs_m):
                                    resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["restaurants"][0]["flash_sale_active"])

    def test_open_filter_param(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"open": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_fulfillment_delivery_filter(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"fulfillment": "delivery"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_lat_lng_sort(self):
        """lat/lng params are accepted without error."""
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"lat": "48.8566", "lng": "2.3522"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_invalid_lat_lng_ignored(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"lat": "not-a-float", "lng": "also-not"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_min_rating_filter_no_crash(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"min_rating": "4.0"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_price_tier_filter(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"price_tier": "2"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_tags_filter(self):
        with patch("tenancy.models.Profile") as mock_p:
            self._empty_qs_mock(mock_p)
            resp = self._with_flash_patches(self._get, params={"tags": "halal,vegetarian"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ── R9: SQL search + backward-compatible pagination ───────────────────────────
# These guard the R9 scale/discoverability fix:
#   FIX1 — ?q= search runs in SQL on the FULL queryset (before any slice), so it finds a
#          tenant that would fall PAST the old pre-slice window. Proven non-DB by asserting
#          the ?q= filter is pushed into the queryset (.filter with a Q on the right fields)
#          and that the in-Python haystack no longer drops a SQL-matched row.
#   FIX2 — page/page_size + has_more, with a no-param request staying backward-compatible
#          (default page_size = 100 = the old cap; restaurants[] + filters unchanged; new
#          keys added alongside). Pagination boundaries are exercised with a slice-aware
#          fake queryset so has_more flips True/False at the real page edges.


class _FakeListQS:
    """A minimal queryset stand-in over an in-memory list of rows.

    Supports the exact operations the public list views use on the queryset:
      - .filter(*a, **k)  → records the call, returns self (chainable)
      - qs[start:stop]    → real Python slice of the backing list (so pagination boundaries
                            and has_more are exercised for real, not mocked away)
      - iteration / qs[:] → the full backing list (MarketplaceView does list(qs[:]))
    Ordering is treated as already-applied (rows are supplied in final order).
    """

    def __init__(self, rows):
        self._rows = list(rows)
        self.filter_calls = []  # list of (args, kwargs) for assertions

    def filter(self, *args, **kwargs):
        self.filter_calls.append((args, kwargs))
        return self

    def __getitem__(self, key):
        return self._rows[key]

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return len(self._rows)


def _profiles(n, *, name_prefix="R", **overrides):
    """Build n distinct profile mocks, named/slugged R0..R(n-1) in order."""
    out = []
    for i in range(n):
        p = _make_profile(**overrides)
        p.tenant = MagicMock()
        p.tenant.id = i
        p.tenant.slug = f"r{i}"
        p.tenant.name = f"{name_prefix}{i:03d}"
        p.tenant.schema_name = f"r{i}"
        out.append(p)
    return out


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class MarketplaceSqlSearchTests(SimpleTestCase):
    """FIX1: ?q= is pushed into SQL BEFORE slicing (finds matches past the old window)."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = MarketplaceView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/marketplace/", params or {})
        req.user = _anon()
        return self.view(req)

    def _run(self, fake_qs, params):
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = fake_qs
            with patch("accounts.views._compute_is_open_now", return_value=True):
                optin_m = MagicMock(); optin_m.objects.values.return_value = []
                fs_m = MagicMock(); fs_m.objects.filter.return_value = []
                with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                        patch("accounts.models.PlatformFlashSale", fs_m):
                    return self._get(params)

    def test_q_is_pushed_into_sql_before_slicing(self):
        """The ?q= term is applied as a queryset .filter (SQL), so the DB does the search
        over ALL tenants — not a Python pass over a pre-sliced qs[:200] window. We assert a
        .filter call carrying a Q over name/tagline/cuisine/city was made on the queryset."""
        from django.db.models import Q

        # The "match" — a tenant that, in a large table, would sort PAST the old 100/200
        # window in tenant__name order. Because the search is SQL, the DB returns it directly
        # and the view never windows it away.
        target = _make_profile()
        target.tenant.name = "Zzz Far Bistro"   # high in tenant__name order → past the window
        target.tenant.slug = "zzz-far"
        fake_qs = _FakeListQS([target])

        resp = self._run(fake_qs, {"q": "zzz"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The match is returned (SQL filtered it in)…
        slugs = [r["slug"] for r in resp.data["restaurants"]]
        self.assertIn("zzz-far", slugs)
        # …and a Q-based .filter was applied to the queryset (SQL search, not Python window).
        q_filter_calls = [
            args for (args, kwargs) in fake_qs.filter_calls
            if args and isinstance(args[0], Q)
        ]
        self.assertTrue(
            q_filter_calls,
            "expected ?q= to be applied as a queryset .filter(Q(...)) (SQL), found none",
        )

    def test_q_no_python_window_filter_returns_sql_result_verbatim(self):
        """Proof the Python haystack no longer gates results: a row whose in-memory fields do
        NOT contain the term is STILL returned if the (mocked) SQL filter yielded it — i.e.
        the view trusts the SQL filter and does not re-filter by q in Python. Pre-fix, the
        Python `if q not in haystack: continue` would have dropped this row."""
        # Field values deliberately do NOT contain "needle"; only the SQL layer (mocked to
        # return this row) decides membership now.
        row = _make_profile(tagline="plain", cuisine_type="Italian", city="Paris")
        row.tenant.name = "Bistro"
        fake_qs = _FakeListQS([row])

        resp = self._run(fake_qs, {"q": "needle"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Row survives — no Python window re-filter dropped it.
        self.assertEqual(len(resp.data["restaurants"]), 1)
        self.assertEqual(resp.data["restaurants"][0]["slug"], "bistro")

    def test_no_q_does_not_apply_search_filter(self):
        """Without ?q=, no Q-based search filter is added (only the structural filters)."""
        from django.db.models import Q
        row = _make_profile()
        fake_qs = _FakeListQS([row])
        resp = self._run(fake_qs, {})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        q_filter_calls = [
            args for (args, kwargs) in fake_qs.filter_calls
            if args and isinstance(args[0], Q)
        ]
        self.assertEqual(q_filter_calls, [], "no ?q= → no Q search filter expected")


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class MarketplacePaginationTests(SimpleTestCase):
    """FIX2: page/page_size + has_more on MarketplaceView; no-param is backward-compatible."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = MarketplaceView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/marketplace/", params or {})
        req.user = _anon()
        return self.view(req)

    def _run(self, rows, params):
        fake_qs = _FakeListQS(rows)
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = fake_qs
            with patch("accounts.views._compute_is_open_now", return_value=True):
                optin_m = MagicMock(); optin_m.objects.values.return_value = []
                fs_m = MagicMock(); fs_m.objects.filter.return_value = []
                with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                        patch("accounts.models.PlatformFlashSale", fs_m):
                    return self._get(params)

    def test_no_param_request_is_backward_compatible(self):
        """A request with NO page/page_size returns restaurants[] (up to the old cap of 100)
        plus the additive keys — un-updated frontend keeps working."""
        rows = _profiles(5)
        resp = self._run(rows, {})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Existing keys preserved.
        self.assertIn("restaurants", resp.data)
        self.assertIn("filters", resp.data)
        self.assertEqual(len(resp.data["restaurants"]), 5)
        # New additive keys present with the non-breaking default page_size = 100.
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["page_size"], 100)
        self.assertFalse(resp.data["has_more"])
        self.assertEqual(resp.data["total"], 5)

    def test_default_page_size_caps_at_100_with_has_more(self):
        """101 matching tenants, no params → page 1 returns 100 (the old cap) and has_more=True
        (proving rows past the old window are now reachable via page 2)."""
        rows = _profiles(101)
        resp = self._run(rows, {})
        self.assertEqual(len(resp.data["restaurants"]), 100)
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(resp.data["total"], 101)

    def test_page_2_returns_next_slice(self):
        """page=2&page_size=10 returns rows 10..19 (stable, sorted-before-paginate slice)."""
        rows = _profiles(25)  # R000..R024 in tenant__name order
        resp = self._run(rows, {"page": "2", "page_size": "10"})
        slugs = [r["slug"] for r in resp.data["restaurants"]]
        self.assertEqual(slugs, [f"r{i}" for i in range(10, 20)])
        self.assertEqual(resp.data["page"], 2)
        self.assertEqual(resp.data["page_size"], 10)
        self.assertTrue(resp.data["has_more"])  # rows 20..24 remain

    def test_has_more_false_on_last_page(self):
        """The final page reports has_more=False."""
        rows = _profiles(25)
        resp = self._run(rows, {"page": "3", "page_size": "10"})  # rows 20..24
        slugs = [r["slug"] for r in resp.data["restaurants"]]
        self.assertEqual(slugs, [f"r{i}" for i in range(20, 25)])
        self.assertFalse(resp.data["has_more"])

    def test_page_size_clamped_to_cap_50(self):
        """An explicit page_size above the cap (50) is clamped to 50."""
        rows = _profiles(60)
        resp = self._run(rows, {"page_size": "999"})
        self.assertEqual(resp.data["page_size"], 50)
        self.assertEqual(len(resp.data["restaurants"]), 50)
        self.assertTrue(resp.data["has_more"])

    def test_filters_select_from_full_set_not_a_window(self):
        """A filter (here ?open=1 via computed is_open) selects from the FULL set before
        pagination: with all rows open, total reflects every matching tenant, and page 2 is
        reachable — i.e. filtering is not confined to a pre-slice window."""
        rows = _profiles(120)
        resp = self._run(rows, {"open": "1", "page": "2", "page_size": "50"})
        # Full set is 120 → page 2 (rows 50..99) is 50 rows with more remaining.
        self.assertEqual(len(resp.data["restaurants"]), 50)
        self.assertEqual(resp.data["total"], 120)
        self.assertTrue(resp.data["has_more"])


class DirectoryPaginationTests(SimpleTestCase):
    """FIX2: page/page_size + has_more on DirectoryView; no-param is backward-compatible."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = DirectoryView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/directory/", params or {})
        req.user = _anon()
        return self.view(req)

    def _run(self, rows, params):
        fake_qs = _FakeListQS(rows)
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = fake_qs
            return self._get(params)

    def test_no_param_request_is_backward_compatible(self):
        rows = _profiles(3)
        resp = self._run(rows, {})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("restaurants", resp.data)
        self.assertIn("filters", resp.data)
        self.assertEqual(len(resp.data["restaurants"]), 3)
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["page_size"], 100)
        self.assertFalse(resp.data["has_more"])

    def test_default_page_size_caps_at_100_with_has_more(self):
        rows = _profiles(101)
        resp = self._run(rows, {})
        self.assertEqual(len(resp.data["restaurants"]), 100)
        self.assertTrue(resp.data["has_more"])

    def test_page_2_returns_next_slice(self):
        rows = _profiles(25)
        resp = self._run(rows, {"page": "2", "page_size": "10"})
        slugs = [r["slug"] for r in resp.data["restaurants"]]
        self.assertEqual(slugs, [f"r{i}" for i in range(10, 20)])
        self.assertTrue(resp.data["has_more"])

    def test_has_more_false_on_last_page(self):
        rows = _profiles(25)
        resp = self._run(rows, {"page": "3", "page_size": "10"})
        slugs = [r["slug"] for r in resp.data["restaurants"]]
        self.assertEqual(slugs, [f"r{i}" for i in range(20, 25)])
        self.assertFalse(resp.data["has_more"])

    def test_page_size_clamped_to_cap_50(self):
        rows = _profiles(60)
        resp = self._run(rows, {"page_size": "999"})
        self.assertEqual(resp.data["page_size"], 50)
        self.assertEqual(len(resp.data["restaurants"]), 50)
        self.assertTrue(resp.data["has_more"])


# ── Post-cache live-verdict recompute (freshness fix) ─────────────────────────
# The list-cache freezes the whole response for the TTL, but is_open / promo_badge /
# flash_sale_active are time-sensitive. _refresh_marketplace_live_fields recomputes
# those off the cached RAW inputs at request time (no DB), strips the internal raw
# inputs, and never mutates the cached object. These tests prove: a cached payload
# yields FLIPPED verdicts at a later "now" while matching at fill-time, and no internal
# raw-input keys leak to the client.

class RefreshLiveFieldsTests(SimpleTestCase):
    """Unit tests for accounts.views._refresh_marketplace_live_fields."""

    def _schedule_open_0900_1700(self):
        # All days enabled 09:00–17:00 so the only variable is the clock.
        day = {"enabled": True, "open": "09:00", "close": "17:00"}
        return {k: dict(day) for k in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}

    def _cached_marketplace_payload(self):
        """A cache-FILLED marketplace payload (rows carry raw inputs + top-level windows)."""
        from django.utils import timezone as _tz
        from datetime import timedelta as _td
        return {
            "restaurants": [{
                "slug": "bistro", "name": "Bistro", "is_open": True,
                "promo_badge": None, "flash_sale_active": False,
                "business_hours_schedule": self._schedule_open_0900_1700(),
                # internal raw inputs
                "_raw_is_open": True,
                "_raw_menu_disabled": False,
                "_raw_timezone": "UTC",
                "_raw_schedule": self._schedule_open_0900_1700(),
                "_raw_marketplace_promos": [
                    # No date/day/time restriction → live whenever (matches the promo
                    # windowing rule in menu.promos: blank bounds = unbounded/all-day).
                    {"promo_type": "percentage", "discount_value": 20,
                     "active_from": None, "active_until": None,
                     "days": [], "time_start": None, "time_end": None},
                ],
                "_raw_opted_flash_ids": [7],
            }],
            "filters": {"cities": [], "cuisines": [], "tags": []},
            "_flash_windows": [{
                "id": 7, "is_active": True,
                "active_from": _tz.now() - _td(hours=1),
                "active_until": _tz.now() + _td(hours=1),
                "max_redemptions": None, "redemption_count": 0,
            }],
        }

    def test_is_open_recompute_flips_with_clock_cache_unchanged(self):
        """(a) Crossing the schedule boundary flips is_open; the cached object is unchanged."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from accounts import views

        payload = self._cached_marketplace_payload()

        # Inside hours → open.
        with patch.object(views, "_row_local_now",
                          return_value=datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC"))):
            open_resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertTrue(open_resp["restaurants"][0]["is_open"])

        # Same cached payload, later clock (after close) → closed (FLIPPED).
        with patch.object(views, "_row_local_now",
                          return_value=datetime(2026, 6, 15, 18, 0, tzinfo=ZoneInfo("UTC"))):
            closed_resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertFalse(closed_resp["restaurants"][0]["is_open"])

        # The cached payload itself was NOT mutated: raw inputs intact, is_open untouched.
        self.assertEqual(payload["restaurants"][0]["_raw_is_open"], True)
        self.assertEqual(payload["restaurants"][0]["is_open"], True)  # original fill-time value
        self.assertIn("_flash_windows", payload)  # top-level internal still on the cache

    def test_promo_and_flash_recompute_at_request_time(self):
        """(b) promo_badge + flash_sale_active recompute live and FLIP with the clock."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from django.utils import timezone as _tz
        from accounts import views

        payload = self._cached_marketplace_payload()

        # Promo has no date/time restriction → active now → badge present.
        with patch.object(views, "_row_local_now",
                          return_value=datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC"))):
            resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertEqual(resp["restaurants"][0]["promo_badge"], "20% off")
        self.assertTrue(resp["restaurants"][0]["flash_sale_active"])  # window live now, opted into 7

        # Move "now" past the flash window's active_until → flash flips OFF.
        future = _tz.now() + timedelta(days=2)
        with patch.object(views, "_row_local_now",
                          return_value=datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC"))):
            with patch("django.utils.timezone.now", return_value=future):
                resp2 = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertFalse(resp2["restaurants"][0]["flash_sale_active"])

    def test_open_filter_and_sort_reapplied_on_fresh_verdict(self):
        """(e) After recompute, ?open=1 drops rows that have closed since cache-fill, and the
        open-first sort reorders on the FRESH is_open — so an open-only response never
        contains a closed row, and a now-closed row never keeps its top slot."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from accounts import views

        def _row(name, schedule):
            return {
                "slug": name.lower(), "name": name, "is_open": True,
                "_raw_is_open": True, "_raw_menu_disabled": False,
                "_raw_timezone": "UTC", "_raw_schedule": schedule,
            }

        payload = {
            "restaurants": [
                _row("AClosed", self._schedule_open_0900_1700()),  # closed at 18:00
                _row("BOpen", {}),                                  # no schedule → open via raw is_open
            ],
            "filters": {"cities": [], "cuisines": [], "tags": []},
        }
        at_1800 = datetime(2026, 6, 15, 18, 0, tzinfo=ZoneInfo("UTC"))

        # open-first sort: the open row ranks above the now-closed one (which alphabetically
        # would sort first), proving the sort keys off the RECOMPUTED verdict.
        with patch.object(views, "_row_local_now", return_value=at_1800):
            sorted_resp = views._refresh_marketplace_live_fields(
                payload, include_promo_flash=False, open_first_sort=True)
        self.assertEqual([r["name"] for r in sorted_resp["restaurants"]], ["BOpen", "AClosed"])

        # ?open=1 filter: the now-closed row is dropped — never returned inside an open-only list.
        with patch.object(views, "_row_local_now", return_value=at_1800):
            open_only_resp = views._refresh_marketplace_live_fields(
                payload, include_promo_flash=False, open_only=True)
        self.assertEqual([r["name"] for r in open_only_resp["restaurants"]], ["BOpen"])
        self.assertTrue(all(r["is_open"] for r in open_only_resp["restaurants"]))

    def test_recompute_matches_fill_time_computation_same_instant(self):
        """(c) At now == fill-time, the recompute verdict EQUALS the fill-time helpers."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from accounts import views

        # Build a profile-shaped object the FILL-TIME helper consumes.
        prof = SimpleNamespace(
            is_open=True,
            is_menu_temporarily_disabled=False,
            timezone="UTC",
            business_hours_schedule=self._schedule_open_0900_1700(),
        )
        instant = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC"))

        # Fill-time verdict via the canonical helper at this instant.
        with patch("accounts.views.tenant_local_now", return_value=instant):
            fill_open = views._compute_is_open_now(prof)

        # Recompute verdict on the cached row at the SAME instant.
        payload = self._cached_marketplace_payload()
        with patch.object(views, "_row_local_now", return_value=instant):
            resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertEqual(resp["restaurants"][0]["is_open"], fill_open)

        # And after close, both agree on closed.
        after = datetime(2026, 6, 15, 20, 0, tzinfo=ZoneInfo("UTC"))
        with patch("accounts.views.tenant_local_now", return_value=after):
            fill_closed = views._compute_is_open_now(prof)
        with patch.object(views, "_row_local_now", return_value=after):
            resp2 = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        self.assertEqual(resp2["restaurants"][0]["is_open"], fill_closed)
        self.assertFalse(fill_closed)

    def test_no_internal_raw_inputs_leak_into_response(self):
        """(d) The response rows + payload carry NO internal raw-input keys."""
        from accounts import views
        payload = self._cached_marketplace_payload()
        resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=True)
        row = resp["restaurants"][0]
        for leak in ("_raw_is_open", "_raw_menu_disabled", "_raw_timezone", "_raw_schedule",
                     "_raw_marketplace_promos", "_raw_opted_flash_ids"):
            self.assertNotIn(leak, row)
        self.assertNotIn("_flash_windows", resp)
        # business_hours_schedule IS a public marketplace field → kept.
        self.assertIn("business_hours_schedule", row)

    def test_directory_recompute_only_touches_is_open_and_strips_internals(self):
        """DirectoryView path (include_promo_flash=False): is_open recomputed, internals
        stripped, no promo/flash keys introduced, schedule NOT leaked (directory shape)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from accounts import views

        payload = {
            "restaurants": [{
                "slug": "bistro", "name": "Bistro", "is_open": True,
                "_raw_is_open": True, "_raw_menu_disabled": False,
                "_raw_timezone": "UTC", "_raw_schedule": self._schedule_open_0900_1700(),
            }],
            "filters": {"cities": [], "cuisines": []},
        }
        with patch.object(views, "_row_local_now",
                          return_value=datetime(2026, 6, 15, 18, 0, tzinfo=ZoneInfo("UTC"))):
            resp = views._refresh_marketplace_live_fields(payload, include_promo_flash=False)
        row = resp["restaurants"][0]
        self.assertFalse(row["is_open"])  # after close → flipped to closed
        self.assertNotIn("promo_badge", row)
        self.assertNotIn("flash_sale_active", row)
        for leak in ("_raw_is_open", "_raw_menu_disabled", "_raw_timezone", "_raw_schedule"):
            self.assertNotIn(leak, row)
        # DirectoryView does not expose business hours.
        self.assertNotIn("business_hours_schedule", row)

    def test_cache_hit_path_recomputes_without_db(self):
        """End-to-end: a SECOND request (cache hit) recomputes is_open live from the cached
        payload — proving the cache-hit return path runs the recompute pass, no DB needed."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        profile = _make_profile()
        profile.is_open = True
        profile.timezone = "UTC"
        profile.business_hours_schedule = self._schedule_open_0900_1700()

        factory = APIRequestFactory()
        view = MarketplaceView.as_view()

        def _do_get():
            req = factory.get("/api/marketplace/", {})
            req.user = _anon()
            return view(req)

        cache.clear()
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            optin_m = MagicMock(); optin_m.objects.values.return_value = []
            fs_m = MagicMock(); fs_m.objects.filter.return_value = []
            with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                    patch("accounts.models.PlatformFlashSale", fs_m):
                # First request inside hours → fresh build + cache.set; is_open True.
                with patch("accounts.views._row_local_now",
                           return_value=datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC"))):
                    r1 = _do_get()
                self.assertTrue(r1.data["restaurants"][0]["is_open"])

                # Second request (CACHE HIT — Profile NOT re-queried): after close → False.
                mock_p.objects.filter.reset_mock()
                with patch("accounts.views._row_local_now",
                           return_value=datetime(2026, 6, 15, 18, 0, tzinfo=ZoneInfo("UTC"))):
                    r2 = _do_get()
                self.assertFalse(r2.data["restaurants"][0]["is_open"])
                # Cache hit did NO new Profile query.
                self.assertFalse(mock_p.objects.filter.called)
                # Response carries no internal raw inputs.
                self.assertNotIn("_raw_is_open", r2.data["restaurants"][0])
                self.assertNotIn("_flash_windows", r2.data)


# ── MarketplaceMenuView ───────────────────────────────────────────────────────

class MarketplaceMenuViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplaceMenuView.as_view()

    def _get(self, slug="bistro"):
        req = self.factory.get(f"/api/marketplace/menu/{slug}/")
        req.user = _anon()
        return self.view(req, slug=slug)

    def test_unknown_slug_returns_404(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            mock_tenant.objects.get.side_effect = _FakeDNE
            resp = self._get(slug="unknown")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    def test_suspended_tenant_returns_404(self):
        """A non-ACTIVE (suspended/past-grace) tenant is not reachable via the marketplace."""
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            t = MagicMock()
            t.lifecycle_status = "suspended"  # != mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = t
            resp = self._get(slug="bistro")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "unavailable")

    def test_menu_import_block_resolves_no_server_error(self):
        """Regression: MarketplaceMenuView imported `Profile` from menu.models (which
        defines no Profile) → ImportError swallowed by the broad try/except into a 500
        `server_error` on every request. Profile now comes from tenancy.models. Drive the
        view INTO the schema_context import block and assert it does NOT 500 server_error.
        With Profile.objects...first()=None the view returns the 'unavailable' 404, which
        proves the import block executed (pre-fix it never got past the import)."""
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls:
                mock_profile_cls.objects.filter.return_value.first.return_value = None
                resp = self._get()
        self.assertNotEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotEqual(resp.data.get("code"), "server_error")
        self.assertEqual(resp.data.get("code"), "unavailable")

    def test_schema_error_returns_500(self):
        """If anything inside schema_context raises, the view returns 500."""
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            # schema_context itself raises
            with patch("django_tenants.utils.schema_context", side_effect=Exception("db error")):
                resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(resp.data["code"], "server_error")

    def test_dish_queryset_excludes_paused_super_category(self):
        """Dish filter must include category__super_category__is_temporarily_disabled=False.

        Regression guard for the gap where a paused SuperCategory still exposed its
        child dishes in the marketplace while the direct tenant menu correctly hid them.

        The view imports menu models inside schema_context at function scope, so we
        inject fakes via sys.modules to intercept the filter call.
        """
        import sys

        tenant = MagicMock()
        tenant.schema_name = "bistro"

        # Build mock Dish ORM chain; .filter() records kwargs, .order_by() returns [].
        mock_dish_qs = MagicMock()
        mock_dish_qs.filter.return_value = mock_dish_qs
        mock_dish_qs.select_related.return_value = mock_dish_qs
        mock_dish_qs.prefetch_related.return_value = mock_dish_qs
        mock_dish_qs.order_by.return_value = []

        mock_dish_cls = MagicMock()
        mock_dish_cls.objects.filter.return_value = mock_dish_qs

        mock_profile = MagicMock()
        mock_profile.is_menu_published = True
        mock_profile_cls = MagicMock()
        mock_profile_cls.objects.filter.return_value.first.return_value = mock_profile

        mock_lc_cls = MagicMock()
        mock_lc_cls.objects.filter.return_value.first.return_value = None

        # Build a fake menu.models module with only what the view imports.
        fake_menu_models = MagicMock()
        fake_menu_models.Profile = mock_profile_cls
        fake_menu_models.SuperCategory = MagicMock()
        fake_menu_models.Category = MagicMock()
        fake_menu_models.Dish = mock_dish_cls
        fake_menu_models.OptionGroup = MagicMock()
        fake_menu_models.LoyaltyConfig = mock_lc_cls

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant

            # Profile is imported from tenancy.models (NOT menu.models), so patch it there.
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile", mock_profile_cls):
                original_menu_models = sys.modules.get("menu.models")
                sys.modules["menu.models"] = fake_menu_models
                try:
                    self._get()
                finally:
                    if original_menu_models is None:
                        sys.modules.pop("menu.models", None)
                    else:
                        sys.modules["menu.models"] = original_menu_models

        # Verify the filter was called with the super_category pause guard.
        self.assertTrue(
            mock_dish_cls.objects.filter.called,
            "Dish.objects.filter should have been called",
        )
        call_kwargs = mock_dish_cls.objects.filter.call_args[1]
        self.assertIn(
            "category__super_category__is_temporarily_disabled",
            call_kwargs,
            "Dish filter must exclude dishes from paused SuperCategories",
        )
        self.assertFalse(
            call_kwargs["category__super_category__is_temporarily_disabled"],
        )


# ── MarketplacePlaceOrderView ─────────────────────────────────────────────────

class MarketplacePlaceOrderViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/marketplace/order/", data, format="json")
        req.user = _anon()
        req.session = session or {}
        return self.view(req)

    def test_missing_restaurant_returns_400(self):
        resp = self._post({"items": [{"slug": "burger", "qty": 1}]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_restaurant")

    def test_unknown_restaurant_returns_404(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            mock_tenant.objects.get.side_effect = _FakeDNE
            resp = self._post({"restaurant": "unknown", "items": [{"slug": "x", "qty": 1}]})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    def test_suspended_tenant_refuses_order(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            t = MagicMock(); t.lifecycle_status = "suspended"  # != ACTIVE
            mock_tenant.objects.get.return_value = t
            resp = self._post({"restaurant": "bistro", "items": [{"slug": "x", "qty": 1}]})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "unavailable")

    def test_missing_items_returns_400(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            t = MagicMock(); t.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = t
            resp = self._post({"restaurant": "bistro"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_items")

    def test_empty_items_list_returns_400(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            t = MagicMock(); t.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = t
            resp = self._post({"restaurant": "bistro", "items": []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_items")

    def test_delivery_without_auth_returns_403(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            t = MagicMock(); t.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = t
            resp = self._post({
                "restaurant": "bistro",
                "items": [{"slug": "burger", "qty": 1}],
                "fulfillment_type": "delivery",
            })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "auth_required")

    def test_order_placement_import_block_resolves_no_server_error(self):
        """Regression: MarketplacePlaceOrderView imported `Profile` from menu.models (which
        defines no Profile) → ImportError swallowed by the broad try/except into a 500
        `server_error` on every marketplace order. Profile now comes from tenancy.models.
        Drive a pickup order INTO the schema_context import block and assert it does NOT
        500 server_error. With Profile.objects...first()=None the view returns the
        'unavailable' 404 — proving the import block executed (pre-fix it 500'd at the import)."""
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls:
                mock_profile_cls.objects.filter.return_value.first.return_value = None
                resp = self._post({
                    "restaurant": "bistro",
                    "items": [{"slug": "burger", "qty": 1}],
                    "fulfillment_type": "pickup",
                })
        self.assertNotEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotEqual(resp.data.get("code"), "server_error")
        self.assertEqual(resp.data.get("code"), "unavailable")


# ── MarketplaceOrderStatusView ────────────────────────────────────────────────

class MarketplaceOrderStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderStatusView.as_view()

    def _get(self, order_number="ORD-001", params=None, session_cid=None):
        req = self.factory.get(
            f"/api/marketplace/order/{order_number}/",
            params or {},
        )
        req.user = _anon()
        # OPS-5e: the financial body is gated on the session customer OWNING the
        # order. Default to no session (anonymous → minimal body); pass session_cid
        # to simulate the owner.
        req.session = {"customer_id": session_cid} if session_cid is not None else {}
        return self.view(req, order_number=order_number)

    def test_missing_restaurant_param_returns_400(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_restaurant")

    def test_unknown_restaurant_returns_404(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            mock_tenant.objects.get.side_effect = _FakeDNE
            resp = self._get(params={"restaurant": "unknown"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    def test_order_not_found_returns_404(self):
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Order") as mock_order:
                    mock_order.objects.filter.return_value.prefetch_related.return_value.first.return_value = None
                    resp = self._get(params={"restaurant": "bistro"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    def test_valid_order_owner_returns_full_body(self):
        """OPS-5e: the session customer who OWNS the order gets the full financial body."""
        tenant = MagicMock()
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"
        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "confirmed"
        order.fulfillment_type = "pickup"
        order.customer_id = 7
        order.total = "25.00"
        order.delivery_fee = "0.00"
        order.wallet_amount_paid = "0.00"
        order.currency = "EUR"
        order.estimated_ready_minutes = 20
        order.scheduled_for = None
        order.items.all.return_value = []

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Order") as mock_order:
                    mock_order.objects.filter.return_value.prefetch_related.return_value.first.return_value = order
                    # Session customer matches order.customer_id → owner.
                    resp = self._get(params={"restaurant": "bistro"}, session_cid=7)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order_number"], "ORD-001")
        self.assertEqual(resp.data["status"], "confirmed")
        # Owner sees the financial detail.
        self.assertIn("items", resp.data)
        self.assertIn("total", resp.data)
        self.assertIn("payment_status", resp.data)

    def test_valid_order_non_owner_returns_minimal_body(self):
        """OPS-5e IDOR gate: an anonymous / non-owner caller gets ONLY the minimal,
        non-sensitive status — no items / totals / financial fields."""
        tenant = MagicMock()
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"
        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "confirmed"
        order.fulfillment_type = "pickup"
        order.customer_id = 7

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Order") as mock_order:
                    mock_order.objects.filter.return_value.prefetch_related.return_value.first.return_value = order
                    # No session (anonymous) → non-owner.
                    resp = self._get(params={"restaurant": "bistro"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order_number"], "ORD-001")
        self.assertEqual(resp.data["status"], "confirmed")
        self.assertEqual(resp.data["restaurant_slug"], "bistro")
        self.assertEqual(resp.data["restaurant_name"], "Bistro")
        # Financial / sensitive fields MUST be absent for a non-owner.
        for _leak in ("items", "total", "payment_status", "wallet_amount_paid",
                      "loyalty_discount", "delivery_code"):
            self.assertNotIn(_leak, resp.data)

    def test_schema_context_error_returns_500(self):
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", side_effect=Exception("crash")):
                resp = self._get(params={"restaurant": "bistro"})
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
