"""
Tests for loyalty views:
  - OwnerLoyaltyView            GET/PATCH /api/owner/loyalty/
  - CustomerLoyaltyConfigView   GET /api/customer/loyalty/config/
  - CustomerLoyaltyRedeemView   POST /api/customer/loyalty/redeem/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import CustomerLoyaltyConfigView, CustomerLoyaltyRedeemView, OwnerLoyaltyView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _outsider(tenant_id=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_loyalty_config(enabled=True, points_per_unit=10, redeem_threshold=100,
                          points_value="0.0100"):
    cfg = MagicMock()
    cfg.enabled = enabled
    cfg.points_per_unit = points_per_unit
    cfg.redeem_threshold = redeem_threshold
    cfg.points_value = Decimal(points_value)
    cfg.updated_at = MagicMock()
    cfg.updated_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return cfg


# ── OwnerLoyaltyView ──────────────────────────────────────────────────────────

class OwnerLoyaltyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerLoyaltyView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/loyalty/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _patch(self, data, user=None, tenant=None):
        req = self.factory.patch("/api/owner/loyalty/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_outsider_returns_403(self):
        resp = self._patch({"enabled": True}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET ───────────────────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    def test_get_returns_config(self, mock_cfg_objs):
        cfg = _make_loyalty_config(enabled=False)
        mock_cfg_objs.get_or_create.return_value = (cfg, False)

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("enabled", "points_per_unit", "redeem_threshold", "points_value", "updated_at"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    # ── PATCH ─────────────────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    def test_patch_enables_loyalty(self, mock_cfg_objs):
        cfg = _make_loyalty_config(enabled=False)
        mock_cfg_objs.get_or_create.return_value = (cfg, False)

        resp = self._patch({"enabled": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(cfg.enabled)
        cfg.save.assert_called_once()

    @patch("menu.views.LoyaltyConfig.objects")
    def test_patch_updates_points_per_unit(self, mock_cfg_objs):
        cfg = _make_loyalty_config(points_per_unit=10)
        mock_cfg_objs.get_or_create.return_value = (cfg, False)

        resp = self._patch({"points_per_unit": 20})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cfg.points_per_unit, 20)

    @patch("menu.views.LoyaltyConfig.objects")
    def test_patch_invalid_points_per_unit_ignored(self, mock_cfg_objs):
        cfg = _make_loyalty_config(points_per_unit=10)
        mock_cfg_objs.get_or_create.return_value = (cfg, False)

        resp = self._patch({"points_per_unit": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Original value unchanged
        self.assertEqual(cfg.points_per_unit, 10)

    @patch("menu.views.LoyaltyConfig.objects")
    def test_patch_updates_points_value(self, mock_cfg_objs):
        cfg = _make_loyalty_config()
        mock_cfg_objs.get_or_create.return_value = (cfg, False)

        resp = self._patch({"points_value": "0.0500"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cfg.points_value, Decimal("0.0500"))


# ── CustomerLoyaltyConfigView ─────────────────────────────────────────────────

class CustomerLoyaltyConfigViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyConfigView.as_view()

    def _get(self, tenant=None):
        req = self.factory.get("/api/customer/loyalty/config/")
        req.user = MagicMock(is_authenticated=False)
        req.tenant = tenant or _tenant()
        return self.view(req)

    @patch("menu.views.LoyaltyConfig.objects")
    def test_disabled_config_returns_enabled_false(self, mock_cfg_objs):
        cfg = _make_loyalty_config(enabled=False)
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["enabled"])

    @patch("menu.views.LoyaltyConfig.objects")
    def test_no_config_returns_enabled_false(self, mock_cfg_objs):
        mock_cfg_objs.filter.return_value.first.return_value = None

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["enabled"])

    @patch("menu.views.LoyaltyConfig.objects")
    def test_enabled_config_returns_full_info(self, mock_cfg_objs):
        cfg = _make_loyalty_config(enabled=True, points_per_unit=10,
                                   redeem_threshold=100, points_value="0.0100")
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["enabled"])
        for field in ("points_per_unit", "redeem_threshold", "points_value"):
            self.assertIn(field, resp.data, f"Missing field: {field}")


# ── CustomerLoyaltyRedeemView ─────────────────────────────────────────────────

class CustomerLoyaltyRedeemViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()

    def _post(self, data, customer_id=1, tenant=None):
        req = self.factory.post("/api/customer/loyalty/redeem/", data, format="json")
        req.user = MagicMock(is_authenticated=True)
        req.user.customer_id = customer_id
        req.tenant = tenant or _tenant()
        return req

    # ── Customer not found ────────────────────────────────────────────────────

    @patch("accounts.models.Customer.objects")
    def test_customer_not_found_returns_404(self, mock_cust_objs):
        from accounts.models import Customer as CustomerModel
        mock_cust_objs.get.side_effect = CustomerModel.DoesNotExist

        req = self._post({"points": 50})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Loyalty disabled ──────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_loyalty_disabled_returns_400(self, mock_cust_objs, mock_cfg_objs):
        customer = MagicMock()
        customer.pk = 1
        customer.loyalty_points = 200
        mock_cust_objs.get.return_value = customer
        mock_cfg_objs.filter.return_value.first.return_value = None  # no active config

        req = self._post({"points": 50})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "loyalty_disabled")

    # ── Below threshold ───────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_below_threshold_returns_400(self, mock_cust_objs, mock_cfg_objs):
        customer = MagicMock()
        customer.pk = 1
        customer.loyalty_points = 50  # below redeem_threshold of 100
        mock_cust_objs.get.return_value = customer

        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100)
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 50})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "below_threshold")

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_valid_redemption_returns_200(self, mock_cust_objs, mock_cfg_objs, mock_tx_objs):
        customer = MagicMock()
        customer.pk = 1
        customer.loyalty_points = 200
        mock_cust_objs.get.return_value = customer

        locked = MagicMock()
        locked.loyalty_points = 200
        locked.wallet_balance = Decimal("10.00")
        mock_cust_objs.select_for_update.return_value.get.return_value = locked

        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100, points_value="0.0100")
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 100})
        with patch("django.db.transaction.atomic"):
            with patch("django.db.connection") as mock_dbc:
                mock_dbc.tenant = SimpleNamespace(id=1)
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("redeemed_points", "credit_amount", "new_points_balance", "new_wallet_balance"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertEqual(resp.data["redeemed_points"], 100)
        self.assertEqual(resp.data["credit_amount"], "1.00")  # 100 * 0.01
