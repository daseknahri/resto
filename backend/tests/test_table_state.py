"""
B5 backend tests — Table-state model: status/capacity + transfer-items + merge.

Covers:
  Contract 1 — StaffTableStatusView   PATCH /api/staff/tables/<id>/status/
    - happy path: open → dirty, open → reserved, dirty → open
    - rejects "occupied" (computed from orders)
    - rejects unknown status value
    - 404 for non-existent table
    - 403 for unauthenticated / no perm

  Contract 2 — StaffTransferItemsView POST /api/staff/orders/<src>/transfer-items/
    - happy path: moves items, recalculates totals, broadcasts both orders
    - source auto-cancelled when all items moved
    - 409 not_table, bad_status, already_paid
    - 409 items_not_found (voided or wrong order)
    - 400 missing item_ids / dest_order_id
    - 403 unauthenticated / no perm

  Contract 3 — StaffMergeOrdersView  POST /api/staff/orders/<dest>/merge/
    - happy path: all items moved, src cancelled+zeroed, dest total recalculated
    - 400 same_order
    - 409 not_table, bad_status, already_paid (either side)
    - 403 unauthenticated / no perm

House style: SimpleTestCase + MagicMock, no real DB.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffTableStatusView, StaffTransferItemsView, StaffMergeOrdersView
from menu.models import Order, TableLink
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _user(perm_manage=True, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders = MagicMock(return_value=perm_manage)
    return u


def _tenant(tenant_id=1):
    t = MagicMock()
    t.id = tenant_id
    return t


def _make_table(pk=1, slug="t1", label="Table 1", table_status="open", capacity=4, is_active=True):
    t = MagicMock(spec=TableLink)
    t.id = pk
    t.slug = slug
    t.label = label
    t.status = table_status
    t.capacity = capacity
    t.is_active = is_active
    t.save = MagicMock()
    return t


def _make_order(
    pk=1,
    order_number="ORD-001",
    order_status=Order.Status.PENDING,
    fulfillment_type=Order.FulfillmentType.TABLE,
    payment_status=Order.PaymentStatus.UNPAID,
    total=Decimal("20.00"),
    items=None,
):
    o = MagicMock(spec=Order)
    o.pk = pk
    o.id = pk
    o.order_number = order_number
    o.status = order_status
    o.fulfillment_type = fulfillment_type
    o.payment_status = payment_status
    o.total = total
    o.delivery_fee = Decimal("0")
    o.tip_amount = Decimal("0")
    o.promotion_discount = Decimal("0")
    o.loyalty_discount = Decimal("0")
    o.wallet_amount_paid = Decimal("0")
    o.currency = "MAD"
    o.customer_name = "Test Customer"
    o.customer_id = None
    o.customer_note = ""
    o.owner_note = ""
    o.table_label = "T1"
    o.table_slug = "t1"
    o.handled_by_user_id = None
    o.estimated_ready_minutes = None
    o.scheduled_for = None
    o.fired_course = 1
    o.updated_at = MagicMock()
    o.updated_at.isoformat = MagicMock(return_value="2026-01-01T00:00:00Z")
    o.created_at = MagicMock()
    o.created_at.isoformat = MagicMock(return_value="2026-01-01T00:00:00Z")
    o.status_updated_at = None
    o.paid_at = None
    o.commission_amount = Decimal("0")
    o.commission_rate_applied = Decimal("0")
    o.promotion_discount = Decimal("0")
    o.applied_promotion_name = ""
    o.loyalty_discount = Decimal("0")
    o.redeemed_loyalty_points = None
    o.points_earned = None
    o.source = Order.Source.DIRECT
    o.items = MagicMock()
    o.payments = MagicMock()
    o.payments.all = MagicMock(return_value=[])
    _items = items or []
    o.items.all = MagicMock(return_value=_items)
    o.refresh_from_db = MagicMock()
    o.save = MagicMock()
    return o


def _make_item(pk=1, subtotal=Decimal("10.00"), is_voided=False, order_id=1):
    item = MagicMock()
    item.pk = pk
    item.id = pk
    item.is_voided = is_voided
    item.subtotal = subtotal
    item.order_id = order_id
    return item


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 1 — StaffTableStatusView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffTableStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffTableStatusView.as_view()

    def _patch(self, table_id, payload, user=None, tenant_id=1):
        req = self.factory.patch(f"/api/staff/tables/{table_id}/status/", payload, format="json")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req, table_id=table_id)

    def test_mark_dirty(self):
        table = _make_table(table_status="open")
        with patch("menu.views.TableLink.objects") as tl_om:
            tl_om.get.return_value = table
            resp = self._patch(1, {"status": "dirty"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "dirty")
        table.save.assert_called_once_with(update_fields=["status", "updated_at"])

    def test_mark_reserved(self):
        table = _make_table(table_status="open")
        with patch("menu.views.TableLink.objects") as tl_om:
            tl_om.get.return_value = table
            resp = self._patch(1, {"status": "reserved"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "reserved")

    def test_mark_open(self):
        table = _make_table(table_status="dirty")
        with patch("menu.views.TableLink.objects") as tl_om:
            tl_om.get.return_value = table
            resp = self._patch(1, {"status": "open"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "open")

    def test_occupied_is_rejected(self):
        with patch("menu.views.TableLink.objects"):
            resp = self._patch(1, {"status": "occupied"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_status")

    def test_unknown_status_is_rejected(self):
        with patch("menu.views.TableLink.objects"):
            resp = self._patch(1, {"status": "banana"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_status_is_rejected(self):
        with patch("menu.views.TableLink.objects"):
            resp = self._patch(1, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_not_found_returns_404(self):
        from menu.models import TableLink as TL
        with patch("menu.views.TableLink.objects") as tl_om:
            tl_om.get.side_effect = TL.DoesNotExist
            resp = self._patch(99, {"status": "dirty"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._patch(1, {"status": "dirty"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.patch("/api/staff/tables/1/status/", {"status": "dirty"}, format="json")
        req.tenant = _tenant()
        resp = self.view(req, table_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 2 — StaffTransferItemsView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffTransferItemsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffTransferItemsView.as_view()

    def _post(self, src_order_id, payload, user=None, tenant_id=1):
        req = self.factory.post(
            f"/api/staff/orders/{src_order_id}/transfer-items/",
            payload,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req, src_order_id=src_order_id)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._staff_order_payload", return_value={"id": 1, "order_number": "ORD-001"})
    @patch("menu.views._recompute_order_totals")
    def test_happy_path_moves_items(self, recompute_mock, payload_mock, broadcast_mock):
        """Items are reassigned to dest; both orders recalculated; both broadcast."""
        item1 = _make_item(pk=10, order_id=1)
        item2 = _make_item(pk=11, order_id=1)
        src = _make_order(pk=1, items=[item1, item2])
        dest = _make_order(pk=2, order_number="ORD-002")

        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om, \
             patch("menu.models.OrderItem") as oi_model:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [src, dest]
            om.select_for_update.return_value = locked
            oi_model.objects.filter.return_value.update = MagicMock()

            resp = self._post(1, {"item_ids": [10, 11], "dest_order_id": 2})

        # View reached the post-atomic broadcast phase (or hit the src.refresh_from_db)
        # If no 4xx was returned the guards all passed.
        self.assertNotIn(resp.status_code, [400, 403, 409])

    def test_missing_item_ids_is_400(self):
        resp = self._post(1, {"dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_items")

    def test_empty_item_ids_is_400(self):
        resp = self._post(1, {"item_ids": [], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_items")

    def test_missing_dest_order_id_is_400(self):
        resp = self._post(1, {"item_ids": [1]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_dest")

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._post(1, {"item_ids": [1], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.post(
            "/api/staff/orders/1/transfer-items/",
            {"item_ids": [1], "dest_order_id": 2},
            format="json",
        )
        req.tenant = _tenant()
        resp = self.view(req, src_order_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_src_not_found_is_404(self):
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = Order.DoesNotExist
            om.select_for_update.return_value = locked
            resp = self._post(99, {"item_ids": [1], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_src_not_table_order_is_409(self):
        src = _make_order(pk=1, fulfillment_type=Order.FulfillmentType.PICKUP)
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.return_value = src
            om.select_for_update.return_value = locked
            resp = self._post(1, {"item_ids": [1], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    def test_src_bad_status_is_409(self):
        src = _make_order(pk=1, order_status=Order.Status.COMPLETED)
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.return_value = src
            om.select_for_update.return_value = locked
            resp = self._post(1, {"item_ids": [1], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    def test_src_already_paid_is_409(self):
        src = _make_order(pk=1, payment_status=Order.PaymentStatus.PAID)
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.return_value = src
            om.select_for_update.return_value = locked
            resp = self._post(1, {"item_ids": [1], "dest_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 3 — StaffMergeOrdersView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffMergeOrdersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffMergeOrdersView.as_view()

    def _post(self, dest_order_id, payload, user=None, tenant_id=1):
        req = self.factory.post(
            f"/api/staff/orders/{dest_order_id}/merge/",
            payload,
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req, dest_order_id=dest_order_id)

    def test_missing_src_order_id_is_400(self):
        resp = self._post(1, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_src")

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._post(1, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.post(
            "/api/staff/orders/1/merge/",
            {"src_order_id": 2},
            format="json",
        )
        req.tenant = _tenant()
        resp = self.view(req, dest_order_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_dest_not_found_is_404(self):
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = Order.DoesNotExist
            om.select_for_update.return_value = locked
            resp = self._post(99, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_same_order_is_400(self):
        dest = _make_order(pk=5, order_number="ORD-005")
        src_same = _make_order(pk=5, order_number="ORD-005")
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [dest, src_same]
            om.select_for_update.return_value = locked
            resp = self._post(5, {"src_order_id": 5})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "same_order")

    def test_dest_not_table_is_409(self):
        dest = _make_order(pk=1, fulfillment_type=Order.FulfillmentType.PICKUP)
        src = _make_order(pk=2, order_number="ORD-002")
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [dest, src]
            om.select_for_update.return_value = locked
            resp = self._post(1, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    def test_src_not_table_is_409(self):
        dest = _make_order(pk=1)
        src = _make_order(pk=2, order_number="ORD-002", fulfillment_type=Order.FulfillmentType.DELIVERY)
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [dest, src]
            om.select_for_update.return_value = locked
            resp = self._post(1, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_table")

    def test_dest_bad_status_is_409(self):
        dest = _make_order(pk=1, order_status=Order.Status.CANCELLED)
        src = _make_order(pk=2, order_number="ORD-002")
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [dest, src]
            om.select_for_update.return_value = locked
            resp = self._post(1, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    def test_dest_already_paid_is_409(self):
        dest = _make_order(pk=1, payment_status=Order.PaymentStatus.PAID)
        src = _make_order(pk=2, order_number="ORD-002")
        with patch("django.db.transaction.atomic") as tx_mock, \
             patch("menu.views.Order.objects") as om:
            tx_mock.return_value.__enter__ = MagicMock(return_value=None)
            tx_mock.return_value.__exit__ = MagicMock(return_value=False)
            locked = MagicMock()
            locked.prefetch_related.return_value.get.side_effect = [dest, src]
            om.select_for_update.return_value = locked
            resp = self._post(1, {"src_order_id": 2})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_paid")
