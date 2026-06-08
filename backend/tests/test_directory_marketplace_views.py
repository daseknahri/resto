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
from django.test import SimpleTestCase
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
                            # Live flash sale with id=7
                            live_fs = MagicMock()
                            live_fs.id = 7
                            live_fs.is_active = True
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


# ── MarketplaceOrderStatusView ────────────────────────────────────────────────

class MarketplaceOrderStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderStatusView.as_view()

    def _get(self, order_number="ORD-001", params=None):
        req = self.factory.get(
            f"/api/marketplace/order/{order_number}/",
            params or {},
        )
        req.user = _anon()
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

    def test_valid_order_returns_200(self):
        tenant = MagicMock()
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"
        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "confirmed"
        order.fulfillment_type = "pickup"
        order.total = "25.00"
        order.delivery_fee = "0.00"
        order.wallet_amount_paid = "0.00"
        order.currency = "EUR"
        order.estimated_ready_minutes = 20
        order.items.all.return_value = []

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Order") as mock_order:
                    mock_order.objects.filter.return_value.prefetch_related.return_value.first.return_value = order
                    resp = self._get(params={"restaurant": "bistro"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order_number"], "ORD-001")
        self.assertEqual(resp.data["status"], "confirmed")
        self.assertIn("items", resp.data)

    def test_schema_context_error_returns_500(self):
        tenant = MagicMock()
        tenant.schema_name = "bistro"
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", side_effect=Exception("crash")):
                resp = self._get(params={"restaurant": "bistro"})
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
