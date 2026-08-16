"""
Regression tests for the menu/views.py hardening sweep — one focused test per finding.

All tests are mock-based SimpleTestCase (no real DB), following the house style of the
sibling suites (test_order_self_cancel.py, test_staff_dine_in_items.py,
test_customer_order_status_view.py, test_sweep_auto_refund.py).

Findings covered:
  1. OwnerCustomerLoyaltyGrantView — ordered-here gate blocks the cross-tenant global
     loyalty write.
  2. OwnerCustomerNotesView — ordered-here gate (hygiene).
  3. StaffClockInView — single-open guard runs inside atomic() behind an advisory lock.
  4. CustomerOrderStatusView — tenant_phone is read from Profile (not the tenant), so the
     "call restaurant" button works on the direct/QR page.
  5. CustomerOrderStatusView — customer item payload exposes is_comped.
  6. CustomerOrderStatusView — items_count excludes voided lines (owner-parity).
  7. CustomerOrderCancelView — concurrent self-cancel does not double-apply loyalty/restock.
  8. StaffVoidOrderItemView — the void mark is an atomic compare-and-set; a lost race 409s
     without restocking.
  9. Best-effort restock/loyalty side-effects log instead of swallowing silently.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, User
from menu.models import Order
from menu.views import (
    CustomerOrderCancelView,
    CustomerOrderStatusView,
    OwnerCustomerLoyaltyGrantView,
    OwnerCustomerNotesView,
    StaffVoidOrderItemView,
    _restock_cancelled_order,
)


# ── Shared helpers ──────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 10
    u.id = 10
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 20
    u.id = 20
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    u.Roles = User.Roles
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, slug="demo", name="Demo Restaurant")


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 1 — OwnerCustomerLoyaltyGrantView ordered-here gate (cross-tenant IDOR)
# ═══════════════════════════════════════════════════════════════════════════════

class LoyaltyGrantOrderedHereGateTests(SimpleTestCase):
    def _req(self, data):
        req = APIRequestFactory().post("/api/owner/customers/5/loyalty-grant/", data, format="json")
        req.user = _owner()
        req.tenant = _tenant()
        return req

    @patch("menu.views.Order")
    def test_customer_without_orders_here_is_blocked(self, MockOrder):
        """A customer who only ordered at another tenant → 404 no_orders, and the global
        public-schema loyalty balance is never locked/mutated."""
        MockOrder.objects.filter.return_value.exists.return_value = False
        with patch("accounts.models.Customer") as MockCust:
            resp = OwnerCustomerLoyaltyGrantView.as_view()(self._req({"delta": 5000}), customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "no_orders")
        MockCust.objects.select_for_update.assert_not_called()

    @patch("menu.views.Order")
    def test_customer_with_orders_here_is_mutated(self, MockOrder):
        """A customer with a real relationship to this tenant still gets the grant."""
        MockOrder.objects.filter.return_value.exists.return_value = True
        cust = MagicMock()
        cust.loyalty_points = 100
        with patch("accounts.models.Customer") as MockCust, \
                patch("django.db.transaction.atomic", return_value=_noop_atomic()):
            MockCust.DoesNotExist = Exception
            MockCust.objects.select_for_update.return_value.get.return_value = cust
            resp = OwnerCustomerLoyaltyGrantView.as_view()(self._req({"delta": 50}), customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["loyalty_points"], 150)


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 2 — OwnerCustomerNotesView ordered-here gate (hygiene)
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerNotesOrderedHereGateTests(SimpleTestCase):
    def _req(self, data):
        req = APIRequestFactory().patch("/api/owner/customers/5/notes/", data, format="json")
        req.user = _owner()
        req.tenant = _tenant()
        return req

    @patch("menu.views.Order")
    @patch("menu.views.CustomerNote")
    def test_no_orders_here_blocks_note_upsert(self, MockNote, MockOrder):
        MockOrder.objects.filter.return_value.exists.return_value = False
        resp = OwnerCustomerNotesView.as_view()(self._req({"notes": "x"}), customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "no_orders")
        MockNote.objects.update_or_create.assert_not_called()

    @patch("menu.views.Order")
    @patch("menu.views.CustomerNote")
    def test_note_upsert_allowed_when_ordered_here(self, MockNote, MockOrder):
        MockOrder.objects.filter.return_value.exists.return_value = True
        note_obj = MagicMock()
        note_obj.notes = "VIP"
        MockNote.objects.update_or_create.return_value = (note_obj, True)
        resp = OwnerCustomerNotesView.as_view()(self._req({"notes": "VIP"}), customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        MockNote.objects.update_or_create.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 3 — StaffClockInView single-open guard (atomic + advisory lock)
# ═══════════════════════════════════════════════════════════════════════════════

class ClockInSingleOpenGuardTests(SimpleTestCase):
    def test_guard_uses_atomic_and_advisory_lock(self):
        """Mirrors DrawerOpenView's serialization guard — the exists-check + create must
        run inside transaction.atomic() behind a per-schema+user advisory lock."""
        import inspect
        from menu.views import StaffClockInView
        src = inspect.getsource(StaffClockInView.post)
        self.assertIn("transaction.atomic()", src)
        self.assertIn("pg_advisory_xact_lock", src)
        self.assertIn("clock_in:", src)

    def test_second_concurrent_clock_in_is_409_under_lock(self):
        """With the advisory lock held, the loser sees the winner's open shift → 409."""
        from menu.views import StaffClockInView
        factory = APIRequestFactory()
        req = factory.post("/api/staff/clock-in/", {}, format="json")
        force_authenticate(req, user=_staff())
        req.tenant = _tenant()
        with patch("menu.models.Shift") as _S, patch("menu.views.transaction"):
            _S.objects.filter.return_value.exists.return_value = True  # winner already open
            resp = StaffClockInView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_clocked_in")


