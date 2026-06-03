"""
Unit tests for three helpers that mix pure logic with DB calls:

  menu/views._refund_wallet_for_cancelled_order(order)
    Credits the customer's wallet when a wallet-paid order is cancelled.
    Idempotent — checks for an existing REFUND transaction first.

  sales/views._log_reservation_timeline_event(...)
    Creates a ReservationTimelineEvent record; resolves actor_id from the
    authenticated flag on the actor object.

  accounts/views._resolve_customer_from_request(request)
    Returns (Customer, None) or (None, Response) from session data.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from menu.views import _refund_wallet_for_cancelled_order, _sync_charged_request_bills
from sales.views import _log_reservation_timeline_event
from accounts.views import _resolve_customer_from_request


# ══════════════════════════════════════════════════════════════════════════════
# _refund_wallet_for_cancelled_order
# ══════════════════════════════════════════════════════════════════════════════

def _order(
    *,
    order_number="ORD-001",
    customer_id=42,
    wallet_amount_paid="10.00",
):
    return SimpleNamespace(
        order_number=order_number,
        customer_id=customer_id,
        wallet_amount_paid=wallet_amount_paid,
    )


class RefundWalletTests(SimpleTestCase):
    """_refund_wallet_for_cancelled_order: credits wallet; idempotent."""

    # ── early exits ──────────────────────────────────────────────────────────
    def test_no_customer_id_returns_immediately(self):
        """No DB access when customer_id is None."""
        order = _order(customer_id=None)
        with patch("accounts.models.WalletTransaction") as mock_wtm:
            _refund_wallet_for_cancelled_order(order)
        mock_wtm.objects.filter.assert_not_called()

    def test_zero_customer_id_returns_immediately(self):
        """customer_id=0 is falsy → early return."""
        order = _order(customer_id=0)
        with patch("accounts.models.WalletTransaction") as mock_wtm:
            _refund_wallet_for_cancelled_order(order)
        mock_wtm.objects.filter.assert_not_called()

    def test_zero_wallet_amount_returns_immediately(self):
        order = _order(wallet_amount_paid="0.00")
        with patch("accounts.models.WalletTransaction") as mock_wtm:
            _refund_wallet_for_cancelled_order(order)
        mock_wtm.objects.filter.assert_not_called()

    def test_none_wallet_amount_returns_immediately(self):
        """None is treated as '0' via Decimal(str(None or '0')) → 0 → early return."""
        order = _order(wallet_amount_paid=None)
        with patch("accounts.models.WalletTransaction") as mock_wtm:
            _refund_wallet_for_cancelled_order(order)
        mock_wtm.objects.filter.assert_not_called()

    def test_negative_wallet_amount_returns_immediately(self):
        order = _order(wallet_amount_paid="-5.00")
        with patch("accounts.models.WalletTransaction") as mock_wtm:
            _refund_wallet_for_cancelled_order(order)
        mock_wtm.objects.filter.assert_not_called()

    # ── idempotency guard ────────────────────────────────────────────────────
    def test_existing_refund_skips_create(self):
        """A prior REFUND transaction → nothing written."""
        order = _order()
        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("django.db.transaction.atomic"):
            mock_wtm.objects.filter.return_value.exists.return_value = True
            _refund_wallet_for_cancelled_order(order)
        mock_cust.objects.select_for_update.assert_not_called()
        mock_wtm.objects.create.assert_not_called()

    def test_concurrent_refund_caught_under_lock(self):
        """The fast-path check misses (False) but the under-lock re-check (True) must
        prevent a second refund — closing the double-cancel race."""
        order = _order(customer_id=5, wallet_amount_paid="10.00")
        mock_customer = SimpleNamespace(wallet_balance=Decimal("0.00"), updated_at=None)
        mock_customer.save = MagicMock()
        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("django.db.transaction.atomic"):
            # First .exists() (fast path) → False; second (under lock) → True.
            mock_wtm.objects.filter.return_value.exists.side_effect = [False, True]
            mock_cust.objects.select_for_update.return_value.get.return_value = mock_customer
            _refund_wallet_for_cancelled_order(order)
        # The lock was acquired (fast path missed) but nothing was written.
        mock_cust.objects.select_for_update.return_value.get.assert_called_once_with(pk=5)
        mock_wtm.objects.create.assert_not_called()
        mock_customer.save.assert_not_called()

    def test_idempotency_filter_uses_customer_id_type_and_reference(self):
        """Filter kwargs: customer_id, type=REFUND, reference=order_number."""
        order = _order(order_number="ORD-IDEM", customer_id=7)
        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer"), \
             patch("django.db.transaction.atomic"):
            mock_wtm.objects.filter.return_value.exists.return_value = True
            _refund_wallet_for_cancelled_order(order)
        kw = mock_wtm.objects.filter.call_args[1]
        self.assertEqual(kw["customer_id"], 7)
        self.assertEqual(kw["reference"], "ORD-IDEM")
        self.assertEqual(kw["type"], mock_wtm.Type.REFUND)

    # ── successful refund ────────────────────────────────────────────────────
    def test_new_refund_increments_customer_balance(self):
        """Balance is updated by the refund amount."""
        order = _order(customer_id=5, wallet_amount_paid="15.50")
        mock_customer = SimpleNamespace(wallet_balance=Decimal("50.00"), updated_at=None)
        mock_customer.save = MagicMock()

        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("django.db.transaction.atomic"):
            mock_wtm.objects.filter.return_value.exists.return_value = False
            mock_cust.objects.select_for_update.return_value.get.return_value = mock_customer
            _refund_wallet_for_cancelled_order(order)

        self.assertEqual(mock_customer.wallet_balance, Decimal("65.50"))
        mock_customer.save.assert_called_once()

    def test_new_refund_creates_wallet_transaction(self):
        """A REFUND WalletTransaction is created with correct fields."""
        order = _order(order_number="ORD-XYZ", customer_id=5, wallet_amount_paid="20.00")
        mock_customer = SimpleNamespace(wallet_balance=Decimal("0.00"), updated_at=None)
        mock_customer.save = MagicMock()

        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("django.db.transaction.atomic"):
            mock_wtm.objects.filter.return_value.exists.return_value = False
            mock_cust.objects.select_for_update.return_value.get.return_value = mock_customer
            _refund_wallet_for_cancelled_order(order)

        mock_wtm.objects.create.assert_called_once()
        kw = mock_wtm.objects.create.call_args[1]
        self.assertEqual(kw["amount"], Decimal("20.00"))
        self.assertEqual(kw["reference"], "ORD-XYZ")
        self.assertEqual(kw["type"], mock_wtm.Type.REFUND)

    def test_new_refund_get_uses_customer_id(self):
        """select_for_update().get() is called with the order's customer_id."""
        order = _order(customer_id=99)
        mock_customer = SimpleNamespace(wallet_balance=Decimal("10.00"), updated_at=None)
        mock_customer.save = MagicMock()

        with patch("accounts.models.WalletTransaction") as mock_wtm, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("django.db.transaction.atomic"):
            mock_wtm.objects.filter.return_value.exists.return_value = False
            mock_cust.objects.select_for_update.return_value.get.return_value = mock_customer
            _refund_wallet_for_cancelled_order(order)

        mock_cust.objects.select_for_update.return_value.get.assert_called_once_with(pk=99)


