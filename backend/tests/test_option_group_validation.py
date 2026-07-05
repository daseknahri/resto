"""
Tests for B2 (SECURITY) — server-side OptionGroup.min_select/max_select enforcement.

Covers:
  - menu.views._validate_option_group_selections (the shared helper)
  - PlaceOrderView              POST /api/place-order/
  - MarketplacePlaceOrderView   POST /api/marketplace/order/

Both endpoints already validate that each option_id is BOUND to the ordered dish
(stale_options); this adds the missing layer: enforcing OptionGroup min_select/
max_select, mirroring exactly what the SPA enforces client-side (DishPage.vue /
QuickAddSheet.vue / WaiterNewOrder.vue groupSelectedCount logic) so a valid SPA
order is never rejected — only malformed / API-bypass / replay requests are.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import _validate_option_group_selections, PlaceOrderView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _group(group_id, name="Size", min_select=1, max_select=1, option_ids=()):
    g = MagicMock()
    g.id = group_id
    g.name = name
    g.min_select = min_select
    g.max_select = max_select
    opts = []
    for oid in option_ids:
        o = MagicMock()
        o.id = oid
        opts.append(o)
    g.options.all.return_value = opts
    return g


def _dish_with_groups(slug="burger", groups=()):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.option_groups.all.return_value = list(groups)
    return d


# ═════════════════════════════════════════════════════════════════════════════
# Unit tests for the shared helper
# ═════════════════════════════════════════════════════════════════════════════

class ValidateOptionGroupSelectionsTests(SimpleTestCase):
    def test_no_groups_always_passes(self):
        dish = _dish_with_groups(groups=[])
        self.assertIsNone(_validate_option_group_selections(dish, [1, 2]))

    def test_required_group_satisfied_passes(self):
        group = _group(1, min_select=1, max_select=1, option_ids=[10, 11])
        dish = _dish_with_groups(groups=[group])
        self.assertIsNone(_validate_option_group_selections(dish, [10]))

    def test_required_group_missing_rejects(self):
        group = _group(1, name="Size", min_select=1, max_select=1, option_ids=[10, 11])
        dish = _dish_with_groups(groups=[group])
        err = _validate_option_group_selections(dish, [])
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "option_selection_invalid")
        self.assertEqual(err["reason"], "min_select")
        self.assertEqual(err["group_id"], 1)

    def test_over_max_rejects(self):
        group = _group(1, name="Toppings", min_select=0, max_select=2, option_ids=[10, 11, 12])
        dish = _dish_with_groups(groups=[group])
        err = _validate_option_group_selections(dish, [10, 11, 12])
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "option_selection_invalid")
        self.assertEqual(err["reason"], "max_select")

    def test_optional_group_zero_selected_passes(self):
        group = _group(1, name="Toppings", min_select=0, max_select=2, option_ids=[10, 11])
        dish = _dish_with_groups(groups=[group])
        self.assertIsNone(_validate_option_group_selections(dish, []))

    def test_multiple_groups_each_checked(self):
        size = _group(1, name="Size", min_select=1, max_select=1, option_ids=[10, 11])
        toppings = _group(2, name="Toppings", min_select=0, max_select=2, option_ids=[20, 21, 22])
        dish = _dish_with_groups(groups=[size, toppings])
        # Size satisfied, toppings within bounds.
        self.assertIsNone(_validate_option_group_selections(dish, [10, 20, 21]))
        # Size missing -> rejects even though toppings are fine.
        err = _validate_option_group_selections(dish, [20, 21])
        self.assertEqual(err["group_id"], 1)

    def test_ungrouped_option_ignored(self):
        """An option not in any group's set doesn't count toward or against a group."""
        group = _group(1, name="Size", min_select=1, max_select=1, option_ids=[10, 11])
        dish = _dish_with_groups(groups=[group])
        # 10 satisfies the group; 999 is an ungrouped/foreign id not tracked here
        # (dish-binding of ids is validated separately upstream).
        self.assertIsNone(_validate_option_group_selections(dish, [10, 999]))


# ═════════════════════════════════════════════════════════════════════════════
# PlaceOrderView — POST /api/place-order/
# ═════════════════════════════════════════════════════════════════════════════

def _plan(can_checkout=True, can_whatsapp_order=True):
    return SimpleNamespace(can_checkout=can_checkout, can_whatsapp_order=can_whatsapp_order)


def _tenant(plan=None, tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Demo", plan=plan or _plan())


def _profile(
    is_menu_published=True,
    is_menu_temporarily_disabled=False,
    is_open=True,
    delivery_fee="0",
):
    return SimpleNamespace(
        is_menu_published=is_menu_published,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
        is_open=is_open,
        delivery_fee=delivery_fee,
    )


def _mock_dish_with_group(slug="burger", price="10.00", currency="MAD", min_select=1, max_select=1, option_ids=(10, 11)):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.price = Decimal(price)
    d.currency = currency
    d.stock_qty = None
    group = _group(1, name="Size", min_select=min_select, max_select=max_select, option_ids=list(option_ids))
    d.option_groups.all.return_value = [group]
    d.combo_components.all.return_value = []
    return d


def _session(customer_id=None):
    d = {}
    if customer_id is not None:
        d["customer_id"] = customer_id
    sess = MagicMock()
    sess.get = lambda key, default=None: d.get(key, default)
    sess.__setitem__ = lambda s, k, v: d.__setitem__(k, v)
    sess.pop = lambda key, default=None: d.pop(key, default)
    return sess


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


class PlaceOrderViewOptionGroupTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, data, tenant=None, profile=None, session=None):
        req = self.factory.post("/api/place-order/", data, format="json")
        req.tenant = tenant or _tenant()
        req.user = _anon()
        req.session = session or _session()
        return req

    def _make_option(self, oid, dish_slug, price_delta="0.00"):
        opt = MagicMock()
        opt.id = oid
        opt.name = f"opt-{oid}"
        opt.price_delta = Decimal(price_delta)
        opt.dish = MagicMock()
        opt.dish.slug = dish_slug
        return opt

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_missing_required_group_rejects_400(self, profile_mock, dish_mock):
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _mock_dish_with_group(min_select=1, max_select=1, option_ids=(10, 11))
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(payload)
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "option_selection_invalid")
        self.assertEqual(resp.data["reason"], "min_select")

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_over_max_group_rejects_400(self, profile_mock, dish_mock):
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _mock_dish_with_group(min_select=0, max_select=1, option_ids=(10, 11))
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        opt10 = self._make_option(10, "burger")
        opt11 = self._make_option(11, "burger")

        payload = {"items": [{"slug": "burger", "qty": 1, "option_ids": [10, 11]}], "fulfillment_type": "pickup"}
        req = self._post(payload)
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value.select_related.return_value = [opt10, opt11]
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "option_selection_invalid")
        self.assertEqual(resp.data["reason"], "max_select")

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_valid_selection_passes_group_gate(self, profile_mock, dish_mock, promo_mock):
        """A submission that satisfies min/max_select must NOT be rejected as
        option_selection_invalid — it proceeds to order creation."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _mock_dish_with_group(min_select=1, max_select=1, option_ids=(10, 11))
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        opt10 = self._make_option(10, "burger")

        payload = {"items": [{"slug": "burger", "qty": 1, "option_ids": [10]}], "fulfillment_type": "pickup"}
        req = self._post(payload)

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value.select_related.return_value = [opt10]
            with patch("menu.views.Order.objects") as order_mock:
                mock_order = MagicMock()
                mock_order.order_number = "GRP001"
                mock_order.status = "pending"
                mock_order.total = Decimal("10.00")
                mock_order.delivery_fee = Decimal("0")
                mock_order.currency = "MAD"
                mock_order.estimated_ready_minutes = None
                order_mock.create.return_value = mock_order
                with patch("menu.views.OrderItem.objects"):
                    with patch("menu.views._generate_order_number", return_value="GRP001"):
                        with patch("menu.views.transaction") as tx_mock:
                            cm = MagicMock()
                            cm.__enter__ = MagicMock(return_value=None)
                            cm.__exit__ = MagicMock(return_value=False)
                            tx_mock.atomic.return_value = cm
                            resp = self.view(req)

        self.assertNotEqual(resp.data.get("code"), "option_selection_invalid")
        self.assertNotEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ═════════════════════════════════════════════════════════════════════════════
