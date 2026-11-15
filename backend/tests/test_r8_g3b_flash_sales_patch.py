"""
Run 8 G3b, worker W1 — backend tests for A-04 + A-06 (+ A-03 server contract).

  - A-06: PATCH must reject an inverted active window (POST already did);
    the effective window (patched values over the stored ones) is checked.
  - A-04: the flash-sale serializer strips trailing zeros from the discount
    ("15.00" -> "15", "12.50" -> "12.5") so the admin chip renders "-15%".
  - A-03: POST honours an explicit is_active=false (draft/paused create) —
    the server already accepted it; the new client checkbox relies on it.

Unit-level (SimpleTestCase + mocks — no real DB or schema switching), same
pattern as test_flash_sales.py. The mocked sale carries REAL datetimes for
active_from/active_until (not MagicMocks) so the PATCH window comparison
runs against real values.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    AdminFlashSaleDetailView,
    AdminFlashSaleListCreateView,
    _serialize_flash_sale,
)
from accounts.models import User


# ── Helpers (mirroring test_flash_sales.py) ──────────────────────────────────

def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    u.tenant_id = None
    return u


def _make_fs(fs_id=1, name="Summer Sale", discount_value=Decimal("15.00"),
              is_active=True):
    """Mocked PlatformFlashSale with REAL window datetimes (June 2026)."""
    fs = MagicMock()
    fs.id = fs_id
    fs.name = name
    fs.description = ""
    fs.discount_value = discount_value
    fs.active_from = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    fs.active_until = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
    fs.is_active = is_active
    fs.max_redemptions = None
    fs.redemption_count = 0
    fs.created_at = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    return fs


def _schema_ctx():
    """Context-manager mock for django_tenants.utils.schema_context."""
    mock_ctx = patch("django_tenants.utils.schema_context")
    entered = mock_ctx.start()
    entered.return_value.__enter__ = lambda s: None
    entered.return_value.__exit__ = lambda s, *a: None
    return mock_ctx


# ── A-06: PATCH window validation ────────────────────────────────────────────

class FlashSalePatchWindowTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleDetailView.as_view()

    def _patch(self, fs_id, data, user=None):
        req = self.factory.patch(f"/api/admin/flash-sales/{fs_id}/", data, format="json")
        req.user = user or _admin()
        return self.view(req, fs_id=fs_id)

    def _run_patch(self, fs, data):
        """PATCH against a mocked sale; returns (resp, fs, mock_log)."""
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.views._bust_public_list_cache"):
            mock_fs.objects.get.return_value = fs
            ctx = _schema_ctx()
            try:
                resp = self._patch(fs.id, data)
            finally:
                ctx.stop()
        return resp, fs, mock_log

    def test_patch_both_dates_inverted_returns_400(self):
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {
            "active_from": "2026-07-01T00:00:00Z",
            "active_until": "2026-06-01T00:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "active_from must be before active_until.")
        fs.save.assert_not_called()
        mock_log.assert_not_called()

    def test_patch_only_from_after_stored_until_returns_400(self):
        # Stored window is June; moving only `from` to July inverts it.
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {"active_from": "2026-07-15T00:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "active_from must be before active_until.")
        fs.save.assert_not_called()
        mock_log.assert_not_called()

    def test_patch_only_until_before_stored_from_returns_400(self):
        # Stored window is June; moving only `until` back to May inverts it.
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {"active_until": "2026-05-15T00:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "active_from must be before active_until.")
        fs.save.assert_not_called()
        mock_log.assert_not_called()

    def test_patch_equal_dates_returns_400(self):
        # Same rule as POST (from >= until is rejected) — a zero-length window
        # is never live either.
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {
            "active_from": "2026-06-15T12:00:00Z",
            "active_until": "2026-06-15T12:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        fs.save.assert_not_called()
        mock_log.assert_not_called()

    def test_patch_valid_window_returns_200_and_saves(self):
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {
            "active_from": "2026-06-05T00:00:00Z",
            "active_until": "2026-07-05T00:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        fs.save.assert_called_once()
        mock_log.assert_called_once()
        self.assertEqual(
            fs.active_from, datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(
            fs.active_until, datetime(2026, 7, 5, 0, 0, tzinfo=timezone.utc))

    def test_patch_unrelated_field_does_not_trigger_window_check(self):
        # No date in the payload → the stored (valid) window is untouched and
        # the PATCH succeeds; the check must not false-positive.
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {"discount_value": "20"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        fs.save.assert_called_once()

    def test_patch_invalid_date_string_still_returns_400(self):
        fs = _make_fs()
        resp, fs, mock_log = self._run_patch(fs, {"active_from": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Invalid active_from.")
        fs.save.assert_not_called()


# ── A-04: serializer discount formatting ─────────────────────────────────────

class FlashSaleSerializerDiscountTests(SimpleTestCase):
    def test_discount_trailing_zeros_stripped(self):
        cases = (
            (Decimal("15.00"), "15"),
            (Decimal("12.50"), "12.5"),
            (Decimal("100.00"), "100"),
            (Decimal("0.50"), "0.5"),
            (Decimal("7.25"), "7.25"),
            (Decimal("15"), "15"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                fs = _make_fs(discount_value=raw)
                self.assertEqual(_serialize_flash_sale(fs)["discount_value"], expected)

    def test_get_list_returns_stripped_discount(self):
        """End-to-end through the GET list view, as the admin page reads it."""
        fs = _make_fs(discount_value=Decimal("15.00"))
        factory = APIRequestFactory()
        view = AdminFlashSaleListCreateView.as_view()
        req = factory.get("/api/admin/flash-sales/")
        req.user = _admin()
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.all.return_value = [fs]
            ctx = _schema_ctx()
            try:
                resp = view(req)
            finally:
                ctx.stop()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data[0]["discount_value"], "15")


# ── A-03: POST honours explicit is_active (server contract for the checkbox) ─

class FlashSaleCreateIsActiveTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleListCreateView.as_view()

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/flash-sales/", data, format="json")
        req.user = user or _admin()
        return req

    def test_post_is_active_false_creates_paused_sale(self):
        fs = _make_fs(name="Draft Deal", is_active=False)
        req = self._post({
            "name": "Draft Deal",
            "discount_value": "10",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
            "is_active": False,
        })
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action"), \
             patch("accounts.views._bust_public_list_cache"):
            mock_fs.objects.create.return_value = fs
            ctx = _schema_ctx()
            try:
                resp = self.view(req)
            finally:
                ctx.stop()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(mock_fs.objects.create.call_args[1]["is_active"])

    def test_post_without_is_active_still_defaults_active(self):
        fs = _make_fs(name="Live Deal", is_active=True)
        req = self._post({
            "name": "Live Deal",
            "discount_value": "10",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
        })
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action"), \
             patch("accounts.views._bust_public_list_cache"):
            mock_fs.objects.create.return_value = fs
            ctx = _schema_ctx()
            try:
                resp = self.view(req)
            finally:
                ctx.stop()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_fs.objects.create.call_args[1]["is_active"])