# ══════════════════════════════════════════════════════════════════════════════
# _sync_charged_request_bills
# ══════════════════════════════════════════════════════════════════════════════

class SyncChargedRequestBillsTests(SimpleTestCase):
    """Approved charge requests are applied to their Order bills exactly once."""

    def test_claims_and_applies_each_request_once(self):
        with patch("accounts.models.WalletChargeRequest.objects") as mock_wcr, \
             patch("menu.views.Order.objects") as mock_order:
            mock_wcr.filter.return_value.values_list.return_value = [(1, "ORD1", Decimal("100.00"))]
            mock_wcr.filter.return_value.update.return_value = 1  # claim succeeds
            applied = _sync_charged_request_bills(3, ["ORD1"])
        self.assertEqual(applied, {"ORD1": Decimal("100.00")})
        mock_order.filter.return_value.update.assert_called_once()

    def test_skips_when_claim_lost_to_concurrent_caller(self):
        with patch("accounts.models.WalletChargeRequest.objects") as mock_wcr, \
             patch("menu.views.Order.objects") as mock_order:
            mock_wcr.filter.return_value.values_list.return_value = [(1, "ORD1", Decimal("100.00"))]
            mock_wcr.filter.return_value.update.return_value = 0  # another caller already claimed it
            applied = _sync_charged_request_bills(3, ["ORD1"])
        self.assertEqual(applied, {})
        mock_order.filter.return_value.update.assert_not_called()

    def test_no_order_numbers_is_a_noop(self):
        with patch("accounts.models.WalletChargeRequest.objects") as mock_wcr:
            applied = _sync_charged_request_bills(3, [])
        self.assertEqual(applied, {})
        mock_wcr.filter.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# _log_reservation_timeline_event
# ══════════════════════════════════════════════════════════════════════════════

def _actor(*, is_authenticated=True, pk=5):
    return SimpleNamespace(is_authenticated=is_authenticated, pk=pk)


def _lead(id=10):
    return SimpleNamespace(id=id)


def _tenant_obj(id=1):
    return SimpleNamespace(id=id)


