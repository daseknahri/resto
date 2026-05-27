"""
Tests for analytics, chart, and slot availability views:
  - OwnerBestSellersView        GET /api/owner/best-sellers/
  - OwnerRevenueChartView       GET /api/owner/revenue-chart/
  - AnalyticsSummaryView        GET /api/analytics/summary/
  - OwnerAnalyticsExportView    GET /api/owner/analytics/export/
  - SlotAvailabilityView        GET /api/availability/
  - OwnerInvoiceView            GET /api/owner/invoice/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import (
    OwnerBestSellersView,
    OwnerRevenueChartView,
    AnalyticsSummaryView,
    OwnerAnalyticsExportView,
    SlotAvailabilityView,
    OwnerInvoiceView,
)
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


def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1, schema_name="tenant1"):
    return SimpleNamespace(id=tenant_id, schema_name=schema_name)


def _public_tenant():
    return SimpleNamespace(id=0, schema_name="public")


# ── OwnerBestSellersView ──────────────────────────────────────────────────────

class OwnerBestSellersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerBestSellersView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/best-sellers/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_best_sellers_structure(self):
        with patch("menu.views.OrderItem") as mock_oi:
            qs = MagicMock()
            mock_oi.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []

            with patch("menu.views.Order") as mock_order:
                mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = "MAD"
                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("period", "currency", "by_count", "by_revenue"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    def test_period_clamped_to_90(self):
        with patch("menu.views.OrderItem") as mock_oi:
            qs = MagicMock()
            mock_oi.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []
            with patch("menu.views.Order") as mock_order:
                mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
                resp = self._get(params={"period": "999"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(resp.data["period"], 90)

    def test_invalid_period_defaults_to_30(self):
        with patch("menu.views.OrderItem") as mock_oi:
            qs = MagicMock()
            mock_oi.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []
            with patch("menu.views.Order") as mock_order:
                mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
                resp = self._get(params={"period": "bad"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period"], 30)


# ── OwnerRevenueChartView ─────────────────────────────────────────────────────

class OwnerRevenueChartViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRevenueChartView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/revenue-chart/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_revenue_chart_structure(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.filter.return_value = qs
            qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("period", "currency", "days"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertIsInstance(resp.data["days"], list)

    def test_days_list_length_matches_period(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.filter.return_value = qs
            qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
            resp = self._get(params={"period": "7"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period"], 7)
        self.assertEqual(len(resp.data["days"]), 7)

    def test_invalid_period_defaults_to_14(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.filter.return_value = qs
            qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            mock_order.objects.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
            resp = self._get(params={"period": "nope"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period"], 14)


# ── AnalyticsSummaryView ──────────────────────────────────────────────────────

class AnalyticsSummaryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AnalyticsSummaryView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/analytics/summary/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_no_tenant_returns_400(self):
        req = self.factory.get("/api/analytics/summary/")
        req.user = _owner()
        # No req.tenant set
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_schema_returns_400(self):
        resp = self._get(tenant=_public_tenant())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_access(self):
        """Staff (TENANT_STAFF) in the same tenant can access analytics."""
        with patch("menu.views.AnalyticsEvent") as mock_ae:
            qs = MagicMock()
            mock_ae.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value = []
            qs.count.return_value = 0
            qs.exclude.return_value.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []
            resp = self._get(user=_staff())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_returns_analytics_structure(self):
        with patch("menu.views.AnalyticsEvent") as mock_ae:
            qs = MagicMock()
            mock_ae.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value = []
            qs.count.return_value = 5
            qs.exclude.return_value.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []
            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("days", "since", "total_events", "counts", "top_categories", "top_dishes", "interaction_rate_pct"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    def test_days_clamped_to_90(self):
        with patch("menu.views.AnalyticsEvent") as mock_ae:
            qs = MagicMock()
            mock_ae.objects.filter.return_value = qs
            qs.values.return_value.annotate.return_value = []
            qs.count.return_value = 0
            qs.exclude.return_value.values.return_value.annotate.return_value.order_by.return_value.__getitem__.return_value = []
            resp = self._get(params={"days": "999"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(resp.data["days"], 90)


# ── OwnerAnalyticsExportView ──────────────────────────────────────────────────

class OwnerAnalyticsExportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerAnalyticsExportView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/analytics/export/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_no_tenant_returns_400(self):
        req = self.factory.get("/api/owner/analytics/export/")
        req.user = _owner()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_schema_returns_400(self):
        resp = self._get(tenant=_public_tenant())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_csv_response(self):
        with patch("menu.views.AnalyticsEvent") as mock_ae:
            qs = MagicMock()
            mock_ae.objects.filter.return_value = qs
            qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            resp = self._get()

        self.assertIn("csv", resp.get("Content-Type", "").lower())
        self.assertIn("attachment", resp.get("Content-Disposition", ""))

    def test_csv_contains_header(self):
        with patch("menu.views.AnalyticsEvent") as mock_ae:
            qs = MagicMock()
            mock_ae.objects.filter.return_value = qs
            qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            resp = self._get()

        self.assertIn(b"date", resp.content)
        self.assertIn(b"event_type", resp.content)


# ── SlotAvailabilityView ──────────────────────────────────────────────────────

class SlotAvailabilityViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SlotAvailabilityView.as_view()

    def _get(self, params=None, tenant=None):
        req = self.factory.get("/api/availability/", params or {})
        req.user = MagicMock(is_authenticated=False)
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_no_tenant_returns_400(self):
        # No req.tenant attribute
        req = self.factory.get("/api/availability/", {"date": "2026-06-01"})
        req.user = MagicMock(is_authenticated=False)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_date_returns_400(self):
        resp = self._get(params={}, tenant=_tenant())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_returns_400(self):
        resp = self._get(params={"date": "not-a-date"}, tenant=_tenant())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_date_returns_200(self):
        tenant = _tenant()
        profile = MagicMock()
        profile.max_covers_per_slot = 0
        profile.slot_duration_minutes = 60

        with patch("menu.views.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = profile
            resp = self._get(params={"date": "2026-06-01"}, tenant=tenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("date", "slots", "max_covers", "slot_duration_minutes", "capacity_enabled"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    def test_capacity_disabled_when_max_covers_zero(self):
        profile = MagicMock()
        profile.max_covers_per_slot = 0
        profile.slot_duration_minutes = 60

        with patch("menu.views.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = profile
            resp = self._get(params={"date": "2026-06-01"}, tenant=_tenant())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["capacity_enabled"])

    def test_no_profile_returns_empty_slots(self):
        with patch("menu.views.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = None
            resp = self._get(params={"date": "2026-06-01"}, tenant=_tenant())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ── OwnerInvoiceView ──────────────────────────────────────────────────────────

class OwnerInvoiceViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerInvoiceView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/invoice/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_request_id_returns_400(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_not_found_returns_404(self):
        with patch("sales.models.TierUpgradeRequest") as mock_tur:
            mock_tur.DoesNotExist = Exception
            mock_tur.objects.select_related.return_value.get.side_effect = mock_tur.DoesNotExist
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                resp = self._get(params={"request_id": "999"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_not_approved_returns_400(self):
        upgrade_req = MagicMock()
        upgrade_req.status = "pending"

        with patch("sales.models.TierUpgradeRequest") as mock_tur:
            mock_tur.Status = MagicMock()
            mock_tur.Status.APPROVED = "approved"
            mock_tur.objects.select_related.return_value.get.return_value = upgrade_req
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                resp = self._get(params={"request_id": "1"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_invoice_amount_returns_400(self):
        upgrade_req = MagicMock()
        upgrade_req.status = "approved"
        upgrade_req.invoice_amount = None

        with patch("sales.models.TierUpgradeRequest") as mock_tur:
            mock_tur.Status = MagicMock()
            mock_tur.Status.APPROVED = "approved"
            mock_tur.objects.select_related.return_value.get.return_value = upgrade_req
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                resp = self._get(params={"request_id": "1"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
