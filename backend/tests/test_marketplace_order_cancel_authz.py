"""RISK IDENTITY-1: MarketplaceOrderCancelView ownership gate.

The view used to compare `session["customer_id"]` to `order.customer_id` inline; it now
hydrates the customer onto request.user (CustomerSessionAuthentication) and gates on the
shared IsOrderOwner predicate, keeping the exact 403 {"code": "not_owner"} response. This
locks that the gate is actually invoked: a non-owner is refused, the owner passes it.

Mock-based (SimpleTestCase, no DB): Tenant, schema_context and the tenant-schema Order read
are patched; the owner path uses an already-CANCELLED order so it returns the idempotent 200
without exercising the refund/restock helpers.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import MarketplaceOrderCancelView
from menu.models import Order


def _noop_cm():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class MarketplaceOrderCancelAuthzTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # MarketplaceOrderStatusThrottle counts per-actor
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderCancelView.as_view()

    def _post(self, customer, order):
        req = self.factory.post(
            "/api/marketplace/order/ORD-1/cancel/", {"restaurant": "tacos"}, format="json"
        )
        req.session = {"customer_id": customer.id}
        force_authenticate(req, user=customer)

        tenant = SimpleNamespace(id=7, schema_name="tacos", slug="tacos")
        Tenant = MagicMock()
        Tenant.objects.get.return_value = tenant
        OrderObjs = MagicMock()
        OrderObjs.filter.return_value.first.return_value = order
        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.models.Order.objects", OrderObjs), \
             patch("django_tenants.utils.schema_context", return_value=_noop_cm()):
            return self.view(req, order_number="ORD-1")

    def _order(self, customer_id, status=Order.Status.CANCELLED):
        o = MagicMock()
        o.customer_id = customer_id
        o.status = status
        return o

    def test_non_owner_gets_403_not_owner(self):
        resp = self._post(Customer(id=99), self._order(customer_id=42))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data["code"], "not_owner")

    def test_owner_passes_gate(self):
        # Owner of an already-cancelled order → idempotent 200 (proves the gate let them through).
        resp = self._post(Customer(id=42), self._order(customer_id=42))
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_gets_403_not_owner(self):
        # No customer principal → IsOrderOwner fails closed → same not_owner response.
        req = self.factory.post(
            "/api/marketplace/order/ORD-1/cancel/", {"restaurant": "tacos"}, format="json"
        )
        req.session = {}
        tenant = SimpleNamespace(id=7, schema_name="tacos", slug="tacos")
        Tenant = MagicMock()
        Tenant.objects.get.return_value = tenant
        OrderObjs = MagicMock()
        OrderObjs.filter.return_value.first.return_value = self._order(customer_id=42)
        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.models.Order.objects", OrderObjs), \
             patch("django_tenants.utils.schema_context", return_value=_noop_cm()):
            resp = self.view(req, order_number="ORD-1")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data["code"], "not_owner")
