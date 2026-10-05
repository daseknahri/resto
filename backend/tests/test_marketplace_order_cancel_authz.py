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


class MarketplaceOrderCancelLockedRecheckTests(SimpleTestCase):
    """Regression (TOCTOU, same class as the void/comp fix #442): cancellability is gated on
    the UNLOCKED row, so an owner advancing the order to PREPARING in the window before the
    select_for_update lock must NOT be cancelled + refunded. The REAL _customer_can_cancel is
    exercised (deliberately not patched) against the LOCKED row."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # MarketplaceOrderStatusThrottle counts per-actor
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderCancelView.as_view()

    def _cancel(self, *, pre_status, locked_status):
        customer = Customer(id=42)
        order = MagicMock()
        order.customer_id = 42  # == customer.id → IsOrderOwner passes
        order.status = pre_status  # the UNLOCKED read at the top of post()
        order.fulfillment_type = Order.FulfillmentType.PICKUP
        locked = MagicMock()
        locked.status = locked_status  # the row re-read UNDER select_for_update
        locked.fulfillment_type = Order.FulfillmentType.PICKUP

        req = self.factory.post(
            "/api/marketplace/order/ORD-1/cancel/", {"restaurant": "tacos"}, format="json"
        )
        req.session = {"customer_id": 42}
        force_authenticate(req, user=customer)

        tenant = SimpleNamespace(id=7, schema_name="tacos", slug="tacos")
        Tenant = MagicMock()
        Tenant.objects.get.return_value = tenant
        OrderObjs = MagicMock()
        OrderObjs.filter.return_value.first.return_value = order
        (OrderObjs.select_for_update.return_value
            .filter.return_value.first.return_value) = locked

        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.models.Order.objects", OrderObjs), \
             patch("django_tenants.utils.schema_context", return_value=_noop_cm()), \
             patch("django.db.transaction.atomic", return_value=_noop_cm()), \
             patch("django.db.transaction.set_rollback") as rollback, \
             patch("menu.views._refund_wallet_for_cancelled_order") as refund, \
             patch("menu.views._reverse_loyalty_for_cancelled_order") as revloy, \
             patch("menu.views._restock_cancelled_order") as restock, \
             patch("menu.views._broadcast_order_change") as broadcast, \
             patch("accounts.delivery_service.cancel_delivery_job_for_order") as cancel_job:
            resp = self.view(req, order_number="ORD-1")
        return SimpleNamespace(
            resp=resp, rollback=rollback, refund=refund, revloy=revloy, restock=restock,
            broadcast=broadcast, cancel_job=cancel_job, locked=locked,
        )

    def test_order_advanced_to_preparing_under_the_lock_is_refused(self):
        for locked_status in (
            Order.Status.PREPARING,
            Order.Status.READY,
            Order.Status.OUT_FOR_DELIVERY,
        ):
            with self.subTest(locked_status=locked_status):
                r = self._cancel(pre_status=Order.Status.PENDING, locked_status=locked_status)
                self.assertEqual(r.resp.status_code, 409)
                self.assertEqual(r.resp.data["code"], "cancel_too_late")
                r.rollback.assert_called_once_with(True)
                self.assertEqual(r.locked.status, locked_status)  # never flipped to CANCELLED
                r.refund.assert_not_called()
                r.revloy.assert_not_called()
                r.restock.assert_not_called()
                r.broadcast.assert_not_called()
                r.cancel_job.assert_not_called()

    def test_still_cancellable_under_the_lock_proceeds(self):
        r = self._cancel(pre_status=Order.Status.PENDING, locked_status=Order.Status.CONFIRMED)
        self.assertEqual(r.resp.status_code, 200)
        r.rollback.assert_not_called()
        self.assertEqual(r.locked.status, Order.Status.CANCELLED)
        r.refund.assert_called_once()
        r.restock.assert_called_once()

    def test_peer_cancelled_under_the_lock_is_the_idempotent_replay_not_a_409(self):
        r = self._cancel(pre_status=Order.Status.PENDING, locked_status=Order.Status.CANCELLED)
        self.assertEqual(r.resp.status_code, 200)
        r.rollback.assert_not_called()
        r.refund.assert_called_once()   # keyed wallet credit replays
        r.restock.assert_not_called()   # non-idempotent helper does NOT re-run


class MarketplaceOrderCancelRefundTenantScopingTests(SimpleTestCase):
    """Regression: the marketplace cancel path must forward the OWNING tenant's id to the
    wallet-refund helper.

    The refund WalletTransaction lives in the shared/public schema, so it is only tagged to
    a tenant if the caller passes tenant_id. The bug called _refund(order) with no tenant_id,
    so the refund row was attributed to tenant_id=None and silently dropped from that tenant's
    per-tenant refund reports (the Z-report/refund query filters on tenant_id). Every sibling
    caller in menu/views.py already forwards it. This locks the marketplace-side view to the
    same contract.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # MarketplaceOrderStatusThrottle counts per-actor
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderCancelView.as_view()

    def test_cancel_forwards_owning_tenant_id_to_refund(self):
        customer = Customer(id=42)
        order = MagicMock()
        order.customer_id = 42  # == customer.id → IsOrderOwner passes
        order.status = Order.Status.PENDING  # cancellable; not the idempotent-cancelled 200

        req = self.factory.post(
            "/api/marketplace/order/ORD-1/cancel/", {"restaurant": "tacos"}, format="json"
        )
        req.session = {"customer_id": 42}
        force_authenticate(req, user=customer)

        tenant = SimpleNamespace(id=7, schema_name="tacos", slug="tacos")
        Tenant = MagicMock()
        Tenant.objects.get.return_value = tenant
        OrderObjs = MagicMock()
        OrderObjs.filter.return_value.first.return_value = order
        # The view now re-loads the order UNDER select_for_update inside the atomic block
        # (concurrency hardening) and runs the refund against THAT locked row. Point the
        # lock at the same order so the tenant-scoping assertion below still targets it.
        (OrderObjs.select_for_update.return_value
            .filter.return_value.first.return_value) = order

        # The cancel helpers are imported inside the view from menu.views at call time, so
        # patching them there intercepts the aliased imports. _customer_can_cancel is forced
        # True so the flow reaches the atomic block; the other side-effects are no-ops.
        # cancel_delivery_job_for_order is the best-effort post-commit driver stand-down.
        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.models.Order.objects", OrderObjs), \
             patch("django_tenants.utils.schema_context", return_value=_noop_cm()), \
             patch("django.db.transaction.atomic", return_value=_noop_cm()), \
             patch("menu.views._customer_can_cancel", return_value=True), \
             patch("menu.views._refund_wallet_for_cancelled_order") as mock_refund, \
             patch("menu.views._reverse_loyalty_for_cancelled_order"), \
             patch("menu.views._restock_cancelled_order"), \
             patch("menu.views._broadcast_order_change"), \
             patch("accounts.delivery_service.cancel_delivery_job_for_order"):
            resp = self.view(req, order_number="ORD-1")

        self.assertEqual(resp.status_code, 200)
        # The fix: tenant.id (7) is forwarded so the refund row is tenant-scoped, rather than
        # attributed to tenant_id=None and dropped from this tenant's refund reporting.
        mock_refund.assert_called_once_with(order, tenant_id=7)