class LogReservationTimelineEventTests(SimpleTestCase):
    """_log_reservation_timeline_event: creates a timeline event with correct actor_id."""

    # ── actor_id resolution ──────────────────────────────────────────────────
    def test_authenticated_actor_uses_pk(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(is_authenticated=True, pk=42),
                action="status_change",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["actor_id"], 42)

    def test_unauthenticated_actor_gives_none_actor_id(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(is_authenticated=False, pk=99),
                action="status_change",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertIsNone(kw["actor_id"])

    def test_actor_without_is_authenticated_gives_none_actor_id(self):
        """getattr(actor, 'is_authenticated', False) → False when missing."""
        actor = SimpleNamespace(pk=7)  # no is_authenticated attribute
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=actor,
                action="note_added",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertIsNone(kw["actor_id"])

    def test_actor_with_no_pk_gives_none_actor_id(self):
        """Authenticated actor without pk → actor_id=None via getattr default."""
        actor = SimpleNamespace(is_authenticated=True)  # no pk attribute
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=actor,
                action="note_added",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertIsNone(kw["actor_id"])

    # ── create call fields ───────────────────────────────────────────────────
    def test_lead_id_and_tenant_id_passed_correctly(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(id=55),
                tenant=_tenant_obj(id=3),
                actor=_actor(),
                action="reminder_sent",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["lead_id"], 55)
        self.assertEqual(kw["tenant_id"], 3)

    def test_action_passed_to_create(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(),
                action="reminder_sent",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["action"], "reminder_sent")

    def test_none_previous_status_stored_as_empty_string(self):
        """previous_status=None → '' (falsy coercion: None or '')."""
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(),
                action="status_change",
                previous_status=None,
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["previous_status"], "")

    def test_none_new_status_stored_as_empty_string(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(),
                action="status_change",
                new_status=None,
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["new_status"], "")

    def test_note_passed_through(self):
        with patch("sales.views.ReservationTimelineEvent") as mock_rte:
            _log_reservation_timeline_event(
                lead=_lead(),
                tenant=_tenant_obj(),
                actor=_actor(),
                action="note_added",
                note="Arrived 10 min late.",
            )
        kw = mock_rte.objects.create.call_args[1]
        self.assertEqual(kw["note"], "Arrived 10 min late.")


# ══════════════════════════════════════════════════════════════════════════════
# _resolve_customer_from_request
# ══════════════════════════════════════════════════════════════════════════════

def _request_with_session(customer_id=None):
    session = {"customer_id": customer_id} if customer_id else {}
    return SimpleNamespace(session=session)


def _request_no_session():
    return SimpleNamespace()  # no session attribute at all


class ResolveCustomerFromRequestTests(SimpleTestCase):
    """_resolve_customer_from_request: returns (customer, None) or (None, error response)."""

    # ── missing / no session ─────────────────────────────────────────────────
    def test_no_session_attribute_returns_none_and_401(self):
        customer, err = _resolve_customer_from_request(_request_no_session())
        self.assertIsNone(customer)
        self.assertEqual(err.status_code, 401)

    def test_session_without_customer_id_returns_none_and_401(self):
        req = _request_with_session(customer_id=None)
        customer, err = _resolve_customer_from_request(req)
        self.assertIsNone(customer)
        self.assertEqual(err.status_code, 401)

    def test_session_with_zero_customer_id_returns_401(self):
        """customer_id=0 is falsy → treated as missing."""
        req = SimpleNamespace(session={"customer_id": 0})
        customer, err = _resolve_customer_from_request(req)
        self.assertIsNone(customer)
        self.assertEqual(err.status_code, 401)

    # ── customer found ────────────────────────────────────────────────────────
    def test_valid_customer_id_returns_customer_and_none_error(self):
        mock_customer = SimpleNamespace(pk=5, email="a@b.com")
        with patch("accounts.views.Customer") as mock_cust_cls:
            mock_cust_cls.objects.get.return_value = mock_customer
            customer, err = _resolve_customer_from_request(_request_with_session(customer_id=5))
        self.assertEqual(customer, mock_customer)
        self.assertIsNone(err)

    def test_get_called_with_correct_pk(self):
        mock_customer = SimpleNamespace(pk=7)
        with patch("accounts.views.Customer") as mock_cust_cls:
            mock_cust_cls.objects.get.return_value = mock_customer
            _resolve_customer_from_request(_request_with_session(customer_id=7))
        mock_cust_cls.objects.get.assert_called_once_with(pk=7)

    # ── customer not found ────────────────────────────────────────────────────
    def test_customer_does_not_exist_returns_none_and_404(self):
        with patch("accounts.views.Customer") as mock_cust_cls:
            mock_cust_cls.DoesNotExist = Exception
            mock_cust_cls.objects.get.side_effect = mock_cust_cls.DoesNotExist("gone")
            customer, err = _resolve_customer_from_request(_request_with_session(customer_id=99))
        self.assertIsNone(customer)
        self.assertEqual(err.status_code, 404)
