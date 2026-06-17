"""
A5-followup — Marketplace billing CORRECTNESS (commission reversal + multi-currency).

Three independent money fixes, each unit-tested (SimpleTestCase + mocks — no DB):

  FIX 1 — OwnerCommissionStatementView EXCLUDES cancelled marketplace orders from
          the commission query. A cancelled order's food revenue is fully refunded,
          so the platform must never bill commission on it. The exclusion is applied
          on the base queryset so the aggregate AND the per-order rows agree; a
          COMPLETED order is still billed.

  FIX 2 — StaffVoidOrderItemView RECOMPUTES Order.commission_amount when an item is
          voided off a MARKETPLACE order, from the new (post-void) pre-discount food
          subtotal × the order's SNAPSHOTTED commission_rate_applied — the same basis
          A5 charged at placement. Direct orders (rate == 0) are untouched. Never < 0.

  FIX 3 — OwnerCommissionStatementView reports totals PER ISO CURRENCY (a per_currency
          breakdown) instead of one cross-currency sum, and the PDF labels each
          currency block with its OWN code/total — never orders_data[0]['currency']
          for everything.

The statement view filters with Order.objects.filter(...).exclude(...).order_by(...);
the void view reloads the order via Order.objects.select_for_update().prefetch_related().get().
Both import models at module top, so we patch menu.views.Order directly (same technique
as test_a5_commission.py / test_loyalty_void_clawback.py).
"""
from datetime import datetime, timezone as _tz
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import OwnerCommissionStatementView, StaffVoidOrderItemView
from menu.models import Order
from accounts.models import User


# ── Shared statement-view harness (mirrors test_a5_commission.py) ──────────────

