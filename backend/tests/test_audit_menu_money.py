"""Regression tests for three verified money defects in menu/views.py
(branch fix/audit-menu-money). All mock-based SimpleTestCase — no DB.

  BUG 1 (HIGH — silent revenue loss): the void/comp "Case B" settle predicate on an
        UNPAID order summed the OrderPayment ledger AND wallet_amount_paid. A split-bill
        wallet payment lands in BOTH (StaffOrderPaymentView / OwnerWalletChargeView write
        a WALLET OrderPayment row AND bump wallet_amount_paid), so wallet money was counted
        twice — an order 60-wallet-paid of 100, after voiding a 10 item (new_total 90),
        computed 60+60=120 >= 90 and flipped to PAID, collecting 60 for a 90 order and
        writing off 30. Fixed by using the reconciling _order_collected() helper (each
        wallet payment counted once) minus what the void/comp just refunded.

  BUG 2 (MED — referral double-grant): the referral reward read the stale request-time
        referral_reward_given and issued both credits unconditionally, so two concurrent
        first orders double-credited referrer AND referee. Fixed with an atomic
        compare-and-set (extracted to _award_referral_reward): the referee credit is one
        UPDATE gated on referral_reward_given=False; the referrer is credited only when
        that UPDATE claimed the row (rowcount 1).

  BUG 3 (LOW — stale over-refund): refund_and_cancel_delivery_order re-reads the order
        under the lock into `locked` but refunded order.wallet_amount_paid from the
        pre-lock snapshot. A concurrent void/comp that decremented wallet_amount_paid in
        the window caused an over-refund. Fixed by refunding the post-lock value.
"""
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.models import Order
from menu.views import (
    StaffVoidOrderItemView,
    StaffCompOrderItemView,
    _award_referral_reward,
    refund_and_cancel_delivery_order,
)
from accounts.models import User


# ── Shared harness for the void/comp settle-predicate tests ────────────────────

class _FakeAtomic:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


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
    return u


def _item(item_id=901, dish_slug="burger", dish_name="Burger", qty=1,
          subtotal=Decimal("10.00"), is_voided=False, is_comped=False):
    it = MagicMock()
    it.id = item_id
    it.pk = item_id
    it.dish_slug = dish_slug
    it.dish_name = dish_name
    it.qty = qty
    it.unit_price = subtotal
    it.subtotal = subtotal
    it.options = []
    it.note = ""
    it.is_ready = False
    it.is_voided = is_voided
    it.is_comped = is_comped
    it.combo_components = []
    it.save = MagicMock()
    return it


def _wallet_payment(amount, method="wallet"):
    """A stand-in OrderPayment row. _order_collected reads .amount and compares .method
    against OrderPayment.Method.WALLET (patched to "wallet"); _staff_order_payload also
    serializes created_at / recorded_by_name / note, so provide those too."""
    return SimpleNamespace(
        amount=Decimal(str(amount)), method=method,
        created_at="2026-06-12T10:00:00+00:00", recorded_by_name="", note="",
    )


def _order(*, order_id=10, source="direct", commission_rate="0.00",
           commission_amount="0.00", status_val=Order.Status.PENDING,
           payment_status=Order.PaymentStatus.UNPAID, total=Decimal("100.00"),
           wallet_amount_paid=Decimal("0"), customer_id=None, points_earned=0,
           items=None, payment_rows=None):
    o = MagicMock()
    o.id = order_id
    o.pk = order_id
    o.order_number = "ORD-M001"
    o.source = source
    o.commission_rate_applied = Decimal(commission_rate)
    o.commission_amount = Decimal(commission_amount)
    o.status = status_val
    o.fulfillment_type = Order.FulfillmentType.TABLE
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

    # order.payments is NOT used by the fixed predicate (it now uses _order_collected /
    # OrderPayment.objects), but we still stub it with the WALLET row so a REGRESSION to
    # the old sum(order.payments)+wallet_amount_paid predicate would double-count and
    # visibly fail these tests.
    payments_qs = MagicMock()
    payments_qs.all.return_value = payment_rows or []
    o.payments = payments_qs
    return o