# ═══════════════════════════════════════════════════════════════════════════════
# Findings 4/5/6 — CustomerOrderStatusView payload
# ═══════════════════════════════════════════════════════════════════════════════

def _status_item(dish_slug="margherita", qty=1, subtotal="30.00",
                 is_voided=False, is_comped=False):
    it = MagicMock()
    it.dish_slug = dish_slug
    it.dish_name = dish_slug.title()
    it.qty = qty
    it.unit_price = Decimal(subtotal)
    it.subtotal = Decimal(subtotal)
    it.options = []
    it.note = ""
    it.is_voided = is_voided
    it.is_comped = is_comped
    it.combo_components = []
    return it


def _status_order(items):
    order = MagicMock()
    order.order_number = "ORD123"
    order.status = "pending"
    order.fulfillment_type = "pickup"
    order.table_label = ""
    order.customer_name = "Sara"
    order.delivery_address = ""
    order.total = Decimal("60.00")
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.loyalty_discount = Decimal("0")
    order.wallet_amount_paid = Decimal("0")
    order.currency = "MAD"
    order.payment_status = "unpaid"
    order.requires_prepayment = False
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.scheduled_for = None
    order.delivery_code = None
    order.points_earned = 0
    order.rating = None
    order.customer_id = None  # anonymous → full body (no PII gate)
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-05-15T12:00:00+00:00"
    order.status_updated_at = None
    items_qs = MagicMock()
    items_qs.all.return_value = items
    order.items = items_qs
    return order


