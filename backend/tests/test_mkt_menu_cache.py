"""MarketplaceMenuView 60s single-flight cache — the cached-vs-live split (the TRAP).

GET /api/marketplace/menu/<slug>/ now caches its heavy ANONYMOUS body (dish tree, prices,
reviews, prep-ETA, rating summary, loyalty) under ONE key per tenant (mkt_menu:v1:{slug}),
mirroring the tenant-subdomain twin (menu.views.DishViewSet.list) and the /api/meta/ cache.

THREE fields must NEVER be baked into that {slug}-keyed body; they are recomputed per request
on a COPY of the cached body:
  • cod_eligible — PER-CUSTOMER (trusted-repeat-customer trust). Caching it under {slug}
    would serve one customer's cash-on-handover trust status to every other shopper — a
    cross-customer data leak. THIS is the trap these tests guard.
  • is_open      — TIME-SENSITIVE open/closed verdict.
  • flash_sale   — TIME-SENSITIVE sale window.

All tests are unit-level (SimpleTestCase + mocks — no real DB / schema switch), and clear the
process-global cache in setUp so each starts cold. A shared fake `menu.models` with a spy on
Dish.objects.filter lets a test assert the heavy build ran only ONCE across two requests (i.e.
the second request was a cache HIT) while a live/per-customer field still differs between them.
"""
import sys
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import (
    MarketplaceMenuView,
    _bust_marketplace_menu_cache,
    _mkt_menu_cache_key,
)


class _FakeDNE(Exception):
    """Stand-in for Tenant.DoesNotExist so the view's except clause works."""


def _sc_mock():
    """schema_context replacement that does nothing (no DB switch)."""
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


@contextmanager
def _inject_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield
    finally:
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _make_profile(cod_enabled=True):
    """A published-menu profile whose every serialized field is a concrete PICKLABLE value
    (the cached body is pickled by LocMemCache on set, so MagicMock auto-attrs would break it)."""
    p = MagicMock()
    p.is_menu_published = True
    p.cod_enabled = cod_enabled
    p.cod_min_paid_orders = 3
    p.tagline = ""
    p.logo_url = ""
    p.cuisine_type = ""
    p.city = ""
    p.address = ""
    p.phone = ""
    p.business_type = "restaurant"
    p.currency = "MAD"
    p.delivery_enabled = False
    p.delivery_fee = "0"
    p.delivery_base_fee = "0"
    p.delivery_per_km = "0"
    p.delivery_free_over = "0"
    p.delivery_radius_km = None
    p.delivery_minimum_order = "0"
    p.lat = None
    p.lng = None
    p.price_tier = 1
    p.tags = []
    p.business_hours_schedule = {}
    p.is_menu_temporarily_disabled = False
    p.rating_avg = None
    p.rating_count = 0
    return p


def _make_fake_menu():
    """Fake ``menu.models`` exposing what MarketplaceMenuView._build imports. Dish.objects.filter
    is a SPY so a test can assert the heavy build ran only once (i.e. the body was cached).

    Returns (fake_module, dish_cls) — reuse the SAME pair across two _drive() calls so the spy's
    call_count accumulates across both requests.
    """
    dish_cls = MagicMock()
    dish_qs = MagicMock()
    dish_qs.select_related.return_value = dish_qs
    dish_qs.prefetch_related.return_value = dish_qs
    dish_qs.order_by.return_value = []  # empty menu → no dish mocks leak into the body
    dish_cls.objects.filter.return_value = dish_qs

    lc_cls = MagicMock()
    lc_cls.objects.filter.return_value.first.return_value = None  # no loyalty config

    rating_cls = MagicMock()
    rating_cls.objects.filter.return_value.order_by.return_value.__getitem__ = lambda s, k: []

    m = MagicMock()
    m.Dish = dish_cls
    m.LoyaltyConfig = lc_cls
    m.Rating = rating_cls
    return m, dish_cls


def _live_flash_sale(discount="20"):
    fs = MagicMock()
    fs.is_live.return_value = True
    fs.discount_value = Decimal(discount)
    fs.name = f"Flash {discount}"
    fs.active_until.isoformat.return_value = "2026-12-31T23:59:59+00:00"
    return fs


