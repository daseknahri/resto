"""
Tests for owner wallet views:
  - OwnerWalletTopupView    POST /api/owner/wallet/topup/
  - OwnerWalletHistoryView  GET  /api/owner/wallet/history/<customer_id>/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerWalletTopupView, OwnerWalletHistoryView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _outsider(tenant_id=99):
    """User from a different tenant (id=99) vs the request tenant (id=1)."""
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_customer(customer_id=42, wallet_balance=Decimal("50.00")):
    c = MagicMock()
    c.id = customer_id
    c.wallet_balance = wallet_balance
    c.save = MagicMock()
    return c


def _make_tx(tx_id=1, tx_type="topup", amount="10.00", note="Owner credit", reference="", created_at="2026-05-01T10:00:00+00:00"):
    tx = MagicMock()
    tx.id = tx_id
    tx.type = tx_type
    tx.amount = amount
    tx.note = note
    tx.reference = reference
    tx_created = MagicMock()
    tx_created.isoformat.return_value = created_at
    tx.created_at = tx_created
    return tx


# ── OwnerWalletTopupView ──────────────────────────────────────────────────────

class OwnerWalletTopupViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWalletTopupView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/wallet/topup/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_tenant_returns_403(self):
        """A user whose tenant_id doesn't match the request tenant is denied."""
        resp = self._post({"customer_id": 1, "amount": "10.00"}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_customer_id_returns_400(self):
        resp = self._post({"amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Order.objects")
    def test_customer_without_orders_returns_400(self, mock_order_objs):
        mock_order_objs.filter.return_value.exists.return_value = False
        resp = self._post({"customer_id": 42, "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Regression: Order has no tenant FK (it's schema-isolated). Filtering by
        # tenant=... raises FieldError at runtime — only customer_id is valid here.
        _, kwargs = mock_order_objs.filter.call_args
        self.assertNotIn("tenant", kwargs)
        self.assertEqual(kwargs.get("customer_id"), 42)

    @patch("menu.views.Order.objects")
    def test_invalid_amount_returns_400(self, mock_order_objs):
        mock_order_objs.filter.return_value.exists.return_value = True
        resp = self._post({"customer_id": 42, "amount": "not-a-number"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Order.objects")
    def test_zero_amount_returns_400(self, mock_order_objs):
        mock_order_objs.filter.return_value.exists.return_value = True
        resp = self._post({"customer_id": 42, "amount": "0.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Order.objects")
    def test_negative_amount_returns_400(self, mock_order_objs):
        mock_order_objs.filter.return_value.exists.return_value = True
        resp = self._post({"customer_id": 42, "amount": "-5.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.wallet_service.transfer_to_customer")
    @patch("menu.views.Order.objects")
    def test_successful_topup_returns_200(self, mock_order_objs, mock_transfer):
        """Happy-path: the float covers the amount → balances move, 200 with both balances."""
        mock_order_objs.filter.return_value.exists.return_value = True

        float_tx = MagicMock()
        float_tx.balance_after = Decimal("490.00")
        wallet_tx = MagicMock()
        wallet_tx.balance_after = Decimal("30.00")
        mock_transfer.return_value = (float_tx, wallet_tx)

        resp = self._post({"customer_id": 42, "amount": "10.00", "note": "Birthday gift"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["amount"], "10.00")
        self.assertEqual(resp.data["new_balance"], "30.00")     # customer wallet
        self.assertEqual(resp.data["float_balance"], "490.00")  # remaining restaurant float
        # The owner is recorded as the actor on the transfer.
        _, kwargs = mock_transfer.call_args
        self.assertIn("actor_user_id", kwargs)

    @patch("accounts.wallet_service.transfer_to_customer")
    @patch("menu.views.Order.objects")
    def test_insufficient_float_returns_402(self, mock_order_objs, mock_transfer):
        """When the restaurant float can't cover the top-up, nothing moves and we get 402."""
        from accounts.wallet_service import InsufficientFunds
        mock_order_objs.filter.return_value.exists.return_value = True
        mock_transfer.side_effect = InsufficientFunds("restaurant float is insufficient")

        tnt = MagicMock()
        tnt.id = 1
        tnt.float_balance = Decimal("2.00")
        tnt.refresh_from_db = MagicMock()

        resp = self._post({"customer_id": 42, "amount": "10.00"}, tenant=tnt)

        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(resp.data["float_balance"], "2.00")
        self.assertEqual(resp.data["requested"], "10.00")


# ── OwnerWalletHistoryView ────────────────────────────────────────────────────

class OwnerWalletHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWalletHistoryView.as_view()

    def _get(self, customer_id=42, user=None, tenant=None):
        req = self.factory.get(f"/api/owner/wallet/history/{customer_id}/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, customer_id=customer_id)

    def test_outsider_tenant_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Order.objects")
    def test_customer_without_orders_at_restaurant_returns_404(self, mock_order_objs):
        mock_order_objs.filter.return_value.exists.return_value = False
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.DoesNotExist", new=Exception)
    @patch("accounts.models.Customer.objects")
    @patch("menu.views.Order.objects")
    def test_customer_not_in_db_returns_404(self, mock_order_objs, mock_customer_objs):
        mock_order_objs.filter.return_value.exists.return_value = True
        from accounts.models import Customer as CustomerModel
        mock_customer_objs.get.side_effect = CustomerModel.DoesNotExist
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    @patch("menu.views.Order.objects")
    def test_returns_200_with_expected_shape(self, mock_order_objs, mock_customer_objs, mock_tx_objs):
        mock_order_objs.filter.return_value.exists.return_value = True

        customer = _make_customer(customer_id=42, wallet_balance=Decimal("30.00"))
        mock_customer_objs.get.return_value = customer

        tx = _make_tx(tx_id=1, tx_type="topup", amount="10.00", note="Birthday bonus")
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["customer_id"], 42)
        self.assertEqual(resp.data["wallet_balance"], "30.00")
        self.assertIsInstance(resp.data["transactions"], list)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    @patch("menu.views.Order.objects")
    def test_transaction_row_has_required_fields(self, mock_order_objs, mock_customer_objs, mock_tx_objs):
        mock_order_objs.filter.return_value.exists.return_value = True
        customer = _make_customer(customer_id=42, wallet_balance=Decimal("15.00"))
        mock_customer_objs.get.return_value = customer

        tx = _make_tx(tx_id=5, tx_type="payment", amount="5.00", note="Order #ORD123", reference="ORD123")
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        txs = resp.data["transactions"]
        self.assertEqual(len(txs), 1)
        first = txs[0]
        for field in ("id", "type", "amount", "note", "reference", "created_at"):
            self.assertIn(field, first, msg=f"Missing field: {field}")
        self.assertEqual(first["type"], "payment")
        self.assertEqual(first["reference"], "ORD123")
