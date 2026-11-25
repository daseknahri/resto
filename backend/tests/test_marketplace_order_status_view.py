"""Tests for MarketplaceOrderStatusView — GET /api/marketplace/order/<n>/?restaurant=<slug>.

R P2-1: the owner body items expose is_comped (like the direct status payload),
so the marketplace receipt can render a comped line as contributing 0.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import MarketplaceOrderStatusView


def _make_item(**kw):
    item = MagicMock()
    item.dish_slug = kw.get("dish_slug", "pizza")
    item.dish_name = kw.get("dish_name", "Pizza")
    item.qty = kw.get("qty", 1)
    item.unit_price = Decimal("10.00")
    item.subtotal = Decimal("10.00")
    item.options = []
    item.note = ""
    item.is_voided = kw.get("is_voided", False)
    item.is_comped = kw.get("is_comped", False)
    item.combo_components = []
    return item


def _make_order(items):
    order = MagicMock()
    order.order_number = "ORD-1"
    order.status = "pending"
    order.payment_status = "unpaid"
    order.fulfillment_type = "pickup"
    order.total = Decimal("20.00")
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.wallet_amount_paid = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.redeemed_loyalty_points = 0
    order.points_earned = 0
    order.promotion_discount = Decimal("0")
    order.applied_promotion_name = ""
    order.currency = "MAD"
    order.estimated_ready_minutes = None
    order.estimated_ready_at = None
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-05-15T12:00:00+00:00"
    order.scheduled_for = None
    order.owner_note = ""
    order.rating = None
    order.delivery_code = ""
    items_qs = MagicMock()
    items_qs.all.return_value = items
    order.items = items_qs
    return order


class MarketplaceOrderStatusViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate the status throttle
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderStatusView.as_view()
        # Tenant lookup + schema_context + Order query + ownership + cancel gate.
        self._patchers = [
            patch("tenancy.models.Tenant.objects"),
            patch("django_tenants.utils.schema_context"),
            patch("menu.models.Order"),
            patch("accounts.views.IsOrderOwner"),
            patch("menu.views._customer_can_cancel", return_value=False),
        ]
        (self._tenant_om, self._sc, self._order_cls, self._owns_cls, _ccc) = (
            p.start() for p in self._patchers
        )
        for p in self._patchers:
            self.addCleanup(p.stop)
        tenant = SimpleNamespace(
            schema_name="test_schema", name="Test Resto",
            profile=SimpleNamespace(phone="+212600000000", receipt_message=""),
        )
        self._tenant_om.get.return_value = tenant

    def _get(self, order_number="ORD-1", restaurant="test-resto"):
        req = self.factory.get(
            f"/api/marketplace/order/{order_number}/?restaurant={restaurant}")
        return self.view(req, order_number=order_number)

    def _set_order(self, order):
        (self._order_cls.objects.filter.return_value.prefetch_related.return_value
            .select_related.return_value.first.return_value) = order

    def test_owner_body_items_expose_is_comped(self):
        """R P2-1: the owner body carries is_comped per item (comped True, normal False)."""
        self._owns_cls.return_value.has_object_permission.return_value = True
        self._set_order(_make_order(
            [_make_item(is_comped=True), _make_item(is_comped=False)]))
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = resp.data["items"]
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["is_comped"])
        self.assertFalse(items[1]["is_comped"])
        self.assertIn("is_voided", items[0])

    def test_non_owner_gets_minimal_body_without_items(self):
        self._owns_cls.return_value.has_object_permission.return_value = False
        self._set_order(_make_order([_make_item(is_comped=True)]))
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("items", resp.data)
        self.assertEqual(resp.data["status"], "pending")
