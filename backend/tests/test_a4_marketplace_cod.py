"""
A4 — Marketplace trusted-customer cash-on-handover (COD).

Mirrors the direct PlaceOrderView COD flow (menu/views.py) on the marketplace
path (accounts.views.MarketplacePlaceOrderView + MarketplaceMenuView).

Covered:
  * a COD-eligible customer who chooses cash on a marketplace pickup/delivery
    order places UNPAID with NO wallet deduction (bypasses the prepay gate);
  * a NON-eligible customer choosing cash still hits the wallet requirement
    (402 wallet_insufficient when the balance is short);
  * a scheduled order ignores cash and stays prepaid (402 when wallet short);
  * the marketplace menu payload exposes cod_enabled / cod_eligible.

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema switch).
The view imports its models at function scope INSIDE schema_context, so we inject
fakes through sys.modules (same technique as test_directory_marketplace_views.py).
"""
import sys
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import MarketplacePlaceOrderView, MarketplaceMenuView


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeDNE(Exception):
    """Stand-in for Model.DoesNotExist so the view's except clause works."""


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _sc_mock():
    """schema_context replacement that does nothing (no DB switch)."""
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


def _profile(cod_enabled=True):
    p = MagicMock()
    p.is_menu_published = True
    p.cod_enabled = cod_enabled
    p.cod_min_paid_orders = 3
    # No distance pricing / not delivery in these tests → flat path not exercised.
    p.lat = None
    p.lng = None
    return p


def _dish(slug="burger", price="10.00", currency="MAD", stock_qty=None):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.price = Decimal(price)
    d.currency = currency
    d.stock_qty = stock_qty  # None = unlimited (explicit so MagicMock isn't truthy)
    d.category = MagicMock()
    d.category.course = 0
    d.combo_components.all.return_value = []
    return d


def _customer(cid=7, wallet="0"):
    c = MagicMock()
    c.id = cid
    c.pk = cid
    c.wallet_balance = wallet
    c.name = "Repeat Diner"
    c.phone = "+212600000000"
    c.loyalty_points = 0
    return c


def _fake_menu_models(dish):
    """A fake menu.models module exposing only what the order path imports."""
    order_cls = MagicMock()
    order_cls.objects.filter.return_value.first.return_value = None  # no idempotent replay
    order_cls.objects.filter.return_value.exists.return_value = False  # order-number loop

    dish_cls = MagicMock()
    dish_qs = MagicMock()
    dish_qs.select_related.return_value = dish_qs
    dish_qs.prefetch_related.return_value = [dish]
    dish_cls.objects.filter.return_value = dish_qs
    dish_cls.objects.select_for_update.return_value.filter.return_value = []

    promo_cls = MagicMock()
    promo_cls.objects.filter.return_value.order_by.return_value = []

    do_cls = MagicMock()
    do_cls.objects.filter.return_value.select_related.return_value = []

    m = MagicMock()
    m.Dish = dish_cls
    m.DishOption = do_cls
    m.Order = order_cls
    m.OrderItem = MagicMock()
    m.Promotion = promo_cls
    return m, order_cls


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


# ── MarketplacePlaceOrderView — COD ───────────────────────────────────────────

class MarketplaceCodPlaceOrderTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/marketplace/order/", data, format="json")
        req.user = _anon()
        req.session = session or {}
        return self.view(req)

    def _run_order(self, *, cod_eligible, profile, customer, payload, created_order=None):
        """Drive a marketplace order through the schema_context block with the menu
        models + Customer + transaction mocked. Returns (response, order_cls, wtx_cls)."""
        dish = _dish()
        fake_menu, order_cls = _fake_menu_models(dish)
        if created_order is not None:
            order_cls.objects.create.return_value = created_order

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        wtx_cls = MagicMock()

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls, \
                    patch("accounts.views.Customer") as mock_cust_cls, \
                    patch("accounts.models.WalletTransaction", wtx_cls), \
                    patch("django.db.transaction.atomic", return_value=cm), \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("menu.views._cod_eligible", return_value=cod_eligible), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.pricing.effective_unit_price",
                          side_effect=lambda d, hh: (d.price, None)):
                mock_profile_cls.objects.filter.return_value.first.return_value = profile
                mock_cust_cls.DoesNotExist = _FakeDNE
                mock_cust_cls.objects.get.return_value = customer
                # locked customer fetch inside the wallet-deduction block
                mock_cust_cls.objects.select_for_update.return_value.get.return_value = customer
                with _inject_module("menu.models", fake_menu):
                    resp = self._post(payload, session={"customer_id": customer.id})
        return resp, order_cls, wtx_cls

    def test_cod_eligible_cash_pickup_places_unpaid_no_wallet_deduction(self):
        """A trusted (COD-eligible) customer choosing cash on a marketplace pickup
        order places without wallet prepayment: not blocked by the prepay gate, the
        order is created UNPAID, and NO wallet transaction is recorded."""
        profile = _profile(cod_enabled=True)
        customer = _customer(cid=7, wallet="0")  # no wallet funds, but COD-eligible

        created_order = MagicMock()
        created_order.order_number = "ORD-COD1"
        created_order.status = "pending"
        created_order.total = Decimal("10.00")
        created_order.delivery_fee = Decimal("0")
        created_order.currency = "MAD"
        created_order.wallet_amount_paid = Decimal("0")
        created_order.scheduled_for = None

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "pickup",
            "payment_method": "cash",
        }

        resp, order_cls, wtx_cls = self._run_order(
            cod_eligible=True, profile=profile, customer=customer, payload=payload,
            created_order=created_order,
        )

        # Full happy path ran (order created) — not blocked by the prepay gate.
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn(resp.data.get("code"), ("auth_required", "wallet_insufficient"))
        self.assertEqual(resp.data["wallet_amount_paid"], "0")

        # COD order must NOT debit the wallet (no PAYMENT transaction recorded).
        self.assertFalse(
            wtx_cls.objects.create.called,
            "COD order must not record a wallet PAYMENT transaction",
        )

        # The view settles PAID only inside the wallet/zero-total branch via
        # save(update_fields=["payment_status", "paid_at"]). For a COD order that
        # branch is skipped, so the order keeps its default PENDING state.
        _paid_saves = [
            c for c in created_order.save.call_args_list
            if c.kwargs.get("update_fields") == ["payment_status", "paid_at"]
        ]
        self.assertEqual(_paid_saves, [], "COD order must not be settled PAID at placement")

    def test_cash_without_cod_eligibility_still_requires_wallet(self):
        """Choosing cash when NOT COD-eligible falls back to the wallet prepay gate:
        402 wallet_insufficient when the balance is short."""
        profile = _profile(cod_enabled=True)  # owner enabled COD, but customer not trusted yet
        customer = _customer(cid=7, wallet="2.00")  # < 10.00 total

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "pickup",
            "payment_method": "cash",
        }
        resp, _order_cls, _wtx = self._run_order(
            cod_eligible=False, profile=profile, customer=customer, payload=payload,
        )
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(resp.data["code"], "wallet_insufficient")

    def test_scheduled_cash_order_ignores_cod_stays_prepaid(self):
        """A scheduled (advance) order ignores cash-on-handover and stays prepaid:
        even a COD-eligible customer hits the wallet gate (402 when the balance is short)."""
        profile = _profile(cod_enabled=True)
        customer = _customer(cid=7, wallet="2.00")  # < 10.00 total

        dish = _dish()
        fake_menu, _order_cls = _fake_menu_models(dish)

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "pickup",
            "payment_method": "cash",
            "scheduled_for": "2026-06-20T12:00:00+00:00",
        }

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls, \
                    patch("accounts.views.Customer") as mock_cust_cls, \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("menu.views._cod_eligible", return_value=True), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.views._validate_scheduled_for",
                          side_effect=lambda prof, ft, dt: (dt, None)), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.pricing.effective_unit_price",
                          side_effect=lambda d, hh: (d.price, None)):
                mock_profile_cls.objects.filter.return_value.first.return_value = profile
                mock_cust_cls.DoesNotExist = _FakeDNE
                mock_cust_cls.objects.get.return_value = customer
                with _inject_module("menu.models", fake_menu):
                    resp = self._post(payload, session={"customer_id": 7})

        # Scheduled → cash ignored → wallet gate applies → short balance → 402.
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(resp.data["code"], "wallet_insufficient")


