"""Run 8 G3a — flash-sale fixes (A-01/A-02).

A-02: max_redemptions is validated on both sides of the API. A negative,
fractional or non-numeric value used to reach the PositiveIntegerField DB
constraint (500), and 0 silently became "unlimited" (falsy -> None).
POST and PATCH now 400 on bad values and accept only a positive integer
(or omission/null for unlimited).

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema
switching), following test_flash_sales.py.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import (
    AdminFlashSaleDetailView,
    AdminFlashSaleListCreateView,
    _FLASH_SALE_MAX_REDEMPTIONS_ERROR,
    _parse_flash_sale_max_redemptions,
    _FLASH_SALE_MAX_REDEMPTIONS_INVALID,
)


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _make_fs(fs_id=1, max_redemptions=None):
    fs = MagicMock()
    fs.id = fs_id
    fs.name = "Summer Sale"
    fs.description = ""
    fs.discount_value = Decimal("15.00")
    fs.active_from = MagicMock()
    fs.active_from.isoformat.return_value = "2026-06-01T00:00:00+00:00"
    fs.active_until = MagicMock()
    fs.active_until.isoformat.return_value = "2026-06-30T23:59:59+00:00"
    fs.is_active = True
    fs.max_redemptions = max_redemptions
    fs.redemption_count = 0
    fs.created_at = MagicMock()
    fs.created_at.isoformat.return_value = "2026-05-01T00:00:00+00:00"
    return fs


def _sc_mock():
    ctx = MagicMock()
    ctx.__enter__ = lambda s: None
    ctx.__exit__ = lambda s, *a: None
    return ctx


def _valid_body(**overrides):
    body = {
        "name": "Sale",
        "discount_value": "15",
        "active_from": "2026-06-01T00:00:00Z",
        "active_until": "2026-06-30T23:59:59Z",
    }
    body.update(overrides)
    return body


class ParseMaxRedemptionsTests(SimpleTestCase):
    def test_omitted_or_empty_is_unlimited(self):
        self.assertIsNone(_parse_flash_sale_max_redemptions(None))
        self.assertIsNone(_parse_flash_sale_max_redemptions(""))

    def test_positive_int_and_numeric_string(self):
        self.assertEqual(_parse_flash_sale_max_redemptions(5), 5)
        self.assertEqual(_parse_flash_sale_max_redemptions("5"), 5)
        self.assertEqual(_parse_flash_sale_max_redemptions(1), 1)

    def test_zero_negative_fractional_and_junk_are_invalid(self):
        for bad in (0, "0", -3, "-3", 1.5, "1.5", "abc", True, False, [], {}):
            with self.subTest(raw=bad):
                self.assertIs(
                    _parse_flash_sale_max_redemptions(bad),
                    _FLASH_SALE_MAX_REDEMPTIONS_INVALID,
                )


class AdminFlashSaleMaxRedemptionsPostTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleListCreateView.as_view()

    def _post(self, data):
        req = self.factory.post("/api/admin/flash-sales/", data, format="json")
        req.user = _admin()
        return req

    def test_post_zero_max_redemptions_returns_400_not_unlimited(self):
        """0 used to be falsy -> None (unlimited). Now a 400: the admin asked for a
        cap of zero redemptions, which is not a meaningful cap."""
        req = self._post(_valid_body(max_redemptions=0))
        with patch("django_tenants.utils.schema_context"):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], _FLASH_SALE_MAX_REDEMPTIONS_ERROR)

    def test_post_bad_max_redemptions_returns_400(self):
        for bad in (-1, "1.5", "abc", 2.5):
            with self.subTest(max_redemptions=bad):
                req = self._post(_valid_body(max_redemptions=bad))
                with patch("django_tenants.utils.schema_context"):
                    resp = self.view(req)
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_valid_max_redemptions_persists(self):
        fs = _make_fs(max_redemptions=10)
        req = self._post(_valid_body(max_redemptions=10))
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.create.return_value = fs
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mock_fs.objects.create.call_args[1]["max_redemptions"], 10)

    def test_post_omitted_max_redemptions_is_unlimited(self):
        fs = _make_fs(max_redemptions=None)
        req = self._post(_valid_body())
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.create.return_value = fs
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(mock_fs.objects.create.call_args[1]["max_redemptions"])


class AdminFlashSaleMaxRedemptionsPatchTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleDetailView.as_view()

    def _patch(self, fs_id, data):
        req = self.factory.patch(f"/api/admin/flash-sales/{fs_id}/", data, format="json")
        req.user = _admin()
        return self.view(req, fs_id=fs_id)

    def _patch_max(self, fs, value):
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.views._bust_public_list_cache"):
            mock_fs.objects.get.return_value = fs
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._patch(7, {"max_redemptions": value})
        return resp, fs, mock_log

    def test_patch_zero_max_redemptions_returns_400_and_saves_nothing(self):
        fs = _make_fs(fs_id=7, max_redemptions=10)
        resp, _, mock_log = self._patch_max(fs, 0)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        fs.save.assert_not_called()
        mock_log.assert_not_called()

    def test_patch_bad_max_redemptions_returns_400(self):
        for bad in (-5, "1.5", "abc"):
            with self.subTest(max_redemptions=bad):
                fs = _make_fs(fs_id=7, max_redemptions=10)
                resp, _, _ = self._patch_max(fs, bad)
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                fs.save.assert_not_called()

    def test_patch_valid_max_redemptions_saves(self):
        fs = _make_fs(fs_id=7, max_redemptions=10)
        resp, _, mock_log = self._patch_max(fs, 25)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(fs.max_redemptions, 25)
        fs.save.assert_called_once()
        mock_log.assert_called_once()

    def test_patch_null_max_redemptions_clears_to_unlimited(self):
        """Explicit null removes the cap (the edit form's empty field)."""
        fs = _make_fs(fs_id=7, max_redemptions=10)
        resp, _, _ = self._patch_max(fs, None)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(fs.max_redemptions)
        fs.save.assert_called_once()
