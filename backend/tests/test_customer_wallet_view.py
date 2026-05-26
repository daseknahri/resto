"""
Tests for CustomerWalletView
GET /api/customer/wallet/

All tests are unit-level (SimpleTestCase + mocks — no real DB or session store).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerWalletView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    """Return a minimal session-like object."""
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    sess.pop = lambda key, default=None: data.pop(key, default)
    return sess


def _make_customer(customer_id=1, balance="25.50"):
    c = MagicMock()
    c.pk = customer_id
    c.id = customer_id
    c.wallet_balance = Decimal(balance)
    return c


def _make_tx(tx_id=1, tx_type="topup", amount="10.00", reference="", note="Gift",
             created_at="2026-05-01T10:00:00+00:00"):
    tx = MagicMock()
    tx.id = tx_id
    tx.type = tx_type
    tx.amount = amount
    tx.reference = reference
    tx.note = note
    tx_created = MagicMock()
    tx_created.isoformat.return_value = created_at
    tx.created_at = tx_created
    return tx


# ── Tests ─────────────────────────────────────────────────────────────────────

class CustomerWalletViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/customer/wallet/")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_no_session_returns_401(self):
        """Unauthenticated request (no customer_id in session) must be rejected."""
        resp = self._get(session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_session_customer_not_found_returns_404(self):
        """If session has a customer_id that no longer exists in the DB, return 404."""
        from accounts.models import Customer as CustomerModel
        import accounts.views as _av
        with patch.object(_av.Customer, "objects") as mock_objs:
            mock_objs.get.side_effect = CustomerModel.DoesNotExist
            resp = self._get(session=_session(customer_id=999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Happy path ─────────────────────────────────────────────────────────────

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_returns_200_with_balance_and_transactions(self, mock_cust_objs, mock_tx_objs):
        """Happy-path: authenticated customer gets balance + transaction list."""
        customer = _make_customer(customer_id=5, balance="50.00")
        mock_cust_objs.get.return_value = customer

        tx = _make_tx(tx_id=1, tx_type="topup", amount="50.00", note="Welcome bonus")
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get(session=_session(customer_id=5))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("balance", resp.data)
        self.assertIn("transactions", resp.data)
        self.assertEqual(resp.data["balance"], "50.00")
        self.assertIsInstance(resp.data["transactions"], list)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_transaction_has_required_fields(self, mock_cust_objs, mock_tx_objs):
        """Each transaction row must include id, type, amount, reference, note, created_at."""
        customer = _make_customer(customer_id=3, balance="15.00")
        mock_cust_objs.get.return_value = customer

        tx = _make_tx(tx_id=7, tx_type="payment", amount="5.00",
                      reference="ORD-ABC123", note="Order payment")
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get(session=_session(customer_id=3))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["transactions"]), 1)
        first = resp.data["transactions"][0]
        for field in ("id", "type", "amount", "reference", "note", "created_at"):
            self.assertIn(field, first, msg=f"Missing field: {field}")
        self.assertEqual(first["id"], 7)
        self.assertEqual(first["type"], "payment")
        self.assertEqual(first["reference"], "ORD-ABC123")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_empty_transaction_history_returns_empty_list(self, mock_cust_objs, mock_tx_objs):
        """Customer with no transactions gets an empty list, not an error."""
        customer = _make_customer(customer_id=2, balance="0.00")
        mock_cust_objs.get.return_value = customer

        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = []

        resp = self._get(session=_session(customer_id=2))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["transactions"], [])
        self.assertEqual(resp.data["balance"], "0.00")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_balance_serialized_as_string(self, mock_cust_objs, mock_tx_objs):
        """Wallet balance must be returned as a string to preserve decimal precision."""
        customer = _make_customer(customer_id=4, balance="123.45")
        mock_cust_objs.get.return_value = customer

        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = []

        resp = self._get(session=_session(customer_id=4))
        self.assertIsInstance(resp.data["balance"], str)
        self.assertEqual(resp.data["balance"], "123.45")
