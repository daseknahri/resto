"""
Tests for tier-upgrade and lead-provision admin views:
  - TierUpgradeRequestListCreateView  GET/POST /api/owner/tier-upgrade/
  - AdminTierUpgradeRequestListView   GET /api/admin/tier-upgrade-requests/
  - AdminTierUpgradeRequestDecisionView PUT /api/admin/tier-upgrade-requests/<id>/decision/
  - LeadProvisionPreviewView          GET /api/admin/leads/<id>/provision-preview/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.views import (
    AdminTierUpgradeRequestDecisionView,
    AdminTierUpgradeRequestListView,
    LeadProvisionPreviewView,
    TierUpgradeRequestListCreateView,
)
from sales.models import TierUpgradeRequest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _passthrough_cm():
    cm = MagicMock()
    cm.__enter__ = lambda s: None
    cm.__exit__ = lambda s, *a: None
    return cm


def _admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    u.pk = 1
    u.id = 1
    return u


def _non_admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


def _owner_user(tenant_id=1):
    from accounts.models import User
    u = MagicMock(spec=User)
    u.__class__ = User
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.is_tenant_owner = True
    u.is_tenant_staff = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, slug="restaurant", schema_name="restaurant")


# ── TierUpgradeRequestListCreateView ─────────────────────────────────────────

class TierUpgradeRequestListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TierUpgradeRequestListCreateView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/tier-upgrade/")
        req.user = user or _owner_user()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/tier-upgrade/", data, format="json")
        req.user = user or _owner_user()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_get_no_tenant_returns_403(self):
        # IsTenantEditor permission rejects when tenant is None before view runs
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_no_tenant_returns_403(self):
        resp = self._post({"target_plan": "growth"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_returns_list_with_tenant(self):
        with patch("sales.views.schema_context", return_value=_passthrough_cm()):
            with patch("sales.views.TierUpgradeRequest") as mock_req:
                mock_qs = MagicMock()
                mock_req.objects.select_related.return_value.filter.return_value.order_by.return_value = mock_qs
                with patch("sales.views.TierUpgradeRequestSerializer") as mock_ser:
                    mock_ser.return_value.data = []
                    resp = self._get(tenant=_tenant())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_post_creates_upgrade_request(self):
        upgrade_req = MagicMock()
        upgrade_req.tenant = _tenant()
        upgrade_req.current_plan = MagicMock(code="starter")
        upgrade_req.target_plan = MagicMock(code="growth")
        upgrade_req.payment_method = "cash"
        upgrade_req.id = 1

        with patch("sales.views.TierUpgradeRequestCreateSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            target_plan = MagicMock(code="growth")
            instance.validated_data = {
                "target_plan": target_plan,
                "payment_method": "cash",
                "payment_reference": "",
                "customer_note": "",
            }
            with patch("sales.views.create_tier_upgrade_request", return_value=upgrade_req):
                with patch("sales.views.log_admin_action"):
                    with patch("sales.views.TierUpgradeRequestSerializer") as mock_resp_ser:
                        mock_resp_ser.return_value.data = {"id": 1}
                        resp = self._post(
                            {"target_plan": "growth"},
                            tenant=_tenant(),
                        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_post_value_error_returns_400(self):
        with patch("sales.views.TierUpgradeRequestCreateSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {
                "target_plan": MagicMock(code="growth"),
                "payment_method": "cash",
                "payment_reference": "",
                "customer_note": "",
            }
            with patch("sales.views.create_tier_upgrade_request", side_effect=ValueError("already pending")):
                resp = self._post({"target_plan": "growth"}, tenant=_tenant())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already pending", resp.data["detail"])

    def test_unauthenticated_returns_403(self):
        u = MagicMock()
        u.is_authenticated = False
        resp = self._get(user=u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── AdminTierUpgradeRequestListView ──────────────────────────────────────────

class AdminTierUpgradeRequestListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminTierUpgradeRequestListView.as_view()

    def _get(self, user=None, params=None):
        req = self.factory.get("/api/admin/tier-upgrade-requests/", params or {})
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_returns_200_with_list(self):
        with patch("sales.views.schema_context", return_value=_passthrough_cm()):
            with patch("sales.views.TierUpgradeRequest") as mock_req:
                mock_qs = MagicMock()
                mock_req.objects.select_related.return_value.order_by.return_value = mock_qs
                mock_qs.filter.return_value = mock_qs
                mock_qs.__getitem__ = lambda s, k: []
                with patch("sales.views.TierUpgradeRequestSerializer") as mock_ser:
                    mock_ser.return_value.data = []
                    resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_status_filter_applied(self):
        with patch("sales.views.schema_context", return_value=_passthrough_cm()):
            with patch("sales.views.TierUpgradeRequest") as mock_req:
                mock_qs = MagicMock()
                mock_req.objects.select_related.return_value.order_by.return_value = mock_qs
                mock_qs.filter.return_value = mock_qs
                mock_qs.__getitem__ = lambda s, k: []
                with patch("sales.views.TierUpgradeRequestSerializer") as mock_ser:
                    mock_ser.return_value.data = []
                    resp = self._get(params={"status": "pending"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ── AdminTierUpgradeRequestDecisionView ──────────────────────────────────────

class AdminTierUpgradeRequestDecisionViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminTierUpgradeRequestDecisionView.as_view()

    def _put(self, data, request_id=1, user=None):
        req = self.factory.put(
            f"/api/admin/tier-upgrade-requests/{request_id}/decision/",
            data,
            format="json",
        )
        req.user = user or _admin()
        return self.view(req, request_id=request_id)

    def test_non_admin_returns_403(self):
        resp = self._put({"decision": "approve"}, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_not_found_returns_404(self):
        with patch("sales.views.TierUpgradeDecisionSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {"decision": "approve", "admin_note": ""}
            with patch("sales.views.decide_tier_upgrade_request", side_effect=TierUpgradeRequest.DoesNotExist):
                resp = self._put({"decision": "approve"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_value_error_returns_400(self):
        with patch("sales.views.TierUpgradeDecisionSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {"decision": "approve", "admin_note": ""}
            with patch("sales.views.decide_tier_upgrade_request", side_effect=ValueError("bad state")):
                resp = self._put({"decision": "approve"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_returns_200(self):
        result = MagicMock()
        result.upgrade_request = MagicMock()
        result.new_plan = MagicMock(name="Growth")
        result.new_plan.name = "Growth"
        result.previous_plan = MagicMock(code="starter")
        result.previous_plan.code = "starter"
        result.new_plan.code = "growth"
        result.tenant = _tenant()

        with patch("sales.views.TierUpgradeDecisionSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {
                "decision": "approve",
                "admin_note": "Looks good",
                "payment_reference": "PAY-123",
            }
            with patch("sales.views.decide_tier_upgrade_request", return_value=result):
                with patch("sales.views.log_admin_action"):
                    with patch("sales.views.TierUpgradeRequestSerializer") as mock_resp_ser:
                        mock_resp_ser.return_value.data = {"id": 1}
                        resp = self._put({"decision": "approve"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("Tenant upgraded to", resp.data["detail"])

    def test_reject_returns_200(self):
        result = MagicMock()
        result.upgrade_request = MagicMock()
        result.new_plan = MagicMock(name="Starter")
        result.new_plan.name = "Starter"
        result.previous_plan = MagicMock(code="starter")
        result.previous_plan.code = "starter"
        result.new_plan.code = "starter"
        result.tenant = _tenant()

        with patch("sales.views.TierUpgradeDecisionSerializer") as mock_ser:
            instance = mock_ser.return_value
            instance.is_valid.return_value = True
            instance.validated_data = {"decision": "reject", "admin_note": "Not qualified"}
            with patch("sales.views.decide_tier_upgrade_request", return_value=result):
                with patch("sales.views.log_admin_action"):
                    with patch("sales.views.TierUpgradeRequestSerializer") as mock_resp_ser:
                        mock_resp_ser.return_value.data = {"id": 1}
                        resp = self._put({"decision": "reject"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Upgrade request rejected.")


# ── TierUpgradeDecisionSerializer.invoice_amount (RISK SER-1) ──────────────────

class TierUpgradeDecisionSerializerInvoiceAmountTests(SimpleTestCase):
    """invoice_amount migrated onto QuantizedMoneyField (config/drf_fields.py) — pins the
    behavior-preservation contract at this specific field (full generic contract is covered
    by test_ser1_money_field.py): over-precision rounds instead of rejecting, an out-of-range
    magnitude is a clean 400 instead of the old DB-overflow 500, and allow_null/optional
    (used on reject, where invoice_amount is never sent) still passes through unchanged."""

    def _serializer(self, **overrides):
        from sales.serializers import TierUpgradeDecisionSerializer
        data = {"decision": "approve"}
        data.update(overrides)
        return TierUpgradeDecisionSerializer(data=data)

    def test_over_precision_amount_is_rounded(self):
        from decimal import Decimal
        s = self._serializer(invoice_amount="99.005")
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["invoice_amount"], Decimal("99.00"))

    def test_out_of_range_magnitude_rejected_cleanly(self):
        s = self._serializer(invoice_amount="99999999999.99")
        self.assertFalse(s.is_valid())
        self.assertIn("invoice_amount", s.errors)

    def test_omitted_amount_still_optional(self):
        s = self._serializer(decision="reject")
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("invoice_amount", s.validated_data)

    def test_null_amount_still_allowed(self):
        s = self._serializer(invoice_amount=None)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["invoice_amount"])


# ── LeadProvisionPreviewView ──────────────────────────────────────────────────

class LeadProvisionPreviewViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = LeadProvisionPreviewView.as_view()

    def _get(self, lead_id=1, user=None, params=None):
        req = self.factory.get(f"/api/admin/leads/{lead_id}/provision-preview/", params or {})
        req.user = user or _admin()
        return self.view(req, lead_id=lead_id)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_lead_not_found_returns_404(self):
        from django.http import Http404
        with patch("sales.views.get_object_or_404", side_effect=Http404):
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_preview_data(self):
        lead = MagicMock()
        preview = {
            "slug": "my-restaurant",
            "schema_name": "my_restaurant",
            "domain": "my-restaurant.localhost",
            "domain_suffix": "localhost",
        }
        with patch("sales.views.get_object_or_404", return_value=lead):
            with patch("sales.views.preview_lead_provision", return_value=preview):
                resp = self._get(params={"domain_suffix": "localhost"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["slug"], "my-restaurant")

    def test_uses_requested_slug_param(self):
        lead = MagicMock()
        with patch("sales.views.get_object_or_404", return_value=lead):
            with patch("sales.views.preview_lead_provision", return_value={}) as mock_preview:
                resp = self._get(params={"requested_slug": "custom-slug"})
        # Verify preview was called with requested_slug
        mock_preview.assert_called_once_with(lead, domain_suffix="localhost", requested_slug="custom-slug")
