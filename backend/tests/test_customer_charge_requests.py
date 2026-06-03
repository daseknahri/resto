"""Tests for the customer-confirmed charge approval flow (no real DB).

CustomerWalletChargeApproveView / DeclineView — a customer approves or declines an
above-threshold wallet charge a restaurant initiated. Approval debits the wallet using
the request's stored idempotency key; a re-approve replays instead of charging twice.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import WalletChargeRequest
from accounts.views import (
    CustomerWalletChargeApproveView,
    CustomerWalletChargeDeclineView,
)


def _pending_cr():
    cr = MagicMock()
    cr.status = WalletChargeRequest.Status.PENDING
    cr.amount = Decimal("100.00")
    cr.order_number = "ORD-1"
    cr.tenant_id = 3
    cr.note = ""
    cr.idempotency_key = "cr-key-xyz"
    cr.expires_at = timezone.now() + timedelta(hours=1)
    cr.save = MagicMock()
    return cr


class ApproveChargeRequestTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletChargeApproveView.as_view()

    def _post(self, request_id=1, customer_id=5):
        req = self.factory.post(f"/api/customer/wallet/charge-requests/{request_id}/approve/")
        req.session = {"customer_id": customer_id} if customer_id else {}
        return self.view(req, request_id=request_id)

    def test_unauthenticated_401(self):
        self.assertEqual(self._post(customer_id=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_approve_pending_debits_with_request_key_and_marks_charged(self):
        cr = _pending_cr()
        tx = MagicMock(id=55, amount=Decimal("100.00"), balance_after=Decimal("20.00"))
        with patch("accounts.models.WalletChargeRequest.objects") as mock_objs, \
             patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit, \
             patch("django.db.transaction.atomic"):
            mock_objs.select_for_update.return_value.get.return_value = cr
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "charged")
        self.assertEqual(resp.data["new_balance"], "20.00")
        # Debit used the request's stored idempotency key (at most once ever).
        self.assertEqual(mock_debit.call_args.kwargs["idempotency_key"], "cr-key-xyz")
        self.assertEqual(cr.status, WalletChargeRequest.Status.CHARGED)
        self.assertEqual(cr.wallet_tx_id, 55)

    def test_reapprove_already_charged_replays_without_recharging(self):
        cr = _pending_cr()
        cr.status = WalletChargeRequest.Status.CHARGED
        with patch("accounts.models.WalletChargeRequest.objects") as mock_objs, \
             patch("accounts.wallet_service.debit_wallet") as mock_debit, \
             patch("django.db.transaction.atomic"):
            mock_objs.select_for_update.return_value.get.return_value = cr
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        mock_debit.assert_not_called()

    def test_approve_expired_returns_410_and_no_charge(self):
        cr = _pending_cr()
        cr.expires_at = timezone.now() - timedelta(seconds=1)
        with patch("accounts.models.WalletChargeRequest.objects") as mock_objs, \
             patch("accounts.wallet_service.debit_wallet") as mock_debit, \
             patch("django.db.transaction.atomic"):
            mock_objs.select_for_update.return_value.get.return_value = cr
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)
        self.assertEqual(resp.data["code"], "expired")
        mock_debit.assert_not_called()
        self.assertEqual(cr.status, WalletChargeRequest.Status.EXPIRED)


class DeclineChargeRequestTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletChargeDeclineView.as_view()

    def _post(self, request_id=1, customer_id=5):
        req = self.factory.post(f"/api/customer/wallet/charge-requests/{request_id}/decline/")
        req.session = {"customer_id": customer_id} if customer_id else {}
        return self.view(req, request_id=request_id)

    def test_decline_marks_declined(self):
        cr = _pending_cr()
        with patch("accounts.models.WalletChargeRequest.objects") as mock_objs:
            mock_objs.filter.return_value.first.return_value = cr
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cr.status, WalletChargeRequest.Status.DECLINED)

    def test_decline_missing_request_404(self):
        with patch("accounts.models.WalletChargeRequest.objects") as mock_objs:
            mock_objs.filter.return_value.first.return_value = None
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
