"""
Tests for OwnerDashboardView
GET /api/owner/dashboard/

The full happy-path requires schema_context, analytics aggregation, Plan lookups,
and TierUpgradeRequest queries — all of which are better covered by integration
tests. These unit tests cover the auth/permission guards and response shape
using aggressive mocking of the DB layer.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from sales.views import OwnerDashboardView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 1
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, is_active=True)


def _analytics_qs_mock():
    """
    Return a queryset mock that satisfies the full chain used by OwnerDashboardView:
      .filter(...)
      .values("event_type").annotate(count=Count("id"))          # → iterable of {}
      .exclude(...).values("slug").annotate(...).order_by(...)[:5]  # → []
    """
    annotated = MagicMock()
    annotated.__iter__ = lambda s: iter([])  # raw_counts loop → empty
    order_result = MagicMock()
    order_result.__getitem__ = lambda s, k: []   # [:5] → []
    annotated.order_by.return_value = order_result

    qs = MagicMock()
    qs.count.return_value = 0
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.values.return_value.annotate.return_value = annotated
    return qs


def _order_qs_mock():
    """Minimal Order queryset mock for the revenue aggregation chain."""
    daily_result = MagicMock()
    daily_result.__iter__ = lambda s: iter([])

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.aggregate.return_value = {
        "total_revenue": None, "order_count": 0,
        "mkt_count": 0, "mkt_revenue": None, "mkt_commission": None,
    }
    qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = daily_result
    return qs


def _orderitem_qs_mock():
    """Minimal OrderItem queryset mock for the popular_dishes aggregation chain."""
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    # .values().annotate().order_by()[:10] must be iterable → return empty list
    qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
    return qs


# ── Auth/permission tests ─────────────────────────────────────────────────────

class OwnerDashboardViewAuthTests(SimpleTestCase):
    """Verify the auth/permission guards fire before any DB work is done."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDashboardView.as_view()

    def test_unauthenticated_returns_403(self):
        anon = MagicMock()
        anon.is_authenticated = False
        req = self.factory.get("/api/owner/dashboard/")
        req.user = anon
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_user_returns_403(self):
        wrong_user = _owner(tenant_id=99)
        req = self.factory.get("/api/owner/dashboard/")
        force_authenticate(req, user=wrong_user)
        req.user = wrong_user
        req.tenant = _tenant(tid=1)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_tenant_on_request_returns_403(self):
        """IsTenantEditor rejects when tenant is None, producing 403."""
        user = _owner()
        req = self.factory.get("/api/owner/dashboard/")
        force_authenticate(req, user=user)
        req.user = user
        # Deliberately omit req.tenant
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── Response shape tests ──────────────────────────────────────────────────────

def _apply_common_mocks(
    mock_ts,
    mock_upgrade_req,
    mock_plan,
    mock_tenant,
    mock_analytics,
    mock_order,
    mock_dish,
    mock_cat,
    mock_schema,
    mock_orderitem=None,
):
    """Wire up the minimum mocks needed for OwnerDashboardView to return 200."""
    mock_schema.return_value.__enter__ = MagicMock(return_value=None)
    mock_schema.return_value.__exit__ = MagicMock(return_value=False)

    mock_cat.count.return_value = 3
    mock_dish.count.return_value = 8
    mock_analytics.filter.return_value = _analytics_qs_mock()
    mock_order.filter.return_value = _order_qs_mock()
    if mock_orderitem is not None:
        mock_orderitem.filter.return_value = _orderitem_qs_mock()

    plan_obj = MagicMock()
    plan_obj.code = "basic"
    plan_obj.name = "Basic"
    tenant_obj = MagicMock()
    tenant_obj.plan = plan_obj
    mock_tenant.select_related.return_value.get.return_value = tenant_obj

    mock_plan.all.return_value = []
    mock_upgrade_req.filter.return_value.exists.return_value = False
    mock_upgrade_req.select_related.return_value.filter.return_value.order_by.return_value = []

    mock_ts.return_value = MagicMock(data=[])


class OwnerDashboardViewResponseTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDashboardView.as_view()

    def _get(self, params=None):
        user = _owner()
        req = self.factory.get("/api/owner/dashboard/", params or {})
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = _tenant()
        return req

    @patch("sales.views.OrderItem.objects")
    @patch("sales.views.TierUpgradeRequestSerializer")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    @patch("sales.views.AnalyticsEvent.objects")
    @patch("sales.views.Order.objects")
    @patch("sales.views.Dish.objects")
    @patch("sales.views.Category.objects")
    @patch("sales.views.schema_context")
    def test_response_includes_required_keys(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem,
    ):
        """200 response must contain analytics_summary, upgrade_meta, upgrade_targets, and revenue_summary."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_orderitem,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("analytics_summary", "upgrade_meta", "upgrade_targets", "upgrade_requests", "revenue_summary"):
            self.assertIn(key, resp.data, f"Missing top-level key: {key}")
        self.assertIn("interaction_rate_pct", resp.data["analytics_summary"])

    @patch("sales.views.OrderItem.objects")
    @patch("sales.views.TierUpgradeRequestSerializer")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    @patch("sales.views.AnalyticsEvent.objects")
    @patch("sales.views.Order.objects")
    @patch("sales.views.Dish.objects")
    @patch("sales.views.Category.objects")
    @patch("sales.views.schema_context")
    def test_days_param_clamped_to_90(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem,
    ):
        """?days=999 must be clamped to 90 in the response."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_orderitem,
        )
        resp = self.view(self._get({"days": 999}))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["analytics_summary"]["days"], 90)

    @patch("sales.views.OrderItem.objects")
    @patch("sales.views.TierUpgradeRequestSerializer")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    @patch("sales.views.AnalyticsEvent.objects")
    @patch("sales.views.Order.objects")
    @patch("sales.views.Dish.objects")
    @patch("sales.views.Category.objects")
    @patch("sales.views.schema_context")
    def test_days_param_defaults_to_30(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem,
    ):
        """Omitting ?days defaults to 30."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_orderitem,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["analytics_summary"]["days"], 30)

    @patch("sales.views.OrderItem.objects")
    @patch("sales.views.TierUpgradeRequestSerializer")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    @patch("sales.views.AnalyticsEvent.objects")
    @patch("sales.views.Order.objects")
    @patch("sales.views.Dish.objects")
    @patch("sales.views.Category.objects")
    @patch("sales.views.schema_context")
    def test_revenue_summary_shape(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem,
    ):
        """revenue_summary must contain total_revenue, order_count, avg_order_value, daily list, peak_hours, and popular_dishes."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_orderitem,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rs = resp.data["revenue_summary"]
        for key in ("total_revenue", "order_count", "avg_order_value", "daily", "days", "peak_hours", "popular_dishes"):
            self.assertIn(key, rs, f"Missing revenue_summary key: {key}")
        self.assertEqual(rs["total_revenue"], 0.0)
        self.assertEqual(rs["order_count"], 0)
        self.assertIsInstance(rs["daily"], list)
        self.assertIsInstance(rs["popular_dishes"], list)
        self.assertIn("by_hour", rs["peak_hours"])
        self.assertIn("by_weekday", rs["peak_hours"])
        self.assertEqual(len(rs["peak_hours"]["by_hour"]), 24)
        self.assertEqual(len(rs["peak_hours"]["by_weekday"]), 7)

    @patch("sales.views.OrderItem.objects")
    @patch("sales.views.TierUpgradeRequestSerializer")
    @patch("sales.views.TierUpgradeRequest.objects")
    @patch("sales.views.Plan.objects")
    @patch("sales.views.Tenant.objects")
    @patch("sales.views.AnalyticsEvent.objects")
    @patch("sales.views.Order.objects")
    @patch("sales.views.Dish.objects")
    @patch("sales.views.Category.objects")
    @patch("sales.views.schema_context")
    def test_revenue_avg_zero_when_no_orders(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem,
    ):
        """avg_order_value must be 0.0 when there are no orders (no division-by-zero)."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_orderitem,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["revenue_summary"]["avg_order_value"], 0.0)