class OrderStatusPayloadTests(SimpleTestCase):
    def _get(self, order, tenant):
        req = APIRequestFactory().get("/api/order-status/ORD123/")
        req.tenant = tenant
        return CustomerOrderStatusView.as_view()(req, order_number="ORD123")

    @patch("menu.views.order_vat_fields", return_value={})
    @patch("menu.views.Order.objects")
    def test_tenant_phone_read_from_profile(self, objects_mock, _vat):
        """Finding 4: phone lives on Profile, not the Tenant — the payload must surface it."""
        order = _status_order([_status_item()])
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        tenant = SimpleNamespace(
            id=7,
            profile=SimpleNamespace(phone="0612345678", receipt_message="Thanks",
                                    vat_rate=0, vat_label=""),
        )
        resp = self._get(order, tenant)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["tenant_phone"], "0612345678")

    @patch("menu.views.order_vat_fields", return_value={})
    @patch("menu.views.Order.objects")
    def test_item_payload_exposes_is_comped(self, objects_mock, _vat):
        """Finding 5: a comped line must carry is_comped so the receipt can reconcile."""
        order = _status_order([_status_item(is_comped=True)])
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        tenant = SimpleNamespace(id=7, profile=SimpleNamespace(
            phone="", receipt_message="", vat_rate=0, vat_label=""))
        resp = self._get(order, tenant)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("is_comped", resp.data["items"][0])
        self.assertTrue(resp.data["items"][0]["is_comped"])

    @patch("menu.views.order_vat_fields", return_value={})
    @patch("menu.views.Order.objects")
    def test_items_count_excludes_voided(self, objects_mock, _vat):
        """Finding 6: header count must match the owner semantic (non-voided only)."""
        items = [
            _status_item(dish_slug="kept", qty=2, is_voided=False),
            _status_item(dish_slug="voided", qty=1, is_voided=True),
        ]
        order = _status_order(items)
        objects_mock.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = order
        tenant = SimpleNamespace(id=7, profile=SimpleNamespace(
            phone="", receipt_message="", vat_rate=0, vat_label=""))
        resp = self._get(order, tenant)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # 2 (non-voided) — NOT 3 (which would count the struck-through voided line)
        self.assertEqual(resp.data["items_count"], 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 7 — CustomerOrderCancelView concurrent self-cancel
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerSelfCancelRaceTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderCancelView.as_view()
        self._patchers = {
            "orders": patch("menu.views.Order.objects"),
            "refund": patch("menu.views._refund_wallet_for_cancelled_order"),
            "loyalty": patch("menu.views._reverse_loyalty_for_cancelled_order"),
            "restock": patch("menu.views._restock_cancelled_order"),
            "broadcast": patch("menu.views._broadcast_order_change"),
            "email": patch("menu.views._send_order_status_email"),
            "atomic": patch("django.db.transaction.atomic", return_value=_noop_atomic()),
        }
        self.m = {k: p.start() for k, p in self._patchers.items()}
        for p in self._patchers.values():
            self.addCleanup(p.stop)

    def _post(self, cid=42):
        req = self.factory.post("/api/order-status/ORD-1/cancel/")
        principal = Customer(id=cid)
        principal.save = MagicMock()
        force_authenticate(req, user=principal)
        req.tenant = MagicMock(id=7)
        return req

    def _wire(self, stale_status, locked_status):
        order = MagicMock()
        order.order_number = "ORD-1"
        order.pk = 1
        order.customer_id = 42
        order.status = stale_status
        order.fulfillment_type = "pickup"
        order.payment_status = "paid"
        order.save = MagicMock()
        # First (unlocked) lookup.
        self.m["orders"].filter.return_value.first.return_value = order
        # Row read UNDER select_for_update inside the atomic block.
        locked = MagicMock()
        locked.status = locked_status
        self.m["orders"].select_for_update.return_value.filter.return_value.first.return_value = locked
        return order

    def test_peer_cancelled_under_lock_skips_loyalty_and_restock(self):
        """This caller loaded the order as PENDING (stale), but a racing peer cancelled it
        first, so the row read UNDER the lock is CANCELLED. The keyed wallet credit still
        replays, but the NON-idempotent loyalty claw-back + restock must NOT run twice."""
        self._wire(stale_status=Order.Status.PENDING, locked_status=Order.Status.CANCELLED)
        resp = self.view(self._post(), order_number="ORD-1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.m["refund"].assert_called_once()      # idempotent → safe to replay
        self.m["loyalty"].assert_not_called()      # NOT double-clawed
        self.m["restock"].assert_not_called()      # NOT double-restocked

    def test_first_cancel_runs_full_reversal(self):
        """The winning call (row still live under the lock) performs the full reversal."""
        order = self._wire(stale_status=Order.Status.PENDING, locked_status=Order.Status.PENDING)
        resp = self.view(self._post(), order_number="ORD-1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.m["refund"].assert_called_once()
        self.m["loyalty"].assert_called_once()
        self.m["restock"].assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 8 — StaffVoidOrderItemView atomic compare-and-set
# ═══════════════════════════════════════════════════════════════════════════════

def _void_item(item_id=901, is_voided=False, subtotal="12.50"):
    it = MagicMock()
    it.id = item_id
    it.dish_slug = "burger"
    it.qty = 1
    it.subtotal = Decimal(subtotal)
    it.combo_components = []
    it.is_voided = is_voided
    it.save = MagicMock()
    return it


def _void_order(item, status_val=Order.Status.PENDING, payment_status=Order.PaymentStatus.UNPAID):
    order = MagicMock()
    order.id = 10
    order.pk = 10
    order.order_number = "ORD-V"
    order.status = status_val
    order.payment_status = payment_status
    order.wallet_amount_paid = Decimal("0")
    order.customer_id = None
    order.items.filter.return_value.first.return_value = item
    return order


class VoidItemCompareAndSetTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffVoidOrderItemView.as_view()
        for tgt in ("menu.views._can_access_order", "menu.views._can_void_order_item"):
            p = patch(tgt, return_value=True)
            p.start()
            self.addCleanup(p.stop)

    def _post(self, item_id=901):
        req = self.factory.post(f"/api/staff/orders/10/items/{item_id}/void/", {}, format="json")
        force_authenticate(req, user=_staff())
        req.tenant = _tenant()
        return self.view(req, order_id=10, item_id=item_id)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.transaction")
    @patch("menu.views.OrderItem")
    @patch("menu.views.Order.objects")
    def test_lost_race_409s_without_restock(self, order_om, oi_mock, tx_mock, dish_om, broadcast):
        """A concurrent double-tap: this call passed the unlocked fast-path, but the atomic
        compare-and-set (filter(pk, is_voided=False).update) affects 0 rows because the peer
        already committed the void → 409, and NO restock / broadcast runs."""
        item = _void_item(is_voided=False)
        order = _void_order(item)
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = order
        # CAS loses the race → 0 rows updated.
        oi_mock.objects.filter.return_value.update.return_value = 0
        tx_mock.atomic.return_value.__enter__ = MagicMock(return_value=None)
        tx_mock.atomic.return_value.__exit__ = MagicMock(return_value=False)

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_voided")
        oi_mock.objects.filter.assert_called_with(pk=901, is_voided=False)
        dish_om.select_for_update.assert_not_called()   # no restock
        broadcast.assert_not_called()
        item.save.assert_not_called()                   # the mark is a CAS, not item.save


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 9 — best-effort side-effects log instead of a silent bare pass
# ═══════════════════════════════════════════════════════════════════════════════

class BestEffortLoggingTests(SimpleTestCase):
    def test_restock_failure_is_logged_not_raised(self):
        """A raising restock loop must be swallowed (never block a cancel) but LOGGED
        (previously a silent bare `pass`), with the order id for reconciliation."""
        order = MagicMock()
        order.order_number = "ORD-9"
        order.items.filter.side_effect = RuntimeError("boom")
        logger = MagicMock()
        with patch("logging.getLogger", return_value=logger):
            _restock_cancelled_order(order)  # must NOT raise
        logger.exception.assert_called_once()
        # The log message carries the order identifier.
        self.assertIn("ORD-9", str(logger.exception.call_args))

    def test_void_clawback_failure_is_logged(self):
        """The per-item loyalty clawback except-block logs (bare `pass` removed)."""
        import inspect
        src = inspect.getsource(StaffVoidOrderItemView.post)
        self.assertIn("Loyalty clawback failed", src)
        self.assertNotIn("pass  # Loyalty clawback is best-effort", src)