class _MktMenuCacheBase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # The view caches under mkt_menu:v1:{slug} in the process-global cache — start cold.
        cache.clear()

    def _drive(self, *, slug, fake_menu, profile, customer_id=None,
               is_open=True, flash_optin_ids=(), flash_sales=(), now_local=None):
        """Drive MarketplaceMenuView once. Reuse the SAME `fake_menu`/`profile` across calls to
        share the cache + build spy. Live values (is_open, flash) are per-call so a cache HIT can
        be shown to still reflect the current request-time state."""
        tenant = MagicMock()
        tenant.slug = slug
        tenant.name = "Bistro"
        tenant.schema_name = slug

        req = self.factory.get(f"/api/marketplace/menu/{slug}/")
        req.session = {}
        if customer_id is not None:
            from accounts.models import Customer
            force_authenticate(req, user=Customer(id=customer_id))

        optin_m = MagicMock()
        optin_m.objects.filter.return_value.values_list.return_value = list(flash_optin_ids)
        fs_m = MagicMock()
        fs_m.objects.filter.return_value.order_by.return_value = list(flash_sales)

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile", MagicMock(objects=MagicMock(
                        filter=MagicMock(return_value=MagicMock(
                            first=MagicMock(return_value=profile)))))), \
                    patch("accounts.views._compute_is_open_now", return_value=is_open), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.views._profile_now", return_value=now_local), \
                    patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                    patch("accounts.models.PlatformFlashSale", fs_m):
                with _inject_module("menu.models", fake_menu):
                    return MarketplaceMenuView.as_view()(req, slug=slug)


class CodEligiblePerCustomerTests(_MktMenuCacheBase):
    """THE TRAP: cod_eligible must be per-request, NOT cached under {slug}."""

    def test_two_customers_get_different_cod_from_the_same_cached_body(self):
        """Customer A (COD-eligible) and customer B (NOT eligible) hit the SAME slug back to
        back. They must receive DIFFERENT cod_eligible even though the heavy body was built
        ONCE and shared — proving cod_eligible is recomputed per request, never cached."""
        fake_menu, dish_cls = _make_fake_menu()
        profile = _make_profile(cod_enabled=True)

        # _cod_eligible is trusted for customer 1, untrusted for customer 2.
        with patch("menu.views._cod_eligible", side_effect=lambda prof, cid: cid == 1):
            resp_a = self._drive(slug="trap", fake_menu=fake_menu, profile=profile, customer_id=1)
            resp_b = self._drive(slug="trap", fake_menu=fake_menu, profile=profile, customer_id=2)

        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)

        # The trap: trust status is per-customer, never leaked across the shared body.
        self.assertTrue(resp_a.data["cod_eligible"], "trusted customer must be COD-eligible")
        self.assertFalse(resp_b.data["cod_eligible"], "untrusted customer must NOT be COD-eligible")

        # cod_enabled (the OWNER toggle) is the same for both — it IS cached in the body.
        self.assertTrue(resp_a.data["cod_enabled"])
        self.assertTrue(resp_b.data["cod_enabled"])

        # The heavy body was built exactly ONCE across the two requests (2nd was a cache HIT),
        # so the differing cod_eligible cannot have come from a rebuild — it is per-request.
        self.assertEqual(
            dish_cls.objects.filter.call_count, 1,
            "the anonymous body must be built once and shared (2nd request is a cache hit)",
        )

        # And the shared, cached NON-live fields are byte-identical between the two responses.
        self.assertEqual(resp_a.data["super_categories"], resp_b.data["super_categories"])
        self.assertEqual(resp_a.data["rating_count"], resp_b.data["rating_count"])

    def test_anonymous_shopper_never_inherits_a_prior_customers_trust(self):
        """A trusted customer builds the cache; a following ANONYMOUS shopper on the same slug
        must still get cod_eligible=False (not the trusted customer's True from the body)."""
        fake_menu, dish_cls = _make_fake_menu()
        profile = _make_profile(cod_enabled=True)

        with patch("menu.views._cod_eligible", side_effect=lambda prof, cid: cid == 1):
            resp_trusted = self._drive(slug="trap2", fake_menu=fake_menu, profile=profile, customer_id=1)
            resp_anon = self._drive(slug="trap2", fake_menu=fake_menu, profile=profile, customer_id=None)

        self.assertTrue(resp_trusted.data["cod_eligible"])
        self.assertFalse(resp_anon.data["cod_eligible"], "anonymous shopper must not inherit trust")
        self.assertEqual(dish_cls.objects.filter.call_count, 1)


class IsOpenLiveOnCacheHitTests(_MktMenuCacheBase):
    def test_is_open_reflects_live_verdict_on_a_cache_hit(self):
        """Build the body while open, then hit the cache while closed: is_open must flip to the
        LIVE verdict on the cache hit (it is never frozen for the TTL), body built once."""
        fake_menu, dish_cls = _make_fake_menu()
        profile = _make_profile()

        resp_open = self._drive(slug="hours", fake_menu=fake_menu, profile=profile, is_open=True)
        resp_closed = self._drive(slug="hours", fake_menu=fake_menu, profile=profile, is_open=False)

        self.assertTrue(resp_open.data["is_open"])
        self.assertFalse(resp_closed.data["is_open"], "is_open must be recomputed live on a cache hit")
        self.assertEqual(dish_cls.objects.filter.call_count, 1)


