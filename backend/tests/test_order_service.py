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
from menu.order_service import compute_order_delivery_fee


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