class _VoidCompSettleHarness(SimpleTestCase):
    """Drives the real StaffVoidOrderItemView / StaffCompOrderItemView with the DB
    collaborators mocked, controlling only what the settle predicate depends on:
    the locked order's recomputed total (via its item list), wallet_amount_paid, and
    the OrderPayment ledger _order_collected() reads."""

    view = None            # set by subclass
    is_comp = False        # comp CAS filters on is_comped as well

    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, order_id=10, item_id=901):
        path = "comp" if self.is_comp else "void"
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/{item_id}/{path}/",
            {"reason": "customer changed mind"}, format="json",
        )
        force_authenticate(req, user=_user())
        req.tenant = SimpleNamespace(id=1)
        return self.view(req, order_id=order_id, item_id=item_id)

    def _run(self, initial, locked, payment_rows):
        with patch("menu.views._can_void_order_item", return_value=True), \
                patch("menu.views._can_access_order", return_value=True), \
                patch("menu.views.transaction") as tx_mock, \
                patch("menu.views.Order.objects") as order_om, \
                patch("menu.views.OrderItem") as oi_mock, \
                patch("menu.views.Dish.objects") as dish_om, \
                patch("menu.views._broadcast_order_change"), \
                patch("menu.models.OrderPayment") as op_mock:
            tx_mock.atomic.return_value = _FakeAtomic()
            order_om.prefetch_related.return_value.filter.return_value.first.return_value = initial
            order_om.select_for_update.return_value.prefetch_related.return_value.get.return_value = locked
            order_om.filter.return_value.update.return_value = 1
            oi_mock.objects.filter.return_value.update.return_value = 1  # CAS won
            dish_om.select_for_update.return_value.filter.return_value = []
            op_mock.Method.WALLET = "wallet"
            op_mock.objects.filter.return_value = payment_rows
            return self._post(order_id=initial.id, item_id=901)


class VoidCaseBSettleTests(_VoidCompSettleHarness):
    view = staticmethod(StaffVoidOrderItemView.as_view())
    is_comp = False

    def test_partial_wallet_payment_not_double_counted_stays_unpaid(self):
        """The core HIGH regression. UNPAID order, 60 wallet-paid of 100 with a WALLET
        OrderPayment ledger row of 60 (StaffOrderPaymentView writes BOTH signals). Void a
        10 line → new_total 90. _order_collected counts the 60 ONCE, so 60 < 90 and the
        order is NOT flipped to PAID. The old predicate computed 60+60=120 >= 90 and
        silently wrote off 30."""
        to_void = _item(item_id=901, subtotal=Decimal("10.00"))
        initial = _order(items=[to_void], payment_status=Order.PaymentStatus.UNPAID,
                         wallet_amount_paid=Decimal("60.00"), customer_id=7)
        locked = _order(
            wallet_amount_paid=Decimal("60.00"), customer_id=7,
            payment_status=Order.PaymentStatus.UNPAID,
            items=[_item(item_id=901, subtotal=Decimal("10.00"), is_voided=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("90.00"))],
            payment_rows=[_wallet_payment("60.00")],
        )
        resp = self._run(initial, locked, payment_rows=[_wallet_payment("60.00")])
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        # new_total after recompute = 90; collected (wallet counted once) = 60 < 90.
        self.assertEqual(locked.total, Decimal("90.00"))
        locked.mark_paid.assert_not_called()
        self.assertNotEqual(locked.payment_status, Order.PaymentStatus.PAID)

    def test_fully_collected_order_still_flips_to_paid(self):
        """The fix must not OVER-correct: an order genuinely covered after the void must
        still auto-settle. UNPAID order with a WALLET row 60 (== wallet_amount_paid 60)
        plus a CASH row 30 = 90 collected; void a 10 line → new_total 90 → PAID.
        _order_collected reconciles to 60 (wallet once) + 30 (cash) = 90, never 150."""
        to_void = _item(item_id=901, subtotal=Decimal("10.00"))
        initial = _order(items=[to_void], payment_status=Order.PaymentStatus.UNPAID,
                         wallet_amount_paid=Decimal("60.00"), customer_id=7)
        rows = [_wallet_payment("60.00"), _wallet_payment("30.00", method="cash")]
        locked = _order(
            wallet_amount_paid=Decimal("60.00"), customer_id=7,
            payment_status=Order.PaymentStatus.UNPAID,
            items=[_item(item_id=901, subtotal=Decimal("10.00"), is_voided=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("90.00"))],
            payment_rows=rows,
        )
        resp = self._run(initial, locked, payment_rows=rows)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(locked.total, Decimal("90.00"))
        locked.mark_paid.assert_called_once_with(save=False)


