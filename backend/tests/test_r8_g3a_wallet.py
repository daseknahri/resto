"""Run 8 G3a — admin wallet vouchers (A-19/A-20/A-21).

A-20: vouchers can be revoked (new POST .../vouchers/<id>/revoke/, 404 missing,
409 used/already-revoked, audit-logged VOUCHER_REVOKED); the list now exposes
is_revoked; redeem rejects revoked vouchers.
A-21: minting a voucher with a past expires_at (or a non-positive / non-integer
expires_days) is a 400 — previously a past expiry minted a dead voucher and a
bad expires_days silently became "never expires".

Unit-level (SimpleTestCase + mocks — no real DB), following test_admin_wallet_views.py.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, WalletVoucher
from accounts.views import (
    AdminWalletVoucherRevokeView,
    AdminWalletVoucherView,
    CustomerWalletRedeemVoucherView,
)


@contextmanager
def _noop_atomic(*args, **kwargs):
    yield


def _admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = True
    u.is_staff = True
    u.is_platform_admin = True
    return u


def _non_admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    return u


def _voucher(**overrides):
    v = MagicMock()
    v.id = 1
    v.code = "ABCD1234EF"
    v.amount = Decimal("20.00")
    v.note = ""
    v.is_used = False
    v.is_revoked = False
    v.used_by = None
    v.used_at = None
    v.expires_at = None
    v.created_at = MagicMock()
    v.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    for k, val in overrides.items():
        setattr(v, k, val)
    return v


class AdminWalletVoucherExpiryTests(SimpleTestCase):
    """A-21: past / bad expiry inputs are rejected at mint time."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletVoucherView.as_view()
        _p = patch("django.db.transaction.atomic", _noop_atomic)
        _p.start()
        self.addCleanup(_p.stop)

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/wallet/vouchers/", data, format="json")
        req.user = user or _admin()
        return self.view(req)

    def test_post_past_expires_at_returns_400(self):
        resp = self._post({"amount": "20.00", "expires_at": "2020-01-01T00:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("future", resp.data["detail"])

    def test_post_expires_days_zero_or_negative_returns_400(self):
        for bad in (0, -5, "-3"):
            with self.subTest(expires_days=bad):
                resp = self._post({"amount": "20.00", "expires_days": bad})
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_expires_days_non_numeric_returns_400(self):
        resp = self._post({"amount": "20.00", "expires_days": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_future_expires_at_accepted(self, mock_gen, mock_voucher_objs):
        v1 = MagicMock()
        v1.code = "CODE123"
        mock_voucher_objs.bulk_create.return_value = [v1]
        resp = self._post({"amount": "20.00", "expires_at": "2030-01-01T00:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_expires_days_sets_future_expiry(self, mock_gen, mock_voucher_objs):
        v1 = MagicMock()
        v1.code = "CODE123"
        mock_voucher_objs.bulk_create.return_value = [v1]
        resp = self._post({"amount": "20.00", "expires_days": 30})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        minted = mock_voucher_objs.bulk_create.call_args[0][0][0]
        self.assertIsNotNone(minted.expires_at)
        self.assertGreater(minted.expires_at, datetime.now(timezone.utc))


class AdminWalletVoucherListRevokedTests(SimpleTestCase):
    """A-20: the audit list exposes is_revoked."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletVoucherView.as_view()

    @patch("accounts.models.WalletVoucher.objects")
    def test_get_includes_is_revoked(self, mock_voucher_objs):
        v = _voucher(is_revoked=True)
        mock_voucher_objs.select_related.return_value.__getitem__ = lambda s, k: [v]
        req = self.factory.get("/api/admin/wallet/vouchers/")
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data[0]["is_revoked"])


class AdminWalletVoucherRevokeTests(SimpleTestCase):
    """A-20: the revoke endpoint."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletVoucherRevokeView.as_view()

    def _post(self, voucher_id, user=None):
        req = self.factory.post(f"/api/admin/wallet/vouchers/{voucher_id}/revoke/", {}, format="json")
        req.user = user or _admin()
        return self.view(req, voucher_id=voucher_id)

    @patch("accounts.models.WalletVoucher.objects")
    def test_revoke_missing_voucher_returns_404(self, mock_voucher_objs):
        mock_voucher_objs.get.side_effect = WalletVoucher.DoesNotExist
        resp = self._post(99)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_revoke_non_admin_returns_403(self):
        resp = self._post(1, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.WalletVoucher.objects")
    def test_revoke_used_voucher_returns_409(self, mock_voucher_objs):
        mock_voucher_objs.get.return_value = _voucher(is_used=True)
        resp = self._post(1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("accounts.models.WalletVoucher.objects")
    def test_revoke_already_revoked_returns_409(self, mock_voucher_objs):
        mock_voucher_objs.get.return_value = _voucher(is_revoked=True)
        resp = self._post(1)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("sales.audit.log_admin_action")
    @patch("accounts.models.WalletVoucher.objects")
    def test_revoke_unused_voucher_marks_revoked(self, mock_voucher_objs, mock_log):
        v = _voucher()
        mock_voucher_objs.get.return_value = v
        resp = self._post(1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_revoked"])
        self.assertTrue(v.is_revoked)
        v.save.assert_called_once_with(update_fields=["is_revoked"])
        mock_log.assert_called_once()


class CustomerWalletRedeemRevokedTests(SimpleTestCase):
    """A-20: redeem rejects a revoked voucher."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate the per-actor invalid-code lockout counter across tests
        self.factory = APIRequestFactory()
        self.view = CustomerWalletRedeemVoucherView.as_view()
        _p = patch("django.db.transaction.atomic", _noop_atomic)
        _p.start()
        self.addCleanup(_p.stop)

    def _customer(self):
        c = Customer(id=5, phone_verified=True)
        c.save = MagicMock()
        return c

    @patch("accounts.models.WalletVoucher.objects")
    def test_redeem_revoked_voucher_returns_400(self, mock_voucher_objs):
        mock_voucher_objs.select_for_update.return_value.get.return_value = _voucher(is_revoked=True)
        req = self.factory.post("/api/customer/wallet/redeem-voucher/", {"code": "ABCD1234EF"}, format="json")
        req.session = {"customer_id": 5}
        # Force the DRF principal (bypasses the session DB lookup
        # CustomerSessionAuthentication would otherwise do — same pattern as
        # test_customer_voucher_redeem.py).
        force_authenticate(req, user=self._customer())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("revoked", resp.data["detail"])