# MarketplacePlaceOrderView — POST /api/marketplace/order/
# ═════════════════════════════════════════════════════════════════════════════

def _noop_sc():
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


def _mkt_dish(slug="burger", name="Burger", price="10.00", currency="USD",
              min_select=1, max_select=1, option_ids=(10, 11)):
    d = SimpleNamespace()
    d.slug = slug
    d.name = name
    d.price = Decimal(price)
    d.currency = currency
    d.combo_components = MagicMock()
    d.combo_components.all.return_value = []
    d.category = SimpleNamespace(course=0)
    group = MagicMock()
    group.id = 1
    group.name = "Size"
    group.min_select = min_select
    group.max_select = max_select
    _opts = []
    for oid in option_ids:
        o = MagicMock()
        o.id = oid
        _opts.append(o)
    group.options.all.return_value = _opts
    d.option_groups = MagicMock()
    d.option_groups.all.return_value = [group]
    return d


def _mkt_option(oid, dish_slug, price_delta="0.00", name="opt"):
    opt = SimpleNamespace()
    opt.id = oid
    opt.name = name
    opt.price_delta = Decimal(price_delta)
    opt.dish = SimpleNamespace(slug=dish_slug)
    return opt


class MarketplacePlaceOrderOptionGroupTests(SimpleTestCase):
    """Drives MarketplacePlaceOrderView (pickup) far enough to reach the per-item
    option-group gate. A sentinel is raised right AFTER the item loop (the promo
    query) so a request that PASSES the gate surfaces as 500 server_error rather
    than 400 — same harness pattern as tests/test_ops5f_accounts.py."""

    def setUp(self):
        from accounts.views import MarketplacePlaceOrderView
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _drive(self, *, dish, options, item):
        import menu.models as mm

        tenant = SimpleNamespace(
            slug="bistro", name="Bistro", schema_name="bistro",
            id=1, lifecycle_status="active",
        )

        dish_qs = MagicMock()
        dish_qs.select_related.return_value.prefetch_related.return_value = [dish]
        opt_qs = MagicMock()
        opt_qs.select_related.return_value = options

        profile = MagicMock()
        profile.is_menu_published = True
        profile.platform_delivery_enabled = False
        prof_qs = MagicMock()
        prof_qs.first.return_value = profile

        from tenancy.models import Tenant as _RealTenant

        _ProfileStub = MagicMock()
        _ProfileStub.objects.filter.return_value = prof_qs

        with patch("tenancy.models.Tenant") as MockTenant, \
             patch("django_tenants.utils.schema_context", _noop_sc()), \
             patch("tenancy.models.Profile", _ProfileStub), \
             patch.object(mm.Dish, "objects") as MockDishObjs, \
             patch.object(mm.DishOption, "objects") as MockDOObjs, \
             patch.object(mm.Order, "objects") as MockOrderObjs, \
             patch.object(mm.Promotion, "objects") as MockPromoObjs, \
             patch("accounts.views._compute_is_open_now", return_value=True), \
             patch("menu.pricing.get_active_happy_hours", return_value=[]), \
             patch("menu.pricing.effective_unit_price",
                   side_effect=lambda d, hh: (d.price, None)), \
             patch("menu.views._profile_now", return_value=None):
            MockTenant.LifecycleStatus = _RealTenant.LifecycleStatus
            MockTenant.DoesNotExist = _RealTenant.DoesNotExist
            tenant.lifecycle_status = _RealTenant.LifecycleStatus.ACTIVE
            MockTenant.objects.get.return_value = tenant
            MockDishObjs.filter.return_value = dish_qs
            MockDOObjs.filter.return_value = opt_qs
            MockOrderObjs.filter.return_value.first.return_value = None
            MockPromoObjs.filter.side_effect = RuntimeError("reached-promo")

            req = self.factory.post("/api/marketplace/order/", {
                "restaurant": "bistro",
                "fulfillment_type": "pickup",
                "items": [item],
            }, format="json")
            req.user = _anon()
            req.session = {}
            return self.view(req)

    def test_missing_required_group_rejects_400(self):
        dish = _mkt_dish(slug="burger", min_select=1, max_select=1, option_ids=(10, 11))
        resp = self._drive(dish=dish, options=[], item={"slug": "burger", "qty": 1})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "option_selection_invalid")
        self.assertEqual(resp.data["reason"], "min_select")

    def test_over_max_group_rejects_400(self):
        dish = _mkt_dish(slug="burger", min_select=0, max_select=1, option_ids=(10, 11))
        opt10 = _mkt_option(10, "burger")
        opt11 = _mkt_option(11, "burger")
        resp = self._drive(
            dish=dish, options=[opt10, opt11],
            item={"slug": "burger", "qty": 1, "option_ids": [10, 11]},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "option_selection_invalid")
        self.assertEqual(resp.data["reason"], "max_select")

    def test_valid_selection_passes_group_gate(self):
        """A submission that satisfies min/max_select proceeds past the item loop
        (surfaced here as the post-loop sentinel, i.e. 500 — not 400)."""
        dish = _mkt_dish(slug="burger", min_select=1, max_select=1, option_ids=(10, 11))
        opt10 = _mkt_option(10, "burger")
        resp = self._drive(
            dish=dish, options=[opt10],
            item={"slug": "burger", "qty": 1, "option_ids": [10]},
        )
        self.assertNotEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