class CompCaseBSettleTests(_VoidCompSettleHarness):
    view = staticmethod(StaffCompOrderItemView.as_view())
    is_comp = True

    def test_partial_wallet_payment_not_double_counted_stays_unpaid(self):
        """Identical HIGH regression for the comp path (shared bug, shared fix)."""
        to_comp = _item(item_id=901, subtotal=Decimal("10.00"))
        initial = _order(items=[to_comp], payment_status=Order.PaymentStatus.UNPAID,
                         wallet_amount_paid=Decimal("60.00"), customer_id=7)
        locked = _order(
            wallet_amount_paid=Decimal("60.00"), customer_id=7,
            payment_status=Order.PaymentStatus.UNPAID,
            items=[_item(item_id=901, subtotal=Decimal("10.00"), is_comped=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("90.00"))],
            payment_rows=[_wallet_payment("60.00")],
        )
        resp = self._run(initial, locked, payment_rows=[_wallet_payment("60.00")])
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(locked.total, Decimal("90.00"))
        locked.mark_paid.assert_not_called()
        self.assertNotEqual(locked.payment_status, Order.PaymentStatus.PAID)

    def test_fully_collected_order_still_flips_to_paid(self):
        to_comp = _item(item_id=901, subtotal=Decimal("10.00"))
        initial = _order(items=[to_comp], payment_status=Order.PaymentStatus.UNPAID,
                         wallet_amount_paid=Decimal("60.00"), customer_id=7)
        rows = [_wallet_payment("60.00"), _wallet_payment("30.00", method="cash")]
        locked = _order(
            wallet_amount_paid=Decimal("60.00"), customer_id=7,
            payment_status=Order.PaymentStatus.UNPAID,
            items=[_item(item_id=901, subtotal=Decimal("10.00"), is_comped=True),
                   _item(item_id=902, dish_slug="fries", subtotal=Decimal("90.00"))],
            payment_rows=rows,
        )
        resp = self._run(initial, locked, payment_rows=rows)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(locked.total, Decimal("90.00"))
        locked.mark_paid.assert_called_once_with(save=False)


# ── BUG 2: referral reward compare-and-set ─────────────────────────────────────

