"""
Tests for CustomerWalletRedeemVoucherView
POST /api/customer/wallet/redeem-voucher/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerWalletRedeemVoucherView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(customer_id=1, wallet_balance=Decimal("20.00")):
    c = MagicMock()
    c.id = customer_id
    c.wallet_balance = wallet_balance
    return c


def _make_voucher(code="GIFT1234AB", amount=Decimal("15.00"), is_used=False,
                  expires_at=None, note="Gift", vid=7):
    v = MagicMock()
    v.id = vid
    v.code = code
    v.amount = amount
    v.is_used = is_used
    v.expires_at = expires_at
    v.note = note
    return v


# ── Tests ─────────────────────────────────────────────────────────────────────

class CustomerWalletRedeemVoucherViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletRedeemVoucherView.as_view()

    def _post(self, data, customer=None):
        req = self.factory.post(
            "/api/customer/wallet/redeem-voucher/", data, format="json"
        )
        req.user = MagicMock(is_authenticated=True)
        # The view checks `getattr(request, 'customer', None)` first
        if customer is not None:
            req.customer = customer
        elif hasattr(req, "customer"):
            del req.customer
        return req

    # ── No customer ───────────────────────────────────────────────────────────

    def test_no_customer_returns_404(self):
        """request.customer is None and fallback Customer.objects.get fails → 404."""
        req = self._post({"code": "GIFT1234AB"})
        req.customer = None

        # Fallback: Customer.objects.get(user=request.user) raises DoesNotExist
        from accounts.models import Customer as CustomerModel
        with patch.object(CustomerModel, "objects") as mock_objs:
            mock_objs.get.side_effect = CustomerModel.DoesNotExist
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_code_returns_400(self):
        req = self._post({}, customer=_make_customer())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_code_returns_400(self):
        req = self._post({"code": "  "}, customer=_make_customer())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Voucher state ─────────────────────────────────────────────────────────

    @patch("accounts.models.WalletVoucher.objects")
    def test_invalid_voucher_code_returns_400(self, mock_voucher_objs):
        from accounts.models import WalletVoucher
        mock_voucher_objs.select_for_update.return_value.get.side_effect = WalletVoucher.DoesNotExist

        req = self._post({"code": "NOSUCHCODE"}, customer=_make_customer())
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.WalletVoucher.objects")
    def test_already_used_voucher_returns_400(self, mock_voucher_objs):
        voucher = _make_voucher(is_used=True)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher

        req = self._post({"code": "GIFT1234AB"}, customer=_make_customer())
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.WalletVoucher.objects")
    def test_expired_voucher_returns_400(self, mock_voucher_objs):
        from django.utils import timezone
        from datetime import timedelta
        past_dt = timezone.now() - timedelta(days=1)
        voucher = _make_voucher(is_used=False, expires_at=past_dt)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher

        req = self._post({"code": "EXPIRED01"}, customer=_make_customer())
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    # OPS-5f: the credit now goes through wallet_service.credit_wallet (locks the
    # customer row, idempotent) instead of a manual balance write + WalletTransaction.
    @patch("accounts.wallet_service.credit_wallet")
    @patch("accounts.models.WalletVoucher.objects")
    def test_valid_redemption_returns_200_with_new_balance(self, mock_voucher_objs, mock_credit):
        from types import SimpleNamespace
        customer = _make_customer(wallet_balance=Decimal("20.00"))
        voucher = _make_voucher(amount=Decimal("15.00"), is_used=False, expires_at=None)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher
        mock_credit.return_value = SimpleNamespace(balance_after=Decimal("35.00"))

        req = self._post({"code": "GIFT1234AB"}, customer=customer)
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("credited", resp.data)
        self.assertIn("new_balance", resp.data)
        self.assertEqual(resp.data["credited"], "15.00")
        # Balance comes from the ledger row's balance_after, not a manual write.
        self.assertEqual(resp.data["new_balance"], "35.00")
        self.assertTrue(voucher.is_used)
        voucher.save.assert_called()

    @patch("accounts.wallet_service.credit_wallet")
    @patch("accounts.models.WalletVoucher.objects")
    def test_valid_redemption_creates_wallet_transaction(self, mock_voucher_objs, mock_credit):
        from types import SimpleNamespace
        customer = _make_customer(wallet_balance=Decimal("0.00"))
        voucher = _make_voucher(amount=Decimal("25.00"), is_used=False, vid=42)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher
        mock_credit.return_value = SimpleNamespace(balance_after=Decimal("25.00"))

        req = self._post({"code": "GIFT1234AB"}, customer=customer)
        with patch("django.db.transaction.atomic"):
            self.view(req)

        # The ledger write is funnelled through credit_wallet with a stable key.
        mock_credit.assert_called_once()
        args, kwargs = mock_credit.call_args
        self.assertEqual(args[0], customer.id)
        self.assertEqual(args[1], Decimal("25.00"))
        self.assertEqual(kwargs["idempotency_key"], "voucher:42")

    @patch("accounts.wallet_service.credit_wallet")
    @patch("accounts.models.WalletVoucher.objects")
    def test_code_is_uppercased_before_lookup(self, mock_voucher_objs, mock_credit):
        from types import SimpleNamespace
        customer = _make_customer()
        voucher = _make_voucher(code="GIFT1234AB", is_used=False)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher
        mock_credit.return_value = SimpleNamespace(balance_after=Decimal("35.00"))

        req = self._post({"code": "gift1234ab"}, customer=customer)
        with patch("django.db.transaction.atomic"):
            self.view(req)

        call_kwargs = mock_voucher_objs.select_for_update.return_value.get.call_args[1]
        self.assertEqual(call_kwargs.get("code"), "GIFT1234AB")
