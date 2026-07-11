"""
Tests for CustomerWalletRedeemVoucherView
POST /api/customer/wallet/redeem-voucher/

RISK IDENTITY-1: this view now authenticates via CustomerSessionAuthentication +
IsCustomer, so the signed-in Customer arrives as request.user. (It previously did
`Customer.objects.get(user=request.user)` — Customer has no `user` field, so that raised
FieldError for any real caller; the OLD tests masked it by injecting `request.customer`.)
Here we force-authenticate a real Customer principal, matching the production auth path.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerWalletRedeemVoucherView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _customer(customer_id=1, phone_verified=True):
    """A real (unsaved) Customer so it passes IsCustomer's principal check
    (is_authenticated + class name). No DB is touched — the view never saves it."""
    return Customer(id=customer_id, phone_verified=phone_verified)


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


class CustomerWalletRedeemVoucherViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate the per-actor invalid-code lockout counter across tests
        self.factory = APIRequestFactory()
        self.view = CustomerWalletRedeemVoucherView.as_view()

    def _post(self, data, customer=None):
        req = self.factory.post(
            "/api/customer/wallet/redeem-voucher/", data, format="json"
        )
        req.session = {"customer_id": customer.id} if customer is not None else {}
        if customer is not None:
            # Force the DRF principal (bypasses the session DB lookup CustomerSessionAuthentication
            # would otherwise do — that class is covered in test_identity_customer_auth.py).
            force_authenticate(req, user=customer)
        return req

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_no_customer_returns_401(self):
        """No customer principal (anonymous) → IsCustomer rejects with 401 (was a masked
        404 in the old FieldError code path)."""
        resp = self.view(self._post({"code": "GIFT1234AB"}))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_phone_returns_403(self):
        """A signed-in customer without a verified phone can't touch the wallet."""
        resp = self.view(self._post({"code": "GIFT1234AB"}, customer=_customer(phone_verified=False)))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "phone_unverified")

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_code_returns_400(self):
        resp = self.view(self._post({}, customer=_customer()))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_code_returns_400(self):
        resp = self.view(self._post({"code": "  "}, customer=_customer()))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Voucher state ─────────────────────────────────────────────────────────

    @patch("accounts.models.WalletVoucher.objects")
    def test_invalid_voucher_code_returns_400(self, mock_voucher_objs):
        from accounts.models import WalletVoucher
        mock_voucher_objs.select_for_update.return_value.get.side_effect = WalletVoucher.DoesNotExist

        req = self._post({"code": "NOSUCHCODE"}, customer=_customer())
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.WalletVoucher.objects")
    def test_already_used_voucher_returns_400(self, mock_voucher_objs):
        voucher = _make_voucher(is_used=True)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher

        req = self._post({"code": "GIFT1234AB"}, customer=_customer())
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

        req = self._post({"code": "EXPIRED01"}, customer=_customer())
        with patch("django.db.transaction.atomic"):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    # OPS-5f: the credit goes through wallet_service.credit_wallet (locks the customer
    # row, idempotent) instead of a manual balance write + WalletTransaction.
    @patch("accounts.wallet_service.credit_wallet")
    @patch("accounts.models.WalletVoucher.objects")
    def test_valid_redemption_returns_200_with_new_balance(self, mock_voucher_objs, mock_credit):
        customer = _customer(customer_id=5)
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
        customer = _customer(customer_id=3)
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
        customer = _customer()
        voucher = _make_voucher(code="GIFT1234AB", is_used=False)
        mock_voucher_objs.select_for_update.return_value.get.return_value = voucher
        mock_credit.return_value = SimpleNamespace(balance_after=Decimal("35.00"))

        req = self._post({"code": "gift1234ab"}, customer=customer)
        with patch("django.db.transaction.atomic"):
            self.view(req)

        call_kwargs = mock_voucher_objs.select_for_update.return_value.get.call_args[1]
        self.assertEqual(call_kwargs.get("code"), "GIFT1234AB")
