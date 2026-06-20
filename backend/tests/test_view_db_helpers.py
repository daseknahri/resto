"""
Unit tests for three helpers that mix pure logic with DB calls:

  menu/views._refund_wallet_for_cancelled_order(order)
    Credits the customer's wallet when a wallet-paid order is cancelled.
    Routes through wallet_service.credit_wallet with a SCHEMA-NAMESPACED idempotency
    key (f"cancelrefund:{schema}:{order.id}"); credit_wallet owns the lock + the
    idempotent replay (OPS-5h: the old manual balance write + order_number-based
    _already_refunded guard could silently skip a cross-tenant refund).

  sales/views._log_reservation_timeline_event(...)
    Creates a ReservationTimelineEvent record; resolves actor_id from the
    authenticated flag on the actor object.

  accounts/views._resolve_customer_from_request(request)
    Returns (Customer, None) or (None, Response) from session data.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.views import _refund_wallet_for_cancelled_order, _sync_charged_request_bills
from sales.views import _log_reservation_timeline_event
from accounts.views import _resolve_customer_from_request


# ══════════════════════════════════════════════════════════════════════════════
# _refund_wallet_for_cancelled_order
# ══════════════════════════════════════════════════════════════════════════════

def _order(
    *,
    order_id=10,
    order_number="ORD-001",
    customer_id=42,
    wallet_amount_paid="10.00",
):
    return SimpleNamespace(
        id=order_id,
        order_number=order_number,
        customer_id=customer_id,
        wallet_amount_paid=wallet_amount_paid,
    )


class RefundWalletTests(SimpleTestCase):
    """_refund_wallet_for_cancelled_order: delegates to credit_wallet (locked + idempotent)."""

    # ── early exits (no money path touched at all) ─────────────────────────────
    def test_no_customer_id_returns_immediately(self):
        """No credit_wallet call when customer_id is None."""
        order = _order(customer_id=None)
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order)
        mock_cw.assert_not_called()

    def test_zero_customer_id_returns_immediately(self):
        """customer_id=0 is falsy → early return."""
        order = _order(customer_id=0)
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order)
        mock_cw.assert_not_called()

    def test_zero_wallet_amount_returns_immediately(self):
        order = _order(wallet_amount_paid="0.00")
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order)
        mock_cw.assert_not_called()

    def test_none_wallet_amount_returns_immediately(self):
        """None is treated as '0' via Decimal(str(None or '0')) → 0 → early return."""
        order = _order(wallet_amount_paid=None)
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order)
        mock_cw.assert_not_called()

    def test_negative_wallet_amount_returns_immediately(self):
        order = _order(wallet_amount_paid="-5.00")
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order)
        mock_cw.assert_not_called()

    # ── delegates to the locked, idempotent money path ─────────────────────────
    def test_routes_through_credit_wallet_not_direct_balance_write(self):
        """The refund goes through credit_wallet; it never touches Customer directly."""
        order = _order(customer_id=5, wallet_amount_paid="15.50")
        with patch("accounts.wallet_service.credit_wallet") as mock_cw, \
             patch("accounts.models.Customer") as mock_cust:
            _refund_wallet_for_cancelled_order(order, tenant_id=3)
        mock_cw.assert_called_once()
        # No direct balance mutation: the view never locks/loads Customer itself anymore.
        mock_cust.objects.select_for_update.assert_not_called()
        mock_cust.objects.get.assert_not_called()

    def test_idempotency_key_is_schema_namespaced_on_order_id(self):
        """Key = f"cancelrefund:{schema}:{order.id}" — order.id (tenant-schema PK) + the
        schema prefix make it globally unique, so a cross-tenant order_number collision
        can't silently skip a legit refund."""
        from django.db import connection
        order = _order(order_id=77, order_number="ORD-IDEM", customer_id=7)
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order, tenant_id=3)
        key = mock_cw.call_args.kwargs["idempotency_key"]
        self.assertEqual(key, f"cancelrefund:{connection.schema_name}:77")
        self.assertIn(connection.schema_name, key)

    def test_credit_wallet_called_with_refund_ledger_kwargs(self):
        """type=REFUND, tenant_id, reference=order_number, note + require_verified=False are
        all forwarded so the Z-report/refund queries and the ledger semantics survive."""
        from accounts.models import WalletTransaction
        order = _order(order_id=10, order_number="ORD-XYZ", customer_id=5,
                       wallet_amount_paid="20.00")
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order, tenant_id=9)
        args, kw = mock_cw.call_args
        self.assertEqual(args[0], 5)                 # customer_id (positional)
        self.assertEqual(args[1], Decimal("20.00"))  # amount (positional)
        self.assertEqual(kw["tx_type"], WalletTransaction.Type.REFUND)
        self.assertEqual(kw["tenant_id"], 9)         # tenant_id MUST be set for refund reports
        self.assertEqual(kw["reference"], "ORD-XYZ")
        self.assertEqual(kw["note"], "Refund for cancelled order")
        self.assertFalse(kw["require_verified"])     # system-originated refund

    def test_credit_wallet_uses_orders_customer_id(self):
        """The credit targets the order's customer_id."""
        order = _order(customer_id=99)
        with patch("accounts.wallet_service.credit_wallet") as mock_cw:
            _refund_wallet_for_cancelled_order(order, tenant_id=1)
        self.assertEqual(mock_cw.call_args.args[0], 99)


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
