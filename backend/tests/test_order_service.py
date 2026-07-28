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
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.models import Order
from menu.order_service import compute_order_delivery_fee, compute_order_tip, resolve_prepay_and_wallet


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
