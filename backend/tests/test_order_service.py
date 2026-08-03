"""RISK STRUCT-1: menu.order_service.compute_order_delivery_fee (first OrderService seam).

Behavior-preservation tests for the delivery-fee sub-phase extracted verbatim from
PlaceOrderView.post. Mock-based (SimpleTestCase, no DB): the tenancy pricing/routing helpers the
service delegates to are patched at their origin (the service imports them function-locally, so
origin-patching intercepts the call), pinning the extracted control flow without a database.

This branch had NO through-the-view characterization test before extraction — these are the new
coverage the STRUCT-1 scout called for alongside proving the seam is inert.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from menu.models import Order
from menu.order_service import (
    compute_order_delivery_fee,
    compute_order_tip,
    deplete_ingredients,
    deplete_stock,
    price_line_options,
    resolve_available_dishes,
    resolve_option_map,
    resolve_prepay_and_wallet,
)


class ComputeOrderDeliveryFeeTests(SimpleTestCase):
    def _profile(self, lat=33.5, lng=-7.6):
        return SimpleNamespace(lat=lat, lng=lng)

    def test_non_delivery_returns_zero_and_computes_nothing(self):
        # Pickup/dine-in: no fee, and the pricing/routing helpers must never be called.
        with patch("tenancy.delivery_pricing.compute_delivery_fee") as m_fee, \
             patch("tenancy.routing.road_distance_km") as m_dist:
            result = compute_order_delivery_fee(
                self._profile(), fulfillment_type=Order.FulfillmentType.PICKUP,
                food_subtotal=Decimal("50.00"), delivery_lat=33.6, delivery_lng=-7.5,
            )
        self.assertEqual(result, (Decimal("0"), None, None))
        m_fee.assert_not_called()
        m_dist.assert_not_called()

    def test_delivery_valid_coords_uses_road_distance(self):
        profile = self._profile()
        with patch("tenancy.delivery_pricing.valid_coord", return_value=True), \
             patch("tenancy.routing.road_distance_km", return_value=4.2) as m_dist, \
             patch("tenancy.delivery_pricing.compute_delivery_fee",
                   return_value={"out_of_range": False, "fee": Decimal("12.00")}) as m_fee:
            fee, dist, err = compute_order_delivery_fee(
                profile, fulfillment_type=Order.FulfillmentType.DELIVERY,
                food_subtotal=Decimal("50.00"), delivery_lat=33.6, delivery_lng=-7.5,
            )
        self.assertEqual((fee, dist, err), (Decimal("12.00"), 4.2, None))
        m_dist.assert_called_once_with(profile.lat, profile.lng, 33.6, -7.5)
        m_fee.assert_called_once_with(profile, distance_km=4.2, food_subtotal=Decimal("50.00"))

    def test_delivery_invalid_coords_falls_back_to_flat_fee(self):
        # Missing / (0,0) / out-of-range coord → distance unknown → flat fallback, never a
        # false "outside area". road_distance_km must NOT be called.
        profile = self._profile()
        with patch("tenancy.delivery_pricing.valid_coord", return_value=False), \
             patch("tenancy.routing.road_distance_km") as m_dist, \
             patch("tenancy.delivery_pricing.compute_delivery_fee",
                   return_value={"out_of_range": False, "fee": Decimal("15.00")}) as m_fee:
            fee, dist, err = compute_order_delivery_fee(
                profile, fulfillment_type=Order.FulfillmentType.DELIVERY,
                food_subtotal=Decimal("50.00"), delivery_lat=0, delivery_lng=0,
            )
        self.assertEqual((fee, dist, err), (Decimal("15.00"), None, None))
        m_dist.assert_not_called()
        m_fee.assert_called_once_with(profile, distance_km=None, food_subtotal=Decimal("50.00"))

    def test_delivery_out_of_range_returns_error_code(self):
        profile = self._profile()
        with patch("tenancy.delivery_pricing.valid_coord", return_value=True), \
             patch("tenancy.routing.road_distance_km", return_value=25.0), \
             patch("tenancy.delivery_pricing.compute_delivery_fee",
                   return_value={"out_of_range": True, "fee": Decimal("0")}):
            fee, dist, err = compute_order_delivery_fee(
                profile, fulfillment_type=Order.FulfillmentType.DELIVERY,
                food_subtotal=Decimal("50.00"), delivery_lat=34.9, delivery_lng=-9.0,
            )
        self.assertEqual(err, "delivery_out_of_range")
        self.assertEqual(dist, 25.0)
        self.assertEqual(fee, Decimal("0"))


class ComputeOrderTipTests(SimpleTestCase):
    """RISK STRUCT-1 slice 2: gratuity parse/clamp, byte-identical to the former inline block."""

    def test_valid_tip_below_cap_returned(self):
        self.assertEqual(compute_order_tip("5.00", Decimal("50.00")), Decimal("5.00"))
        self.assertEqual(compute_order_tip(5, Decimal("50.00")), Decimal("5.00"))

    def test_over_precision_is_quantized(self):
        self.assertEqual(compute_order_tip("5.017", Decimal("50.00")), Decimal("5.02"))

    def test_tip_capped_at_food_subtotal(self):
        # fat-finger guard: tip > subtotal → clamped to subtotal
        self.assertEqual(compute_order_tip("999.00", Decimal("40.00")), Decimal("40.00"))

    def test_negative_tip_becomes_zero(self):
        self.assertEqual(compute_order_tip("-5.00", Decimal("50.00")), Decimal("0"))

    def test_non_numeric_becomes_zero(self):
        for bad in ("abc", "5,00", [1, 2], None):
            self.assertEqual(compute_order_tip(bad, Decimal("50.00")), Decimal("0"))

    def test_zero_subtotal_does_not_cap(self):
        # matches the original `if _food_subtotal > 0 and ...` — no cap when subtotal is 0
        self.assertEqual(compute_order_tip("100.00", Decimal("0")), Decimal("100.00"))


class ResolvePrepayAndWalletTests(SimpleTestCase):
    """RISK STRUCT-1 slice 3: prepay/COD/wallet money-gate, byte-identical to the inline block.

    `menu.views._cod_eligible` is patched (the service calls it function-locally to keep that patch
    target valid). No DB — customers/users are lightweight namespaces.
    """

    def _customer(self, balance="100.00", cid=1):
        return SimpleNamespace(id=cid, wallet_balance=Decimal(balance))

    def _call(self, **kw):
        base = dict(
            user=SimpleNamespace(is_authenticated=True, role=None),
            linked_customer=self._customer(), profile=SimpleNamespace(),
            fulfillment_type=Order.FulfillmentType.PICKUP, total=Decimal("50.00"),
            is_scheduled=False, payment_method=None, use_wallet_flag=None,
        )
        base.update(kw)
        return resolve_prepay_and_wallet(**base)

    def test_staff_order_exempt(self):
        from accounts.models import User
        rp, cod, uw, wd, err = self._call(user=SimpleNamespace(is_authenticated=True, role=User.Roles.TENANT_STAFF))
        self.assertFalse(rp)
        self.assertIsNone(err)
        self.assertFalse(cod)

    def test_customer_pickup_no_linked_customer_403(self):
        rp, cod, uw, wd, err = self._call(linked_customer=None)
        self.assertIsNotNone(err)
        self.assertEqual(err[1], 403)
        self.assertEqual(err[0]["code"], "auth_required")

    def test_cash_cod_eligible_becomes_cod_no_wallet(self):
        with patch("menu.views._cod_eligible", return_value=True):
            rp, cod, uw, wd, err = self._call(payment_method="cash")
        self.assertIsNone(err)
        self.assertTrue(cod)
        self.assertFalse(uw)
        self.assertEqual(wd, Decimal("0"))

    def test_cash_not_cod_insufficient_wallet_402(self):
        with patch("menu.views._cod_eligible", return_value=False):
            rp, cod, uw, wd, err = self._call(payment_method="cash", linked_customer=self._customer("30.00"))
        self.assertIsNotNone(err)
        self.assertEqual(err[1], 402)
        self.assertEqual(err[0]["code"], "wallet_insufficient")
        self.assertEqual(err[0]["amount_due"], "50.00")

    def test_wallet_covers_uses_wallet(self):
        rp, cod, uw, wd, err = self._call(linked_customer=self._customer("100.00"))
        self.assertIsNone(err)
        self.assertTrue(rp)
        self.assertTrue(uw)
        self.assertEqual(wd, Decimal("50.00"))  # min(100, 50)

    def test_dine_in_with_use_wallet_flag(self):
        # non-pickup/delivery → not prepay-required, but an explicit use_wallet still deducts
        rp, cod, uw, wd, err = self._call(fulfillment_type="table", use_wallet_flag=True, total=Decimal("20.00"))
        self.assertFalse(rp)
        self.assertTrue(uw)
        self.assertEqual(wd, Decimal("20.00"))

    def test_zero_deduction_disables_wallet(self):
        rp, cod, uw, wd, err = self._call(fulfillment_type="table", use_wallet_flag=True, total=Decimal("0"))
        self.assertFalse(uw)
        self.assertEqual(wd, Decimal("0"))


class ResolveItemsTests(SimpleTestCase):
    """RISK STRUCT-1 slice: resolve_available_dishes / resolve_option_map — the item-resolution
    queries shared verbatim by PlaceOrderView and MarketplacePlaceOrderView. Mock-based: the models
    are patched at their order_service module binding, so no DB is needed."""

    @patch("menu.models.Dish")
    def test_resolve_available_dishes_maps_by_slug_with_availability_gate(self, mock_dish):
        d1 = MagicMock(slug="burger")
        d2 = MagicMock(slug="fries")
        (
            mock_dish.objects.filter.return_value
            .select_related.return_value
            .prefetch_related.return_value
        ) = [d1, d2]
        result = resolve_available_dishes(["burger", "fries", "gone"])
        self.assertEqual(set(result.keys()), {"burger", "fries"})
        self.assertIs(result["burger"], d1)
        # The availability gate is applied exactly (published + available, published & non-disabled
        # category) — the guard against ordering an unpublished/sold-out/hidden dish.
        kwargs = mock_dish.objects.filter.call_args.kwargs
        self.assertEqual(kwargs["slug__in"], ["burger", "fries", "gone"])
        self.assertTrue(kwargs["is_published"])
        self.assertTrue(kwargs["is_available"])
        self.assertTrue(kwargs["category__is_published"])
        self.assertFalse(kwargs["category__is_temporarily_disabled"])

    @patch("menu.models.DishOption")
    def test_resolve_option_map_empty_short_circuits(self, mock_do):
        self.assertEqual(resolve_option_map([]), {})
        mock_do.objects.filter.assert_not_called()

    @patch("menu.models.DishOption")
    def test_resolve_option_map_maps_by_id_and_select_relates_dish(self, mock_do):
        o1 = MagicMock(id=5)
        o2 = MagicMock(id=7)
        mock_do.objects.filter.return_value.select_related.return_value = [o1, o2]
        result = resolve_option_map([5, 7])
        self.assertEqual(set(result.keys()), {5, 7})
        self.assertIs(result[5], o1)
        mock_do.objects.filter.assert_called_once_with(id__in=[5, 7])
        # select_related("dish") is the OPS-5f price-smuggling guard — assert it's applied.
        mock_do.objects.filter.return_value.select_related.assert_called_once_with("dish")


class PriceLineOptionsTests(SimpleTestCase):
    """RISK STRUCT-1 slice 2: price_line_options — OPS-5f option binding + B2 group-select +
    price_delta accumulation, shared verbatim by PlaceOrderView and MarketplacePlaceOrderView.
    `menu.views._validate_option_group_selections` is patched at origin (the helper imports it
    function-locally); no DB."""

    def _dish(self, slug="burger", name="Burger"):
        return SimpleNamespace(slug=slug, name=name)

    def _opt(self, oid, dish_slug, price_delta="0.00", name="opt"):
        return SimpleNamespace(
            id=oid, name=name, price_delta=Decimal(price_delta),
            dish=SimpleNamespace(slug=dish_slug),
        )

    def test_empty_options_returns_base_price(self):
        with patch("menu.views._validate_option_group_selections", return_value=None):
            price, snaps, err = price_line_options(self._dish(), [], {}, Decimal("10.00"))
        self.assertIsNone(err)
        self.assertEqual(price, Decimal("10.00"))
        self.assertEqual(snaps, [])

    def test_bound_options_add_price_delta_in_order(self):
        dish = self._dish()
        o1 = self._opt(1, "burger", "1.50", "cheese")
        o2 = self._opt(2, "burger", "0.50", "bacon")
        with patch("menu.views._validate_option_group_selections", return_value=None):
            price, snaps, err = price_line_options(dish, [1, 2], {1: o1, 2: o2}, Decimal("10.00"))
        self.assertIsNone(err)
        self.assertEqual(price, Decimal("12.00"))
        self.assertEqual([s["id"] for s in snaps], [1, 2])
        self.assertEqual(snaps[0], {"id": 1, "name": "cheese", "price_delta": "1.50"})

    def test_foreign_option_rejected_stale_options(self):
        # OPS-5f: an option bound to a DIFFERENT dish is rejected before pricing — no negative
        # price_delta smuggled onto a cheap dish, and group-select is never reached.
        dish = self._dish(slug="burger")
        foreign = self._opt(9, "pizza", "-9.00")
        with patch("menu.views._validate_option_group_selections", return_value=None) as vogs:
            price, snaps, err = price_line_options(dish, [9], {9: foreign}, Decimal("10.00"))
        self.assertIsNone(price)
        self.assertEqual(err["code"], "stale_options")
        self.assertEqual(err["dish_slug"], "burger")
        self.assertIn(9, err["invalid_option_ids"])
        vogs.assert_not_called()

    def test_unknown_option_rejected_stale_options(self):
        with patch("menu.views._validate_option_group_selections", return_value=None):
            price, snaps, err = price_line_options(self._dish(), [5], {}, Decimal("10.00"))
        self.assertIsNone(price)
        self.assertEqual(err["code"], "stale_options")
        self.assertIn(5, err["invalid_option_ids"])

    def test_group_select_violation_returned(self):
        dish = self._dish()
        o1 = self._opt(1, "burger", "1.00")
        payload = {"code": "option_selection_invalid", "reason": "min_select"}
        with patch("menu.views._validate_option_group_selections", return_value=payload):
            price, snaps, err = price_line_options(dish, [1], {1: o1}, Decimal("10.00"))
        self.assertIsNone(price)
        self.assertIs(err, payload)

    def test_group_select_receives_bound_ids(self):
        dish = self._dish()
        o1 = self._opt(1, "burger")
        o2 = self._opt(2, "burger")
        with patch("menu.views._validate_option_group_selections", return_value=None) as vogs:
            price_line_options(dish, [1, 2], {1: o1, 2: o2}, Decimal("10.00"))
        vogs.assert_called_once_with(dish, [1, 2])


class DepleteStockTests(SimpleTestCase):
    """RISK STRUCT-1 slice 3: deplete_stock — dish + component validate/decrement over the
    caller's select_for_update-locked rows. Returns the first sold-out slug/name (the caller
    raises its own _OutOfStock); a decrement to zero flips is_available + stock_auto_zeroed.
    menu.models.Dish patched; no DB."""

    @patch("menu.models.Dish")
    def test_sufficient_stock_decrements_and_returns_none(self, mock_dish):
        locked = {1: SimpleNamespace(pk=1, stock_qty=5)}
        result = deplete_stock(locked, [(1, 2)], {1: "burger"}, {}, {})
        self.assertIsNone(result)
        mock_dish.objects.filter.assert_called_once_with(pk=1)
        mock_dish.objects.filter.return_value.update.assert_called_once_with(stock_qty=3)

    @patch("menu.models.Dish")
    def test_dish_short_returns_slug_before_any_decrement(self, mock_dish):
        # Validation runs for every dish BEFORE any decrement — a short dish returns its slug
        # and no .update() fires (the caller raises → rollback).
        locked = {1: SimpleNamespace(pk=1, stock_qty=1)}
        result = deplete_stock(locked, [(1, 5)], {1: "burger"}, {}, {})
        self.assertEqual(result, "burger")
        mock_dish.objects.filter.assert_not_called()

    @patch("menu.models.Dish")
    def test_decrement_to_zero_sets_soldout_flags(self, mock_dish):
        locked = {1: SimpleNamespace(pk=1, stock_qty=2)}
        deplete_stock(locked, [(1, 2)], {1: "burger"}, {}, {})
        mock_dish.objects.filter.return_value.update.assert_called_once_with(
            stock_qty=0, is_available=False, stock_auto_zeroed=True
        )

    @patch("menu.models.Dish")
    def test_component_short_returns_name_after_dish_decrement(self, mock_dish):
        # Dish ok (decrements), component short → returns the component NAME. Matches the inline
        # order (dish decremented, then component short), which the caller's raise rolls back.
        locked = {1: SimpleNamespace(pk=1, stock_qty=10), 2: SimpleNamespace(pk=2, stock_qty=1)}
        result = deplete_stock(locked, [(1, 1)], {1: "combo"}, {2: 3}, {2: "patty"})
        self.assertEqual(result, "patty")
        mock_dish.objects.filter.assert_called_once_with(pk=1)
        mock_dish.objects.filter.return_value.update.assert_called_once_with(stock_qty=9)

    @patch("menu.models.Dish")
    def test_untracked_stock_qty_none_is_skipped(self, mock_dish):
        # stock_qty None (unlimited) → never validated or decremented.
        locked = {1: SimpleNamespace(pk=1, stock_qty=None)}
        result = deplete_stock(locked, [(1, 99)], {1: "burger"}, {}, {})
        self.assertIsNone(result)
        mock_dish.objects.filter.assert_not_called()


class DepleteIngredientsTests(SimpleTestCase):
    """RISK STRUCT-1 slice 3b: deplete_ingredients — recipe BOM → F() ingredient decrement.
    menu.models.Ingredient + RecipeLine patched; F() stays a real lazy expression (no DB)."""

    def _dishes_map(self, **slug_pk):
        return {slug: SimpleNamespace(pk=pk) for slug, pk in slug_pk.items()}

    @patch("menu.models.RecipeLine")
    @patch("menu.models.Ingredient")
    def test_depletes_by_recipe_qty_times_order_qty(self, mock_ing, mock_rl):
        rl = SimpleNamespace(dish_id=1, ingredient_id=10, quantity=Decimal("2"))
        mock_rl.objects.filter.return_value.only.return_value = [rl]
        deplete_ingredients([{"dish_slug": "burger", "qty": 3}], self._dishes_map(burger=1))
        mock_ing.objects.filter.assert_called_once_with(pk=10)
        self.assertIn("stock_quantity", mock_ing.objects.filter.return_value.update.call_args.kwargs)

    @patch("menu.models.RecipeLine")
    @patch("menu.models.Ingredient")
    def test_same_ingredient_across_dishes_aggregated(self, mock_ing, mock_rl):
        rls = [
            SimpleNamespace(dish_id=1, ingredient_id=10, quantity=Decimal("1")),
            SimpleNamespace(dish_id=2, ingredient_id=10, quantity=Decimal("1")),
        ]
        mock_rl.objects.filter.return_value.only.return_value = rls
        deplete_ingredients(
            [{"dish_slug": "burger", "qty": 1}, {"dish_slug": "wrap", "qty": 1}],
            self._dishes_map(burger=1, wrap=2),
        )
        mock_ing.objects.filter.assert_called_once_with(pk=10)

    @patch("menu.models.RecipeLine")
    @patch("menu.models.Ingredient")
    def test_no_recipe_lines_no_update(self, mock_ing, mock_rl):
        mock_rl.objects.filter.return_value.only.return_value = []
        deplete_ingredients([{"dish_slug": "burger", "qty": 1}], self._dishes_map(burger=1))
        mock_ing.objects.filter.assert_not_called()

    @patch("menu.models.RecipeLine")
    @patch("menu.models.Ingredient")
    def test_empty_order_short_circuits(self, mock_ing, mock_rl):
        deplete_ingredients([], {})
        mock_rl.objects.filter.assert_not_called()
        mock_ing.objects.filter.assert_not_called()

    @patch("menu.models.RecipeLine")
    @patch("menu.models.Ingredient")
    def test_non_int_pk_dish_skipped(self, mock_ing, mock_rl):
        # A dish whose pk isn't an int (e.g. an unsaved / mocked dish) is skipped, so the recipe
        # query never runs — this is the guard the storefront happy-hour mock tests rely on.
        dishes_map = {"burger": SimpleNamespace(pk=MagicMock())}
        deplete_ingredients([{"dish_slug": "burger", "qty": 1}], dishes_map)
        mock_rl.objects.filter.assert_not_called()
        mock_ing.objects.filter.assert_not_called()
