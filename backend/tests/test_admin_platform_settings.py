"""Tests for AdminPlatformSettingsView (platform-wide admin-editable settings). No DB."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

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


class AdminPlatformSettingsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminPlatformSettingsView.as_view()

    def test_non_admin_get_403(self):
        req = self.factory.get("/api/admin/settings/")
        req.user = _non_admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.PlatformConfig")
    def test_admin_get_returns_threshold(self, mock_pc):
        mock_pc.get_solo.return_value = MagicMock(wallet_charge_approval_threshold=Decimal("50.00"))
        req = self.factory.get("/api/admin/settings/")
        req.user = _admin()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["wallet_charge_approval_threshold"], "50.00")

    @patch("accounts.models.PlatformConfig")
    def test_admin_patch_updates_threshold(self, mock_pc):
        cfg = MagicMock(wallet_charge_approval_threshold=Decimal("50.00"))
        cfg.save = MagicMock()
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
        mock_pc.get_solo.return_value = MagicMock(wallet_charge_approval_threshold=Decimal("50.00"))
        req = self.factory.patch(
            "/api/admin/settings/", {"wallet_charge_approval_threshold": "-5"}, format="json"
        )
        req.user = _admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.PlatformConfig")
    def test_admin_patch_invalid_400(self, mock_pc):
        mock_pc.get_solo.return_value = MagicMock(wallet_charge_approval_threshold=Decimal("50.00"))
        req = self.factory.patch(
            "/api/admin/settings/", {"wallet_charge_approval_threshold": "abc"}, format="json"
        )
        req.user = _admin()
        self.assertEqual(self.view(req).status_code, status.HTTP_400_BAD_REQUEST)
