"""Tests for AdminPlatformSettingsView (platform-wide admin-editable settings). No DB."""
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import AdminPlatformSettingsView


def _admin():
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = False
    u.is_staff = False
    return u


def _non_admin():
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


def _make_cfg(**kwargs):
    """Return a MagicMock PlatformConfig with sensible defaults."""
    defaults = dict(
        wallet_charge_approval_threshold=Decimal("50.00"),
        ride_base_fare=Decimal("8.00"),
        ride_per_km=Decimal("3.50"),
        ride_per_minute=Decimal("0.00"),
        ride_minimum_fare=Decimal("12.00"),
        ride_commission_pct=Decimal("0.00"),
    )
    defaults.update(kwargs)
    cfg = MagicMock(**defaults)
    cfg.save = MagicMock()
    return cfg


class AdminPlatformSettingsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminPlatformSettingsView.as_view()

    # ── access control ──────────────────────────────────────────────────────────

    def test_non_admin_get_403(self):
        req = self.factory.get("/api/admin/settings/")
        req.user = _non_admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_patch_403(self):
        req = self.factory.patch(
            "/api/admin/settings/", {"ride_per_km": "5.00"}, format="json"
        )
        req.user = _non_admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_403_FORBIDDEN)

    # ── GET serialization ───────────────────────────────────────────────────────

    @patch("accounts.models.PlatformConfig")
    def test_admin_get_returns_threshold(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg(wallet_charge_approval_threshold=Decimal("50.00"))
        req = self.factory.get("/api/admin/settings/")
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["wallet_charge_approval_threshold"], "50.00")

    @patch("accounts.models.PlatformConfig")
    def test_get_includes_ride_fields(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg(
            ride_base_fare=Decimal("8.00"),
            ride_per_km=Decimal("3.50"),
            ride_per_minute=Decimal("0.50"),
            ride_minimum_fare=Decimal("12.00"),
            ride_commission_pct=Decimal("10.00"),
        )
        req = self.factory.get("/api/admin/settings/")
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["ride_base_fare"], "8.00")
        self.assertEqual(resp.data["ride_per_km"], "3.50")
        self.assertEqual(resp.data["ride_per_minute"], "0.50")
        self.assertEqual(resp.data["ride_minimum_fare"], "12.00")
        self.assertEqual(resp.data["ride_commission_pct"], "10.00")

    # ── PATCH: threshold (existing behaviour preserved) ─────────────────────────

    @patch("accounts.models.PlatformConfig")
    def test_admin_patch_updates_threshold(self, mock_pc):
        cfg = _make_cfg(wallet_charge_approval_threshold=Decimal("50.00"))
        mock_pc.get_solo.return_value = cfg
        req = self.factory.patch(
            "/api/admin/settings/", {"wallet_charge_approval_threshold": "75.50"}, format="json"
        )
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cfg.wallet_charge_approval_threshold, Decimal("75.50"))
        self.assertEqual(resp.data["wallet_charge_approval_threshold"], "75.50")
        cfg.save.assert_called_once()

    @patch("accounts.models.PlatformConfig")
    def test_admin_patch_negative_400(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg()
        req = self.factory.patch(
            "/api/admin/settings/", {"wallet_charge_approval_threshold": "-5"}, format="json"
        )
        req.user = _admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.PlatformConfig")
    def test_admin_patch_invalid_400(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg()
        req = self.factory.patch(
            "/api/admin/settings/", {"wallet_charge_approval_threshold": "abc"}, format="json"
        )
        req.user = _admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_400_BAD_REQUEST)

    # ── PATCH: ride_per_km ──────────────────────────────────────────────────────

    @patch("accounts.views.log_admin_action")
    @patch("accounts.models.PlatformConfig")
    def test_patch_ride_per_km_updates_and_returns(self, mock_pc, mock_log):
        cfg = _make_cfg(ride_per_km=Decimal("3.50"))
        mock_pc.get_solo.return_value = cfg
        req = self.factory.patch(
            "/api/admin/settings/", {"ride_per_km": "5.00"}, format="json"
        )
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cfg.ride_per_km, Decimal("5.00"))
        self.assertEqual(resp.data["ride_per_km"], "5.00")
        # update_fields subset house rule: only the changed field + updated_at
        save_kwargs = cfg.save.call_args
        update_fields = save_kwargs[1]["update_fields"]
        self.assertIn("ride_per_km", update_fields)
        self.assertIn("updated_at", update_fields)
        self.assertNotIn("ride_base_fare", update_fields)
        # audit log called once with changed field
        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        self.assertIn("ride_per_km", log_kwargs["metadata"]["changed_fields"])

    # ── PATCH: commission > 100 → 400 ──────────────────────────────────────────

    @patch("accounts.models.PlatformConfig")
    def test_commission_101_returns_400(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg()
        req = self.factory.patch(
            "/api/admin/settings/", {"ride_commission_pct": "101"}, format="json"
        )
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ride_commission_pct", resp.data["detail"])

    # ── PATCH: negative ride fare → 400 ────────────────────────────────────────

    @patch("accounts.models.PlatformConfig")
    def test_negative_ride_base_fare_returns_400(self, mock_pc):
        mock_pc.get_solo.return_value = _make_cfg()
        req = self.factory.patch(
            "/api/admin/settings/", {"ride_base_fare": "-1"}, format="json"
        )
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── PATCH: no change → save NOT called ─────────────────────────────────────

    @patch("accounts.views.log_admin_action")
    @patch("accounts.models.PlatformConfig")
    def test_patch_no_known_field_does_not_save(self, mock_pc, mock_log):
        cfg = _make_cfg()
        mock_pc.get_solo.return_value = cfg
        req = self.factory.patch(
            "/api/admin/settings/", {"unknown_field": "99"}, format="json"
        )
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        cfg.save.assert_not_called()
        mock_log.assert_not_called()