# ── MarketplaceMenuView — eligibility exposure ────────────────────────────────

class MarketplaceMenuCodExposureTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplaceMenuView.as_view()

    def _get(self, slug="bistro", customer_id=None):
        from accounts.models import Customer
        req = self.factory.get(f"/api/marketplace/menu/{slug}/")
        # RISK IDENTITY-1: COD eligibility now reads customer_or_none(request.user),
        # hydrated by CustomerSessionAuthentication. force_authenticate a real Customer
        # principal instead of hand-setting the session id (which would trigger the auth
        # class's DB lookup on this no-DB SimpleTestCase).
        req.session = {}
        if customer_id is not None:
            force_authenticate(req, user=Customer(id=customer_id))
        return self.view(req, slug=slug)

    def _run(self, *, cod_enabled, cod_eligible, customer_id):
        """Drive MarketplaceMenuView with an empty menu but a published profile."""
        tenant = MagicMock()
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        profile = MagicMock()
        profile.is_menu_published = True
        profile.cod_enabled = cod_enabled
        profile.cod_min_paid_orders = 3
        # plain string-ish attrs the response serializes
        profile.tagline = ""
        profile.logo_url = ""
        profile.cuisine_type = ""
        profile.city = ""
        profile.address = ""
        profile.phone = ""
        profile.delivery_enabled = False
        profile.delivery_fee = "0"
        profile.delivery_base_fee = "0"
        profile.delivery_per_km = "0"
        profile.delivery_free_over = "0"
        profile.delivery_radius_km = None
        profile.delivery_minimum_order = "0"
        profile.lat = None
        profile.lng = None
        profile.price_tier = 1
        profile.tags = []

        dish_cls = MagicMock()
        dish_qs = MagicMock()
        dish_qs.select_related.return_value = dish_qs
        dish_qs.prefetch_related.return_value = dish_qs
        dish_qs.order_by.return_value = []
        dish_cls.objects.filter.return_value = dish_qs

        lc_cls = MagicMock()
        lc_cls.objects.filter.return_value.first.return_value = None

        rating_cls = MagicMock()
        rating_cls.objects.aggregate.return_value = {"avg": None, "cnt": 0}
        rating_cls.objects.filter.return_value.order_by.return_value.__getitem__ = \
            lambda s, k: []

        fake_menu = MagicMock()
        fake_menu.SuperCategory = MagicMock()
        fake_menu.Category = MagicMock()
        fake_menu.Dish = dish_cls
        fake_menu.OptionGroup = MagicMock()
        fake_menu.LoyaltyConfig = lc_cls
        fake_menu.Rating = rating_cls

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile", MagicMock(
                        objects=MagicMock(
                            filter=MagicMock(return_value=MagicMock(
                                first=MagicMock(return_value=profile)))))), \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("menu.views._cod_eligible", return_value=cod_eligible), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]):
                with _inject_module("menu.models", fake_menu):
                    # Flash-sale batch lookup (public schema) — return nothing.
                    optin_m = MagicMock()
                    optin_m.objects.filter.return_value.values_list.return_value = []
                    fs_m = MagicMock()
                    fs_m.objects.filter.return_value = []
                    with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                            patch("accounts.models.PlatformFlashSale", fs_m):
                        return self._get(customer_id=customer_id)

    def test_menu_payload_includes_cod_fields_eligible(self):
        resp = self._run(cod_enabled=True, cod_eligible=True, customer_id=7)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("cod_enabled", resp.data)
        self.assertIn("cod_eligible", resp.data)
        self.assertTrue(resp.data["cod_enabled"])
        self.assertTrue(resp.data["cod_eligible"])

    def test_menu_payload_cod_fields_false_when_disabled(self):
        resp = self._run(cod_enabled=False, cod_eligible=False, customer_id=None)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["cod_enabled"])
        self.assertFalse(resp.data["cod_eligible"])