class FlashSaleLiveOnCacheHitTests(_MktMenuCacheBase):
    def test_flash_sale_reflects_live_state_on_a_cache_hit(self):
        """Build the body with no live sale, then hit the cache once a sale is live: flash_sale
        must reflect the LIVE sale on the cache hit (never frozen for the TTL), body built once."""
        fake_menu, dish_cls = _make_fake_menu()
        profile = _make_profile()

        resp_no_sale = self._drive(slug="flash", fake_menu=fake_menu, profile=profile)
        resp_live_sale = self._drive(
            slug="flash", fake_menu=fake_menu, profile=profile,
            flash_optin_ids=(1,), flash_sales=(_live_flash_sale("20"),),
        )

        self.assertIsNone(resp_no_sale.data["flash_sale"])
        self.assertIsNotNone(resp_live_sale.data["flash_sale"], "flash_sale must go live on a cache hit")
        self.assertEqual(resp_live_sale.data["flash_sale"]["discount_pct"], "20")
        self.assertEqual(dish_cls.objects.filter.call_count, 1)


def _dish_stub(slug="burger", *, schedule=None, component_ids=()):
    """A concrete (picklable-once-serialized) dish as _build reads it. `component_ids` makes it a combo."""
    sc = SimpleNamespace(id=1, name="Mains", name_i18n={}, position=0)
    cat = SimpleNamespace(id=1, name="Burgers", name_i18n={}, slug="burgers", image_url="", position=0,
                          super_category=sc)
    return SimpleNamespace(
        id=sum(map(ord, slug)), slug=slug, name=slug.title(), name_i18n={}, description="", description_i18n={},
        price=Decimal("10.00"), currency="MAD", image_url="", tags=[], allergens=[], is_available=True,
        availability_schedule=schedule, category=cat, position=0,
        option_groups=SimpleNamespace(all=lambda: []),
        combo_components=SimpleNamespace(all=lambda: [SimpleNamespace(component_id=c) for c in component_ids]),
    )


def _fake_menu_with(dishes):
    """_make_fake_menu() but the (single) build returns real dish stubs. Returns (fake_menu, dish_qs)
    — `dish_qs.order_by.call_count` is the heavy-build spy (the per-request combo-state read ALSO
    hits `Dish.objects.filter`, so `filter.call_count` can't be used for these tests)."""
    fake_menu, dish_cls = _make_fake_menu()
    dish_qs = dish_cls.objects.filter.return_value
    dish_qs.order_by.return_value = list(dishes)
    return fake_menu, dish_qs


def _all_dishes(resp):
    return [d for sc in resp.data["super_categories"] for c in sc["categories"] for d in c["dishes"]]


# 2026-10-05 is a Monday.
_MON_10H = datetime(2026, 10, 5, 10, 0)
_MON_12H = datetime(2026, 10, 5, 12, 0)


