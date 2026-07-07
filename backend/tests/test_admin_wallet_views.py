"""
Tests for admin wallet views:
  - AdminWalletBonusView   POST /api/admin/wallet/bonus/
  - AdminWalletVoucherView GET/POST /api/admin/wallet/vouchers/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import AdminWalletBonusView, AdminWalletVoucherView


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── AdminWalletBonusView ──────────────────────────────────────────────────────

class AdminWalletBonusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletBonusView.as_view()

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/wallet/bonus/", data, format="json")
        req.user = user or _admin()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_non_admin_returns_403(self):
        resp = self._post({"amount": "10.00", "customer_ids": [1]}, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_invalid_amount_returns_400(self):
        resp = self._post({"amount": "not-a-number", "customer_ids": [1]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_amount_returns_400(self):
        resp = self._post({"amount": "0.00", "customer_ids": [1]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_amount_returns_400(self):
        resp = self._post({"amount": "-5.00", "customer_ids": [1]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_target_returns_400(self):
        """Neither customer_ids nor all_customers → 400."""
        resp = self._post({"amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_specific_customer_ids_returns_200(self, mock_cust_objs, mock_tx_objs):
        # OPS-5b: values_list is called twice:
        #   1. values_list("id", flat=True)  → flat list of ids
        #   2. values_list("id", "wallet_balance") → list of (id, balance) tuples
        def _vl_se(*args, **kwargs):
            if kwargs.get("flat"):
                return [1, 2]
            return [(1, "10.00"), (2, "10.00")]
        mock_cust_objs.filter.return_value.values_list.side_effect = _vl_se
        mock_cust_objs.filter.return_value.update.return_value = 2
        mock_tx_objs.bulk_create.return_value = []

        with patch("django.db.transaction.atomic"):
            resp = self._post({"amount": "10.00", "customer_ids": [1, 2], "note": "Thanks"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued_to"], 2)
        self.assertEqual(resp.data["amount"], "10.00")
        self.assertEqual(resp.data["note"], "Thanks")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_all_customers_returns_200(self, mock_cust_objs, mock_tx_objs):
        mock_cust_objs.all.return_value = mock_cust_objs.filter.return_value
        # OPS-5b: two values_list calls — flat ids first, then (id, balance) tuples
        def _vl_se(*args, **kwargs):
            if kwargs.get("flat"):
                return [1, 2, 3]
            return [(1, "5.00"), (2, "5.00"), (3, "5.00")]
        mock_cust_objs.filter.return_value.values_list.side_effect = _vl_se
        mock_cust_objs.filter.return_value.update.return_value = 3
        mock_tx_objs.bulk_create.return_value = []

        with patch("django.db.transaction.atomic"):
            resp = self._post({"amount": "5.00", "all_customers": True})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued_to"], 3)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_no_matching_customers_returns_400(self, mock_cust_objs, mock_tx_objs):
        mock_cust_objs.filter.return_value.values_list.return_value = []

        with patch("django.db.transaction.atomic"):
            resp = self._post({"amount": "10.00", "customer_ids": [999]})

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── AdminWalletVoucherView ────────────────────────────────────────────────────

class AdminWalletVoucherViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletVoucherView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/admin/wallet/vouchers/")
        req.user = user or _admin()
        return self.view(req)

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/wallet/vouchers/", data, format="json")
        req.user = user or _admin()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_non_admin_returns_403(self):
        resp = self._post({"amount": "20.00"}, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET list ──────────────────────────────────────────────────────────────

    @patch("accounts.models.WalletVoucher.objects")
    def test_get_returns_list(self, mock_voucher_objs):
        v = MagicMock()
        v.id = 1
        v.code = "ABCD1234EF"
        v.amount = Decimal("20.00")
        v.note = "Welcome"
        v.is_used = False
        v.used_by = None
        v.used_at = None
        v.expires_at = None
        v.created_at = MagicMock()
        v.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        mock_voucher_objs.select_related.return_value.__getitem__.return_value = [v]

        # The view does: WalletVoucher.objects.select_related("used_by")[:100]
        # Patch the slicing
        mock_voucher_objs.select_related.return_value.__getitem__ = lambda s, k: [v]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_invalid_amount_returns_400(self):
        resp = self._post({"amount": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_zero_amount_returns_400(self):
        resp = self._post({"amount": "0"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── POST happy path ───────────────────────────────────────────────────────

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_creates_vouchers_and_returns_201(self, mock_gen, mock_voucher_objs):
        v1 = MagicMock()
        v1.code = "CODE1"
        v2 = MagicMock()
        v2.code = "CODE2"
        mock_voucher_objs.bulk_create.return_value = [v1, v2]

        resp = self._post({"amount": "20.00", "count": 2, "note": "Promo"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["created"], 2)
        self.assertIn("codes", resp.data)
        self.assertIsInstance(resp.data["codes"], list)
        self.assertEqual(resp.data["amount"], "20.00")

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_single_voucher_default_count(self, mock_gen, mock_voucher_objs):
        v = MagicMock()
        v.code = "SINGLE01"
        mock_voucher_objs.bulk_create.return_value = [v]

        resp = self._post({"amount": "10.00"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["created"], 1)

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_expires_at_included_in_response(self, mock_gen, mock_voucher_objs):
        v = MagicMock()
        v.code = "EXP123"
        mock_voucher_objs.bulk_create.return_value = [v]

        resp = self._post({
            "amount": "15.00",
            "expires_days": 30,
        })

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(resp.data.get("expires_at"))

    # ── POST idempotency (platform-money guard) ───────────────────────────────

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_idempotency_key_dedupes_batch(self, mock_gen, mock_voucher_objs):
        """A repeated POST with the same idempotency_key must NOT mint a second voucher
        batch — it replays the first result. Closes the platform-money hole where a
        network retry / double-submit duplicates a voucher batch."""
        from django.core.cache import cache
        cache.clear()
        try:
            v1, v2 = MagicMock(), MagicMock()
            v1.code, v2.code = "CODE1", "CODE2"
            mock_voucher_objs.bulk_create.return_value = [v1, v2]

            body = {"amount": "20.00", "count": 2, "note": "Promo", "idempotency_key": "abc-123"}
            first = self._post(body)
            self.assertEqual(first.status_code, status.HTTP_201_CREATED)
            self.assertEqual(first.data["created"], 2)
            self.assertEqual(mock_voucher_objs.bulk_create.call_count, 1)

            # Replay with the same key → no second bulk_create, same codes replayed.
            second = self._post(body)
            self.assertEqual(second.status_code, status.HTTP_200_OK)
            self.assertTrue(second.data.get("idempotent_replay"))
            self.assertEqual(second.data["codes"], first.data["codes"])
            self.assertEqual(mock_voucher_objs.bulk_create.call_count, 1)  # still 1
        finally:
            cache.clear()

    @patch("accounts.models.WalletVoucher.objects")
    @patch("accounts.models.WalletVoucher.generate_code", return_value="CODE123")
    def test_post_without_idempotency_key_still_creates_each_time(self, mock_gen, mock_voucher_objs):
        """No idempotency_key → unchanged behavior (every POST creates a batch)."""
        from django.core.cache import cache
        cache.clear()
        try:
            v = MagicMock()
            v.code = "SOLO"
            mock_voucher_objs.bulk_create.return_value = [v]
            r1 = self._post({"amount": "5.00"})
            r2 = self._post({"amount": "5.00"})
            self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
            self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
            self.assertEqual(mock_voucher_objs.bulk_create.call_count, 2)
        finally:
            cache.clear()
