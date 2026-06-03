"""Idempotent-replay tests for loyalty and voucher redemption.

Unit-level (SimpleTestCase + mocks — no real DB). These cover the "lost-response
retry must not double-credit, and must not show a false error" hardening:
  - Loyalty redeem: a repeat with the same idempotency_key replays the prior result.
  - Voucher redeem: the same customer re-submitting an already-used voucher gets a
    success replay (their credit happened once) instead of "already used".
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import CustomerLoyaltyRedeemView
from accounts.views import CustomerWalletRedeemVoucherView


def _auth_user(customer_id=7):
    u = MagicMock()
    u.is_authenticated = True
    u.customer_id = customer_id
    return u


class LoyaltyRedeemIdempotencyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()

    def _post(self, body):
        req = self.factory.post("/api/customer/loyalty/redeem/", body, format="json")
        req.user = _auth_user()
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_replay_returns_duplicate_without_recharging(self, mock_cust, mock_cfg, mock_wt):
        customer = MagicMock(phone_verified=True, loyalty_points=500, wallet_balance=Decimal("42.00"))
        mock_cust.get.return_value = customer

        cfg = MagicMock(redeem_threshold=100, points_value=Decimal("0.10"))
        mock_cfg.filter.return_value.first.return_value = cfg

        prior = MagicMock(amount=Decimal("10.00"), reference="loyalty:100pts")
        mock_wt.filter.return_value.first.return_value = prior

        resp = self._post({"points": 100, "idempotency_key": "abc-123"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        self.assertEqual(resp.data["credit_amount"], "10.00")
        self.assertEqual(resp.data["redeemed_points"], 100)
        self.assertEqual(resp.data["new_wallet_balance"], "42.00")
        # Crucially, no second ledger row is written on replay.
        mock_wt.create.assert_not_called()


class VoucherRedeemIdempotencyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletRedeemVoucherView.as_view()

    def _post(self, body, user):
        req = self.factory.post("/api/customer/wallet/redeem-voucher/", body, format="json")
        req.user = user
        return self.view(req)

    @patch("django.db.transaction.atomic")
    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.views.Customer.objects")
    def test_same_customer_replay_returns_success(self, mock_cust, mock_voucher, _mock_atomic):
        customer = MagicMock(phone_verified=True, wallet_balance=Decimal("60.00"))
        customer.id = 7
        mock_cust.get.return_value = customer

        voucher = MagicMock(is_used=True, used_by_id=7, amount=Decimal("25.00"), note="Promo")
        mock_voucher.select_for_update.return_value.get.return_value = voucher

        resp = self._post({"code": "ABCD1234"}, user=_auth_user(customer_id=7))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["duplicate"])
        self.assertEqual(resp.data["credited"], "25.00")
        self.assertEqual(resp.data["new_balance"], "60.00")

    @patch("django.db.transaction.atomic")
    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.views.Customer.objects")
    def test_other_customer_still_rejected(self, mock_cust, mock_voucher, _mock_atomic):
        customer = MagicMock(phone_verified=True, wallet_balance=Decimal("60.00"))
        customer.id = 7
        mock_cust.get.return_value = customer

        # Voucher was used by a DIFFERENT customer (id 99) — must stay rejected.
        voucher = MagicMock(is_used=True, used_by_id=99, amount=Decimal("25.00"), note="Promo")
        mock_voucher.select_for_update.return_value.get.return_value = voucher

        resp = self._post({"code": "ABCD1234"}, user=_auth_user(customer_id=7))

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
