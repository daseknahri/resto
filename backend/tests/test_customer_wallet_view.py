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

    # ── ?vertical= filter ───────────────────────────────────────────────────────

    def _get_with_vertical(self, vertical, session=None):
        req = self.factory.get("/api/customer/wallet/", {"vertical": vertical})
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_valid_vertical_scopes_transaction_list(self, mock_cust_objs, mock_tx_objs):
        """?vertical=food applies a secondary .filter(vertical='food') on the tx list."""
        customer = _make_customer(customer_id=8, balance="40.00")
        mock_cust_objs.get.return_value = customer

        base_qs = mock_tx_objs.filter.return_value  # .filter(customer=...)
        tx = _make_tx(tx_id=11, tx_type="payment", amount="12.00")
        base_qs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get_with_vertical("food", session=_session(customer_id=8))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The second .filter (on the customer-scoped queryset) must carry vertical=.
        base_qs.filter.assert_any_call(vertical="food")
        self.assertEqual(len(resp.data["transactions"]), 1)
        self.assertEqual(resp.data["transactions"][0]["id"], 11)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_vertical_filter_is_case_insensitive(self, mock_cust_objs, mock_tx_objs):
        """?vertical=FOOD is normalised to lowercase before filtering."""
        customer = _make_customer(customer_id=9, balance="40.00")
        mock_cust_objs.get.return_value = customer

        base_qs = mock_tx_objs.filter.return_value
        base_qs.filter.return_value.order_by.return_value.__getitem__.return_value = []

        resp = self._get_with_vertical("FOOD", session=_session(customer_id=9))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        base_qs.filter.assert_any_call(vertical="food")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_invalid_vertical_is_ignored(self, mock_cust_objs, mock_tx_objs):
        """An unknown ?vertical= value falls back to the unfiltered list (no extra filter)."""
        customer = _make_customer(customer_id=10, balance="40.00")
        mock_cust_objs.get.return_value = customer

        base_qs = mock_tx_objs.filter.return_value
        base_qs.order_by.return_value.__getitem__.return_value = []

        resp = self._get_with_vertical("not-a-vertical", session=_session(customer_id=10))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # No secondary vertical filter should have been applied to the tx list.
        for call in base_qs.filter.call_args_list:
            self.assertNotIn("vertical", call.kwargs)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_blank_vertical_returns_full_list(self, mock_cust_objs, mock_tx_objs):
        """A blank ?vertical= must not scope the list (treated as 'all')."""
        customer = _make_customer(customer_id=12, balance="40.00")
        mock_cust_objs.get.return_value = customer

        base_qs = mock_tx_objs.filter.return_value
        base_qs.order_by.return_value.__getitem__.return_value = []

        resp = self._get_with_vertical("", session=_session(customer_id=12))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for call in base_qs.filter.call_args_list:
            self.assertNotIn("vertical", call.kwargs)

    # ── B8: ?page= pagination ────────────────────────────────────────────────

    def _get_with_page(self, page, session=None):
        req = self.factory.get("/api/customer/wallet/", {"page": page})
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_response_includes_page_and_has_more(self, mock_cust_objs, mock_tx_objs):
        """The response must include page/has_more alongside the existing shape
        (balance, transactions, etc. all still present)."""
        customer = _make_customer(customer_id=20, balance="40.00")
        mock_cust_objs.get.return_value = customer

        tx = _make_tx(tx_id=1)
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get(session=_session(customer_id=20))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("has_more", resp.data)
        self.assertIn("page", resp.data)
        self.assertEqual(resp.data["page"], 1)
        self.assertFalse(resp.data["has_more"])
        # Existing response shape (balance etc.) unchanged.
        self.assertIn("balance", resp.data)
        self.assertIn("transactions", resp.data)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_has_more_true_when_extra_row_returned(self, mock_cust_objs, mock_tx_objs):
        """PAGE_SIZE=20 — if the slice returns 21 rows, has_more=True and only
        20 are surfaced in the transactions list."""
        customer = _make_customer(customer_id=21, balance="40.00")
        mock_cust_objs.get.return_value = customer

        txs = [_make_tx(tx_id=i) for i in range(21)]
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = txs

        resp = self._get(session=_session(customer_id=21))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(len(resp.data["transactions"]), 20)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_page_param_is_echoed_back(self, mock_cust_objs, mock_tx_objs):
        customer = _make_customer(customer_id=22, balance="40.00")
        mock_cust_objs.get.return_value = customer

        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = []

        resp = self._get_with_page(3, session=_session(customer_id=22))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["page"], 3)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_invalid_page_param_falls_back_to_1(self, mock_cust_objs, mock_tx_objs):
        customer = _make_customer(customer_id=23, balance="40.00")
        mock_cust_objs.get.return_value = customer

        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = []

        resp = self._get_with_page("not-a-number", session=_session(customer_id=23))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["page"], 1)