class DishFlagsLiveOnCacheHitTests(_MktMenuCacheBase):
    """The marketplace menu must emit the same per-dish `is_schedule_available` /
    `combo_unavailable` the direct storefront menu does — and, like is_open, compute them PER
    REQUEST, never baked into the {slug}-keyed body."""

    def test_sanity_fixture_dates_are_a_monday(self):
        self.assertEqual(_MON_10H.weekday(), 0)

    def test_schedule_flag_reflects_the_live_clock_on_a_cache_hit(self):
        """Window Mon 09:00-11:00. Build the body at 10:00 (open), then hit the cache at 12:00:
        the dish must flip to NOT available now on the cache hit (it can't freeze for the TTL)."""
        schedule = {"days": ["mon"], "time_start": "09:00", "time_end": "11:00"}
        fake_menu, dish_qs = _fake_menu_with([_dish_stub(schedule=schedule)])
        profile = _make_profile()

        resp_open = self._drive(slug="sched", fake_menu=fake_menu, profile=profile, now_local=_MON_10H)
        resp_closed = self._drive(slug="sched", fake_menu=fake_menu, profile=profile, now_local=_MON_12H)

        self.assertIs(_all_dishes(resp_open)[0]["is_schedule_available"], True)
        self.assertIs(_all_dishes(resp_closed)[0]["is_schedule_available"], False)
        self.assertEqual(dish_qs.order_by.call_count, 1, "2nd request must be a cache HIT (body built once)")

    def test_no_schedule_is_none_and_private_carriers_never_leak(self):
        """No schedule → None (always available by schedule, as in DishSerializer). The private
        cache-only carriers must be stripped from every response (hit or miss)."""
        schedule = {"days": ["mon"], "time_start": "09:00", "time_end": "11:00"}
        fake_menu, _ = _fake_menu_with([
            _dish_stub("plain"),
            _dish_stub("timed", schedule=schedule, component_ids=(5,)),
        ])
        profile = _make_profile()

        for _ in range(2):  # miss, then hit
            resp = self._drive(slug="strip", fake_menu=fake_menu, profile=profile, now_local=_MON_10H)
            by_slug = {d["slug"]: d for d in _all_dishes(resp)}
            self.assertIsNone(by_slug["plain"]["is_schedule_available"])
            self.assertIs(by_slug["plain"]["combo_unavailable"], False)
            for d in by_slug.values():
                self.assertNotIn("_availability_schedule", d)
                self.assertNotIn("_combo_component_ids", d)

    def test_malformed_schedule_degrades_to_available(self):
        """A garbage schedule must never hide a dish or 500 the menu (matches the serializer)."""
        fake_menu, _ = _fake_menu_with([_dish_stub(schedule={"days": "mon", "time_start": 9, "time_end": 11})])
        resp = self._drive(slug="badsched", fake_menu=fake_menu, profile=_make_profile(), now_local=_MON_10H)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNot(_all_dishes(resp)[0]["is_schedule_available"], False)

    def test_combo_unavailable_reflects_live_component_state_on_a_cache_hit(self):
        """A component selling out mid-TTL must grey the combo out on the CACHE HIT — not up to 60s late."""
        fake_menu, dish_qs = _fake_menu_with([_dish_stub("combo", component_ids=(7,))])
        profile = _make_profile()

        def drive(rows):
            dish_qs.values_list.return_value = rows
            resp = self._drive(slug="combo", fake_menu=fake_menu, profile=profile)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            return _all_dishes(resp)[0]["combo_unavailable"]

        self.assertIs(drive([(7, True, 5)]), False)       # component available, stock 5
        self.assertIs(drive([(7, False, None)]), True)    # component 86'd
        self.assertIs(drive([(7, True, 0)]), True)        # finite stock sold out
        self.assertIs(drive([(7, True, None)]), False)    # unlimited stock → fine
        self.assertEqual(dish_qs.order_by.call_count, 1, "every request after the 1st is a cache hit")

    def test_combo_state_read_failure_degrades_to_available(self):
        fake_menu, dish_qs = _fake_menu_with([_dish_stub("combo", component_ids=(7,))])
        dish_qs.values_list.side_effect = RuntimeError("db down")
        resp = self._drive(slug="combofail", fake_menu=fake_menu, profile=_make_profile())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIs(_all_dishes(resp)[0]["combo_unavailable"], False)

    def test_menu_without_combos_makes_no_component_query(self):
        fake_menu, dish_qs = _fake_menu_with([_dish_stub("plain")])
        dish_qs.values_list.side_effect = AssertionError("must not query component state without combos")
        resp = self._drive(slug="nocombo", fake_menu=fake_menu, profile=_make_profile())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MarketplaceMenuBustSeamTests(SimpleTestCase):
    """Every write seam that already busts a related cache also drops mkt_menu:v1:{slug}."""

    def setUp(self):
        cache.clear()

    def test_direct_bust_deletes_the_key(self):
        key = _mkt_menu_cache_key("busta")
        cache.set(key, {"cached": True}, 60)
        self.assertIsNotNone(cache.get(key))
        _bust_marketplace_menu_cache("busta")
        self.assertIsNone(cache.get(key), "bust must delete the cached body")

    def test_menu_write_seam_busts_the_key(self):
        """menu.views._bust_menu_cache (fires on every menu write) drops the marketplace body."""
        from menu.views import _bust_menu_cache
        key = _mkt_menu_cache_key("bustb")
        cache.set(key, {"cached": True}, 60)
        _bust_menu_cache("bustb")
        self.assertIsNone(cache.get(key), "a menu write must bust the marketplace-menu body")

    def test_profile_save_seam_busts_the_key(self):
        """tenancy.api._bust_tenant_meta_cache (fires on every Profile save) drops the body."""
        from tenancy.api import _bust_tenant_meta_cache
        key = _mkt_menu_cache_key("bustc")
        cache.set(key, {"cached": True}, 60)
        _bust_tenant_meta_cache("bustc")
        self.assertIsNone(cache.get(key), "a profile save must bust the marketplace-menu body")

    def test_empty_slug_is_a_noop(self):
        # Guard: a blank slug must not raise or delete anything unexpected.
        _bust_marketplace_menu_cache("")  # no raise