class _CommissionStatementHarness(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCommissionStatementView.as_view()

    def _tenant(self, tz_name="UTC"):
        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        profile = MagicMock()
        profile.timezone = tz_name
        profile.service_day_cutover_hour = 0
        tenant.profile = profile
        return tenant

    def _order_row(self, *, number="ORD-1", total="20.00", commission="3.00",
                   rate="0.15", currency="MAD", status_val="completed",
                   delivery_fee="0.00"):
        return SimpleNamespace(
            order_number=number,
            created_at=datetime(2026, 6, 15, 12, 0, tzinfo=_tz.utc),
            customer_name="Diner",
            total=Decimal(total),
            delivery_fee=Decimal(delivery_fee),
            commission_amount=Decimal(commission),
            commission_rate_applied=Decimal(rate),
            currency=currency,
            status=status_val,
        )

    def _run_json(self, orders, *, capture_filter=None, capture_exclude=None):
        """Drive the JSON branch. The view's qs is filter(...).exclude(...).order_by(...);
        we make those chain back to a qs that iterates `orders` and aggregates over them."""
        tenant = self._tenant()

        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.__iter__ = lambda s: iter(orders)

        def _filter(**kwargs):
            if capture_filter is not None:
                capture_filter.update(kwargs)
            return qs

        def _exclude(**kwargs):
            if capture_exclude is not None:
                capture_exclude.update(kwargs)
            return qs

        qs.exclude.side_effect = _exclude

        with patch("menu.views._is_tenant_owner", return_value=True), \
                patch("menu.views.Order") as mock_order:
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status.CANCELLED = "cancelled"
            mock_order.objects.filter.side_effect = _filter
            req = self.factory.get("/api/owner/commission-statement/?year=2026&month=6")
            req.user = MagicMock(is_authenticated=True)
            req.tenant = tenant
            resp = self.view(req)
        return resp

    def _pdf_text(self, orders):
        tenant = self._tenant()
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.__iter__ = lambda s: iter(orders)

        with patch("menu.views._is_tenant_owner", return_value=True), \
                patch("menu.views.Order") as mock_order:
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status.CANCELLED = "cancelled"
            mock_order.objects.filter.return_value = qs
            req = self.factory.get(
                "/api/owner/commission-statement/?year=2026&month=6&format=pdf"
            )
            req.user = MagicMock(is_authenticated=True)
            req.tenant = tenant
            view = OwnerCommissionStatementView()
            view.format_kwarg = None
            drf_req = view.initialize_request(req)
            resp = view.get(drf_req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(b"".join(resp.streaming_content)
                                   if hasattr(resp, "streaming_content")
                                   else resp.content))
        return "".join(page.extract_text() for page in reader.pages)


# ── FIX 1: cancelled orders excluded from the commission statement ────────────

class CancelledOrderExclusionTests(_CommissionStatementHarness):
    def test_query_excludes_cancelled_status(self):
        """The statement queryset must .exclude(status=CANCELLED) so the platform
        never bills commission on a fully-refunded (cancelled) marketplace order.
        The exclusion sits on the base qs → aggregate AND rows agree."""
        capture_exclude = {}
        resp = self._run_json(
            [self._order_row(number="ORD-OK", status_val="completed")],
            capture_exclude=capture_exclude,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(capture_exclude.get("status"), "cancelled")

    def test_completed_included_cancelled_excluded_in_totals_and_rows(self):
        """A COMPLETED marketplace order is billed; a CANCELLED one never reaches the
        statement (the DB .exclude removes it). We simulate the DB exclusion by only
        feeding the surviving COMPLETED order, and assert the totals + rows reflect
        exactly that one order — proving cancelled revenue/commission is not summed."""
        completed = self._order_row(number="ORD-DONE", total="40.00",
                                    commission="6.00", rate="0.15",
                                    status_val="completed")
        resp = self._run_json([completed])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        # Exactly one row — the completed order.
        self.assertEqual(len(data["orders"]), 1)
        self.assertEqual(data["orders"][0]["order_number"], "ORD-DONE")
        # Totals reflect only the completed order's money.
        self.assertEqual(data["summary"]["order_count"], 1)
        self.assertEqual(data["summary"]["total_revenue"], 40.0)
        self.assertEqual(data["summary"]["total_commission"], 6.0)
        self.assertEqual(data["summary"]["net_payout"], 34.0)


# ── FIX 3: per-currency statement totals ──────────────────────────────────────

class PerCurrencyStatementTests(_CommissionStatementHarness):
    def test_single_currency_keeps_top_level_summary(self):
        """The common single-currency case preserves the historical top-level
        `summary` shape (now with a `currency` field) and still emits per_currency."""
        resp = self._run_json([
            self._order_row(number="ORD-1", total="20.00", commission="3.00",
                            currency="MAD"),
            self._order_row(number="ORD-2", total="30.00", commission="4.50",
                            currency="MAD"),
        ])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data["summary"]["currency"], "MAD")
        self.assertEqual(data["summary"]["order_count"], 2)
        self.assertEqual(data["summary"]["total_revenue"], 50.0)
        self.assertEqual(data["summary"]["total_commission"], 7.5)
        self.assertEqual(data["summary"]["net_payout"], 42.5)
        # per_currency present with a single MAD bucket.
        self.assertEqual(len(data["per_currency"]), 1)
        self.assertEqual(data["per_currency"][0]["currency"], "MAD")
        self.assertEqual(data["per_currency"][0]["total_commission"], 7.5)

    def test_mixed_currency_reports_per_currency_not_one_sum(self):
        """A month with two currencies must yield per-currency totals — NOT a single
        cross-currency sum. 10 MAD + 10 USD must never collapse to 20-of-anything."""
        resp = self._run_json([
            self._order_row(number="ORD-MAD", total="100.00", commission="10.00",
                            rate="0.10", currency="MAD"),
            self._order_row(number="ORD-USD", total="50.00", commission="7.50",
                            rate="0.15", currency="USD"),
        ])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data

        by_cur = {b["currency"]: b for b in data["per_currency"]}
        self.assertEqual(set(by_cur), {"MAD", "USD"})
        self.assertEqual(by_cur["MAD"]["total_revenue"], 100.0)
        self.assertEqual(by_cur["MAD"]["total_commission"], 10.0)
        self.assertEqual(by_cur["MAD"]["net_payout"], 90.0)
        self.assertEqual(by_cur["USD"]["total_revenue"], 50.0)
        self.assertEqual(by_cur["USD"]["total_commission"], 7.5)
        self.assertEqual(by_cur["USD"]["net_payout"], 42.5)

        # The cross-currency top-level summary must NOT publish a meaningless sum.
        self.assertTrue(data["summary"].get("mixed_currency"))
        self.assertEqual(data["summary"]["currency"], "")
        self.assertEqual(data["summary"]["total_revenue"], 0.0)
        self.assertEqual(data["summary"]["total_commission"], 0.0)
        # …but the order count across currencies is still correct.
        self.assertEqual(data["summary"]["order_count"], 2)

    def test_delivery_fee_excluded_from_net_payout(self):
        """net_payout must subtract delivery_fee: the restaurant does NOT keep the
        delivery fee — it passes through to the driver. For a delivery order with
        total=120, delivery_fee=20, commission=10 the restaurant earns 90, not 110."""
        resp = self._run_json([
            self._order_row(number="ORD-DEL", total="120.00", commission="10.00",
                            rate="0.10", delivery_fee="20.00"),
        ])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        row = data["orders"][0]
        self.assertEqual(row["delivery_fee"], 20.0)
        self.assertEqual(row["net_payout"], 90.0)  # 120 - 20 - 10
        pc = data["per_currency"][0]
        self.assertEqual(pc["total_delivery_fees"], 20.0)
        self.assertEqual(pc["net_payout"], 90.0)   # 120 - 20 - 10

    def test_zero_delivery_fee_leaves_net_payout_unchanged(self):
        """A pickup/dine-in order with delivery_fee=0 must still compute
        net_payout = total − commission (identical to the pre-fix formula)."""
        resp = self._run_json([
            self._order_row(number="ORD-PICKUP", total="50.00", commission="5.00",
                            rate="0.10", delivery_fee="0.00"),
        ])
        data = resp.data
        self.assertEqual(data["orders"][0]["net_payout"], 45.0)  # 50 - 0 - 5
        self.assertEqual(data["per_currency"][0]["net_payout"], 45.0)

    def test_pdf_labels_each_currency_with_its_own_code(self):
        """The PDF must render each currency with ITS OWN code/total — never stamp
        every line with orders_data[0]['currency']. A mixed MAD/USD month shows both
        currency codes against their own figures."""
        text = self._pdf_text([
            self._order_row(number="ORD-MAD", total="100.00", commission="10.00",
                            rate="0.10", currency="MAD"),
            self._order_row(number="ORD-USD", total="50.00", commission="7.50",
                            rate="0.15", currency="USD"),
        ])
        # Both currency codes appear (per-currency summary + totals blocks).
        self.assertIn("MAD", text)
        self.assertIn("USD", text)
        # Each currency's own commission figure is present against its code.
        self.assertIn("MAD 10.00", text)
        self.assertIn("USD 7.50", text)
        # The USD line must NOT be mislabelled with MAD.
        self.assertNotIn("MAD 7.50", text)


# ── FIX 2: commission recompute on item void ──────────────────────────────────

def _user(role=User.Roles.TENANT_OWNER, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.id = 42
    u.get_full_name = MagicMock(return_value="")
    u.username = "owner"
    u.email = "owner@example.com"
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _item(item_id=901, dish_slug="burger", dish_name="Burger", qty=1,
          subtotal=Decimal("20.00"), is_voided=False):
    it = MagicMock()
    it.id = item_id
    it.dish_slug = dish_slug
    it.dish_name = dish_name
    it.qty = qty
    it.unit_price = subtotal
    it.subtotal = subtotal
    it.options = []
    it.note = ""
    it.is_ready = False
    it.is_voided = is_voided
    it.combo_components = []
    it.save = MagicMock()
    return it


def _order(*, order_id=10, source="marketplace", commission_rate="0.15",
           commission_amount="6.00", status_val=Order.Status.PENDING,
           payment_status=Order.PaymentStatus.UNPAID, total=Decimal("40.00"),
           wallet_amount_paid=Decimal("0"), customer_id=None, points_earned=0,
           items=None):
    o = MagicMock()
    o.id = order_id
    o.pk = order_id
    o.order_number = "ORD-V001"
    o.source = source
    o.commission_rate_applied = Decimal(commission_rate)
    o.commission_amount = Decimal(commission_amount)
    o.status = status_val
    o.fulfillment_type = Order.FulfillmentType.PICKUP
    o.payment_status = payment_status
    o.total = total
    o.delivery_fee = Decimal("0")
    o.tip_amount = Decimal("0")
    o.promotion_discount = Decimal("0")
    o.loyalty_discount = Decimal("0")
    o.wallet_amount_paid = wallet_amount_paid
    o.customer_id = customer_id
    o.points_earned = points_earned
    o.redeemed_loyalty_points = 0
    o.table_label = ""
    o.customer_name = "Alice"
    o.customer_note = ""
    o.owner_note = ""
    o.estimated_ready_minutes = None
    o.currency = "MAD"
    o.scheduled_for = None
    o.save = MagicMock()
    o.mark_paid = MagicMock()
    o.created_at = MagicMock()
    o.created_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"
    o.updated_at = MagicMock()
    o.updated_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"

    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    items_qs.filter.return_value.first.return_value = _items[0] if _items else None
    o.items = items_qs

    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    o.payments = payments_qs
    return o


class _FakeAtomic:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class VoidCommissionRecomputeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffVoidOrderItemView.as_view()
        _p = patch("menu.views._can_access_order", return_value=True)
        self._access = _p.start()
        self.addCleanup(_p.stop)

    def _post(self, order_id=10, item_id=901):
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/{item_id}/void/", {}, format="json"
        )
        force_authenticate(req, user=_user())
        req.tenant = SimpleNamespace(id=1)
        return self.view(req, order_id=order_id, item_id=item_id)

    def _run(self, order_initial, order_locked):
        with patch("menu.views._can_edit_tenant_order", return_value=True), \
                patch("menu.views.transaction") as tx_mock, \
                patch("menu.views.Order.objects") as order_om, \
                patch("menu.views.Dish.objects") as dish_om, \
                patch("menu.views._broadcast_order_change"):
            tx_mock.atomic.return_value = _FakeAtomic()
            order_om.prefetch_related.return_value.filter.return_value.first.return_value = order_initial
            order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = order_locked
            order_om.filter.return_value.update.return_value = 1
            dish_om.select_for_update.return_value.filter.return_value = []
            return self._post(order_id=order_initial.id, item_id=901)

    def test_marketplace_void_recomputes_commission_at_snapshot_rate(self):
        """Voiding one of two equal lines off a 0.15-rate marketplace order halves the
        food subtotal, so commission must drop to 0.15 × the remaining 20.00 = 3.00
        (down from 6.00). The reduced value is persisted (commission_amount in
        update_fields)."""
        to_void = _item(item_id=901, subtotal=Decimal("20.00"))
        initial = _order(commission_rate="0.15", commission_amount="6.00",
                         total=Decimal("40.00"), items=[to_void])
        # After void: one line voided, one kept (remaining food subtotal = 20.00).
        locked = _order(
            commission_rate="0.15", commission_amount="6.00",
            total=Decimal("40.00"),
            items=[_item(item_id=901, subtotal=Decimal("20.00"), is_voided=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("20.00"))],
        )
        resp = self._run(initial, locked)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(locked.commission_amount, Decimal("3.00"))
        # Persisted in the save's update_fields.
        update_fields = locked.save.call_args.kwargs["update_fields"]
        self.assertIn("commission_amount", update_fields)

    def test_marketplace_full_void_drops_commission_to_zero_never_negative(self):
        """Voiding the only line zeroes the food subtotal → commission = 0.00,
        and is clamped at >= 0 (never negative)."""
        to_void = _item(item_id=901, subtotal=Decimal("20.00"))
        initial = _order(commission_rate="0.15", commission_amount="3.00",
                         total=Decimal("20.00"), items=[to_void])
        locked = _order(
            commission_rate="0.15", commission_amount="3.00",
            total=Decimal("20.00"),
            items=[_item(item_id=901, subtotal=Decimal("20.00"), is_voided=True)],
        )
        resp = self._run(initial, locked)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(locked.commission_amount, Decimal("0.00"))
        self.assertGreaterEqual(locked.commission_amount, Decimal("0"))

    def test_direct_order_commission_untouched(self):
        """A DIRECT order carries no commission rate (commission_rate_applied == 0);
        voiding an item must NOT recompute commission and must NOT add
        commission_amount to the save's update_fields."""
        to_void = _item(item_id=901, subtotal=Decimal("20.00"))
        initial = _order(source="direct", commission_rate="0.00",
                         commission_amount="0.00", total=Decimal("40.00"),
                         items=[to_void])
        locked = _order(
            source="direct", commission_rate="0.00", commission_amount="0.00",
            total=Decimal("40.00"),
            items=[_item(item_id=901, subtotal=Decimal("20.00"), is_voided=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("20.00"))],
        )
        resp = self._run(initial, locked)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # commission_amount left at its placement value (0.00) and NOT in update_fields.
        self.assertEqual(locked.commission_amount, Decimal("0.00"))
        update_fields = locked.save.call_args.kwargs["update_fields"]
        self.assertNotIn("commission_amount", update_fields)

    def test_marketplace_void_uses_pre_discount_food_basis_not_total(self):
        """Commission recompute uses the pre-discount FOOD subtotal (sum of non-voided
        line subtotals) — NOT order.total — so delivery_fee / promo_discount on the
        order do not distort the new commission. Order has a 50.00 promo discount and
        a 15.00 delivery fee, but commission is still 0.15 × remaining food 20.00."""
        to_void = _item(item_id=901, subtotal=Decimal("20.00"))
        initial = _order(commission_rate="0.15", commission_amount="6.00",
                         total=Decimal("40.00"), items=[to_void])
        locked = _order(
            commission_rate="0.15", commission_amount="6.00",
            total=Decimal("40.00"),
            items=[_item(item_id=901, subtotal=Decimal("20.00"), is_voided=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("20.00"))],
        )
        # Non-food components that must NOT enter the commission basis.
        locked.delivery_fee = Decimal("15.00")
        locked.promotion_discount = Decimal("5.00")
        resp = self._run(initial, locked)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # 0.15 × 20.00 remaining FOOD = 3.00 (delivery/promo excluded).
        self.assertEqual(locked.commission_amount, Decimal("3.00"))
