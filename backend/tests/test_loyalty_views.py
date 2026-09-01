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
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.authentication import CustomerSessionAuthentication
from accounts.permissions import IsCustomer
from menu.views import (
    CustomerLoyaltyConfigView,
    CustomerLoyaltyHistoryView,
    CustomerLoyaltyRedeemView,
    OwnerLoyaltyView,
)
from accounts.models import Customer, User


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

    @patch("menu.views.Order.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    def test_get_returns_config(self, mock_cfg_objs, mock_order_objs):
        cfg = _make_loyalty_config(enabled=False)
        mock_cfg_objs.get_or_create.return_value = (cfg, False)
        # Perf fix: stats are now ONE Order.objects.filter(...).aggregate(...) call
        # (was: a separate .values().distinct().count() PLUS a second .aggregate()
        # over the identical filtered queryset).
        mock_qs = MagicMock()
        mock_qs.aggregate.return_value = {"enrolled_customers": 7, "total_points_issued": 350}
        mock_order_objs.filter.return_value = mock_qs

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("enabled", "points_per_unit", "redeem_threshold", "points_value", "updated_at"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

        # Stats come from the single merged aggregate call — not the old two-query shape.
        mock_qs.aggregate.assert_called_once()
        mock_qs.values.assert_not_called()
        self.assertEqual(resp.data["stats"]["enrolled_customers"], 7)
        self.assertEqual(resp.data["stats"]["total_points_issued"], 350)

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
        from django.core.cache import cache
        cache.clear()  # isolate the per-customer loyalty_redeem throttle counter
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()

    def _post(self, data, principal=None, tenant=None):
        # IDENTITY-1: the view resolves the customer off request.user (a real Customer
        # principal via customer_or_none), so force-authenticate one. principal=None leaves
        # the request anonymous, to exercise the IsCustomer denial.
        req = self.factory.post("/api/customer/loyalty/redeem/", data, format="json")
        if principal is not None:
            force_authenticate(req, user=principal)
        req.tenant = tenant or _tenant()
        return req

    # ── Auth: only a signed-in Customer principal may redeem ───────────────────

    def test_anonymous_returns_401(self):
        # No customer principal → IsCustomer denies (401). Before the IDENTITY-1 fix this
        # view ran IsAuthenticated with NO customer auth class, so it never resolved a real
        # customer here — every signed-in customer 404'd on request.user.customer_id.
        req = self._post({"points": 50}, principal=None)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_user_is_not_a_customer_returns_403(self):
        # A staff User is authenticated but is NOT a Customer principal → IsCustomer denies,
        # so a staff cookie can't reach the customer wallet endpoint. (403, not 401: the
        # request IS authenticated — just not as a customer — so DRF renders permission
        # denied rather than "not authenticated".)
        req = self._post({"points": 50}, principal=_owner())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Loyalty disabled ──────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    def test_loyalty_disabled_returns_400(self, mock_cfg_objs):
        customer = Customer(id=1, phone_verified=True, loyalty_points=200)
        mock_cfg_objs.filter.return_value.first.return_value = None  # no active config

        req = self._post({"points": 50}, principal=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "loyalty_disabled")

    # ── Below threshold ───────────────────────────────────────────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    def test_below_threshold_returns_400(self, mock_cfg_objs):
        customer = Customer(id=1, phone_verified=True, loyalty_points=50)  # below threshold 100

        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100)
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 50}, principal=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "below_threshold")

    # ── Unverified phone blocked (FIX 1: wallet-bypass guard) ────────────────

    @patch("menu.views.LoyaltyConfig.objects")
    def test_principal_unverified_phone_returns_403(self, mock_cfg_objs):
        """Pre-flight guard: a signed-in customer whose phone is unverified can't convert
        points to wallet credit (checked on the principal, before the row lock)."""
        customer = Customer(id=1, phone_verified=False, loyalty_points=200)
        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100, points_value="0.0100")
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 100}, principal=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "phone_unverified")

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_unverified_phone_at_lock_returns_403(self, mock_cust_objs, mock_cfg_objs, mock_tx_objs):
        """Defense-in-depth: even if the principal looked verified, the row re-read under
        select_for_update re-checks phone_verified and refuses (code unverified_phone) —
        same guard that credit_wallet enforces for direct top-ups."""
        customer = Customer(id=1, phone_verified=True, loyalty_points=200,
                            wallet_balance=Decimal("10.00"))

        locked = MagicMock()
        locked.loyalty_points = 200
        locked.wallet_balance = Decimal("10.00")
        locked.phone_verified = False  # unverified at lock time!
        mock_cust_objs.select_for_update.return_value.get.return_value = locked

        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100, points_value="0.0100")
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 100}, principal=customer)
        with patch("django.db.transaction.atomic"):
            with patch("django.db.connection") as mock_dbc:
                mock_dbc.tenant = SimpleNamespace(id=1)
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "unverified_phone")

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.LoyaltyConfig.objects")
    @patch("accounts.models.Customer.objects")
    def test_valid_redemption_returns_200(self, mock_cust_objs, mock_cfg_objs, mock_tx_objs):
        customer = Customer(id=1, phone_verified=True, loyalty_points=200,
                            wallet_balance=Decimal("10.00"))

        locked = MagicMock()
        locked.loyalty_points = 200
        locked.wallet_balance = Decimal("10.00")
        locked.phone_verified = True  # verified — passes the FIX 1 guard
        mock_cust_objs.select_for_update.return_value.get.return_value = locked

        cfg = _make_loyalty_config(enabled=True, redeem_threshold=100, points_value="0.0100")
        mock_cfg_objs.filter.return_value.first.return_value = cfg

        req = self._post({"points": 100}, principal=customer)
        with patch("django.db.transaction.atomic"):
            with patch("django.db.connection") as mock_dbc:
                mock_dbc.tenant = SimpleNamespace(id=1)
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("redeemed_points", "credit_amount", "new_points_balance", "new_wallet_balance"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertEqual(resp.data["redeemed_points"], 100)
        self.assertEqual(resp.data["credit_amount"], "1.00")  # 100 * 0.01


# ── CustomerLoyaltyHistoryView ────────────────────────────────────────────────

class CustomerLoyaltyHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyHistoryView.as_view()

    def _get(self, principal=None, tenant=None):
        req = self.factory.get("/api/customer/loyalty/history/")
        if principal is not None:
            force_authenticate(req, user=principal)
        req.tenant = tenant or _tenant()
        return req

    def test_anonymous_returns_401(self):
        resp = self.view(self._get(principal=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_user_is_not_a_customer_returns_403(self):
        # Authenticated staff principal, but not a Customer → IsCustomer denies (403, as above).
        resp = self.view(self._get(principal=_owner()))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("menu.views.Order.objects")
    def test_customer_gets_ledger_with_balance(self, mock_order_objs, mock_tx_objs):
        # A real, signed-in customer resolves via customer_or_none and gets a 200 ledger —
        # the exact path the old request.user.customer_id resolution broke (it 404'd here).
        customer = Customer(id=1, loyalty_points=200, lifetime_loyalty_points=500)
        # Empty earn + redeem querysets (the resolution, not the aggregation, is under test).
        mock_order_objs.filter.return_value.only.return_value.order_by.return_value = []
        mock_tx_objs.filter.return_value.order_by.return_value = []

        resp = self.view(self._get(principal=customer))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["balance"], 200)
        self.assertEqual(resp.data["lifetime"], 500)
        self.assertEqual(resp.data["events"], [])


# ── Auth contract (regression guard for the IDENTITY-1-class defect) ──────────

class LoyaltyCustomerViewAuthContractTests(SimpleTestCase):
    """Both customer loyalty views MUST authenticate customers via
    CustomerSessionAuthentication and gate on IsCustomer. The original defect shipped
    `permission_classes = [IsAuthenticated]` with NO customer auth class and resolved the
    customer via `request.user.customer_id` — so no customer auth ran, and a Customer
    principal's PK is `.id` (never `.customer_id`), 404ing every real customer. This asserts
    the class-level contract so that regression can't silently return."""

    def test_redeem_view_auth_and_permission_classes(self):
        self.assertIn(CustomerSessionAuthentication,
                      CustomerLoyaltyRedeemView.authentication_classes)
        self.assertIn(IsCustomer, CustomerLoyaltyRedeemView.permission_classes)

    def test_history_view_auth_and_permission_classes(self):
        self.assertIn(CustomerSessionAuthentication,
                      CustomerLoyaltyHistoryView.authentication_classes)
        self.assertIn(IsCustomer, CustomerLoyaltyHistoryView.permission_classes)