class AwardReferralRewardTests(SimpleTestCase):
    def _profile(self, enabled=True, pts=100):
        return SimpleNamespace(referral_enabled=enabled, referral_reward_points=pts)

    def _customer(self, pk=1, referred_by_id=2, reward_given=False):
        return SimpleNamespace(pk=pk, referred_by_id=referred_by_id,
                               referral_reward_given=reward_given)

    def test_referrer_credited_only_when_cas_claims(self):
        """The winning first order: the referee CAS UPDATE returns 1 (claimed), so the
        referrer is ALSO credited. The referee filter must carry the
        referral_reward_given=False guard, and the referrer filter targets referred_by_id."""
        with patch("accounts.models.Customer") as CustM:
            filt = CustM.objects.filter
            filt.return_value.update.side_effect = [1, 1]  # referee claims, referrer credited
            _award_referral_reward(self._profile(), self._customer(pk=1, referred_by_id=2))

            self.assertEqual(filt.call_count, 2)  # referee CAS + referrer credit
            referee_kwargs = filt.call_args_list[0].kwargs
            self.assertEqual(referee_kwargs.get("pk"), 1)
            self.assertEqual(referee_kwargs.get("referral_reward_given"), False)
            referrer_kwargs = filt.call_args_list[1].kwargs
            self.assertEqual(referrer_kwargs.get("pk"), 2)

    def test_referrer_not_credited_when_cas_loses(self):
        """A concurrent/second first order (or a replay): the referee CAS UPDATE matches
        0 rows because a peer already flipped referral_reward_given True. The referrer
        must therefore NOT be credited — no second call to filter()."""
        with patch("accounts.models.Customer") as CustM:
            filt = CustM.objects.filter
            filt.return_value.update.side_effect = [0]  # CAS lost — already claimed
            _award_referral_reward(self._profile(), self._customer(pk=1, referred_by_id=2))

            self.assertEqual(filt.call_count, 1)  # ONLY the CAS; referrer credit skipped

    def test_disabled_referral_grants_nothing(self):
        with patch("accounts.models.Customer") as CustM:
            _award_referral_reward(self._profile(enabled=False), self._customer())
            CustM.objects.filter.assert_not_called()

    def test_no_referrer_grants_nothing(self):
        with patch("accounts.models.Customer") as CustM:
            _award_referral_reward(self._profile(),
                                   self._customer(referred_by_id=None))
            CustM.objects.filter.assert_not_called()

    def test_already_rewarded_snapshot_grants_nothing(self):
        with patch("accounts.models.Customer") as CustM:
            _award_referral_reward(self._profile(),
                                   self._customer(reward_given=True))
            CustM.objects.filter.assert_not_called()


# ── BUG 3: cancel-refund reads wallet_amount_paid from the LOCKED row ──────────

def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


@contextmanager
def _noop_cm(*args, **kwargs):
    yield


@patch("menu.views.Order")
@patch("django.db.transaction.atomic", lambda *a, **k: _passthrough_cm())
@patch("accounts.models.DeliveryJob")
@patch("accounts.delivery_service.cancel_delivery_job_for_order")
@patch("menu.views._broadcast_order_change")
@patch("menu.views._restock_cancelled_order")
@patch("menu.views._reverse_loyalty_for_cancelled_order")
@patch("menu.views._refund_wallet_for_cancelled_order")
class RefundReadsLockedWalletTests(SimpleTestCase):
    def _wire_lock(self, order_m, *, locked_status, locked_wallet):
        order_m.Status.CANCELLED = Order.Status.CANCELLED
        locked = MagicMock()
        locked.status = locked_status
        locked.wallet_amount_paid = locked_wallet
        (order_m.objects.select_for_update.return_value
            .filter.return_value.first.return_value) = locked
        return locked

    def _order(self, *, status, wallet):
        o = MagicMock()
        o.status = status
        o.order_number = "ORD-1"
        o.payment_status = "unpaid"
        o.wallet_amount_paid = wallet
        return o

    def test_refund_uses_post_lock_wallet_amount_not_stale_snapshot(
        self, refund_m, loyalty_m, restock_m, broadcast_m, cancel_job_m, dj_m, order_m
    ):
        """BUG 3 regression. The passed `order` was loaded BEFORE the lock with
        wallet_amount_paid=60; a concurrent void/comp decremented it to 30 in the window,
        so the freshly-locked row reads 30. The refund MUST use 30 — refunding the stale
        60 over-refunds by 30 (the idempotency key blocks a double refund, not a wrong
        amount)."""
        locked = self._wire_lock(order_m, locked_status="pending",
                                 locked_wallet=Decimal("30.00"))
        order = self._order(status="pending", wallet=Decimal("60.00"))  # stale, higher

        seen = {}

        def _capture(o, tenant_id=None):
            seen["wallet_amount_paid"] = o.wallet_amount_paid

        refund_m.side_effect = _capture

        result = refund_and_cancel_delivery_order(order, tenant_id=1)

        self.assertTrue(result)
        # The amount the refund saw is the POST-lock value, not the pre-lock 60.
        self.assertEqual(seen["wallet_amount_paid"], Decimal("30.00"))
        self.assertEqual(order.wallet_amount_paid, Decimal("30.00"))
        refund_m.assert_called_once_with(order, tenant_id=1)
