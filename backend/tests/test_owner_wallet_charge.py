"""Tests for OwnerWalletChargeView (wallet charge by pay-code). No DB."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import _WALLET_PAY_SALT
from menu.models import OrderPayment
from menu.views import OwnerWalletChargeView


def _owner(tenant_id=1):
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.tenant_id = tenant_id
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    return u


def _outsider():
    u = _owner(tenant_id=99)  # different tenant than the request tenant (id=1)
    return u


class OwnerWalletChargeViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWalletChargeView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/wallet/charge/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or SimpleNamespace(id=1)
        return self.view(req)

    def test_non_owner_403(self):
        self.assertEqual(self._post({"token": "x", "amount": "10"}, user=_outsider()).status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_token_400(self):
        resp = self._post({"amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_token")

    def test_bad_token_400(self):
        resp = self._post({"token": "not-a-valid-token", "amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid")

    def test_valid_token_but_bad_amount_400(self):
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        resp = self._post({"token": token, "amount": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_above_threshold_creates_pending_request_without_charging(self):
        """Amount over the approval threshold (default 50) → 202 pending, no debit."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        cr = MagicMock(id=7)
        cr.expires_at.isoformat.return_value = "2026-06-03T15:00:00+00:00"
        with patch("accounts.models.WalletChargeRequest.objects") as mock_cr, \
             patch("accounts.wallet_service.debit_wallet") as mock_debit:
            mock_cr.get_or_create.return_value = (cr, True)
            resp = self._post({"token": token, "amount": "100.00"})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["request_id"], 7)
        mock_debit.assert_not_called()

    def test_at_or_below_threshold_charges_instantly(self):
        """Amount within the threshold → instant debit, 200 charged."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        with patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit:
            resp = self._post({"token": token, "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "charged")
        mock_debit.assert_called_once()

    def test_order_tied_charge_writes_orderpayment_row(self):
        """S1: when order_number is supplied, the charge must be tied to that
        order as a real OrderPayment (method=wallet) row — not just an update to
        wallet_amount_paid — so OwnerOrderMarkPaidView's reconciliation guard has
        a real ledger figure to check the settle against."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        charged_order = MagicMock(id=77)
        with patch("accounts.wallet_service.debit_wallet", return_value=tx), \
             patch("menu.views.Order.objects") as mock_order_objects, \
             patch("menu.views.OrderPayment.objects") as mock_op_objects, \
             patch("menu.views._settle_order_if_wallet_covers"):
            mock_order_objects.filter.return_value.update.return_value = 1
            mock_order_objects.filter.return_value.only.return_value.first.return_value = charged_order
            resp = self._post({"token": token, "amount": "10.00", "order_number": "ORD-9"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_op_objects.create.assert_called_once()
        _, kwargs = mock_op_objects.create.call_args
        self.assertEqual(kwargs["order"], charged_order)
        self.assertEqual(kwargs["amount"], Decimal("10.00"))
        self.assertEqual(kwargs["method"], OrderPayment.Method.WALLET)

    def test_no_order_number_does_not_write_orderpayment(self):
        """The general (non-settle) wallet charge use — no order_number supplied —
        must be untouched: no OrderPayment row, only the wallet debit."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        with patch("accounts.wallet_service.debit_wallet", return_value=tx), \
             patch("menu.views.OrderPayment.objects") as mock_op_objects:
            resp = self._post({"token": token, "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_op_objects.create.assert_not_called()
