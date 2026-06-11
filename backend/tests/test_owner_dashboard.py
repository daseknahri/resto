"""
Tests for OwnerDashboardView
GET /api/owner/dashboard/

The full happy-path requires schema_context, analytics aggregation, Plan lookups,
and TierUpgradeRequest queries — all of which are better covered by integration
tests. These unit tests cover the auth/permission guards and response shape
using aggressive mocking of the DB layer.
"""
from decimal import Decimal
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
    """Minimal Order queryset mock for the revenue aggregation chain.

    qs.aggregate() is called multiple times by the view with different key sets:
      1. Revenue totals: total_revenue, order_count, wallet_revenue
      2. Loyalty/promo:  promo_discount_total, loyalty_discount_total, ...
      3. Statement:      gross, promo_discounts, loyalty_discounts, tips, commission
      4. Prev-period:    total_revenue, order_count
      5. Marketplace:    mkt_count, mkt_revenue, mkt_commission
    Returning a superset dict covers all calls regardless of order.
    """
    daily_result = MagicMock()
    daily_result.__iter__ = lambda s: iter([])

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.count.return_value = 0
    qs.aggregate.return_value = {
        # Revenue totals
        "total_revenue": None, "order_count": 0, "wallet_revenue": None,
        # Marketplace
        "mkt_count": 0, "mkt_revenue": None, "mkt_commission": None,
        # Loyalty & promotion
        "promo_discount_total": None, "loyalty_discount_total": None,
        "points_earned_total": None, "points_redeemed_total": None,
        # Statement keys (revenue-summary extension)
        "gross": None, "promo_discounts": None, "loyalty_discounts": None,
        "tips": None, "commission": None,
    }
    # daily / hourly / weekday chain: annotate().values().annotate().order_by()
    qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = daily_result
    # currency lookup: values_list(...).exclude(...).order_by(...).first()
    qs.values_list.return_value.exclude.return_value.order_by.return_value.first.return_value = "USD"
    return qs


def _orderitem_qs_mock():
    """Minimal OrderItem queryset mock for the popular_dishes aggregation chain."""
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    # .values().annotate().order_by()[:10] must be iterable → return empty list
    qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
    return qs


def _lead_qs_mock():
    """Lead queryset mock for the today's-reservations count queries.

    The view does:
        base = Lead.objects.filter(...)
        base.count()                       → today_reservations
        base.filter(status=NEW).count()    → today_new_reservations
    """
    qs = MagicMock()
    qs.count.return_value = 0
    qs.filter.return_value.count.return_value = 0
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

_SPLIT_ZERO = {"wallet": Decimal("0.00"), "cash": Decimal("0.00")}


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
    mock_lead,
    mock_orderitem=None,
    mock_split=None,
):
    """Wire up the minimum mocks needed for OwnerDashboardView to return 200.

    split_revenue_for_orders is patched to avoid real OrderPayment ORM queries.
    """
    mock_schema.return_value.__enter__ = MagicMock(return_value=None)
    mock_schema.return_value.__exit__ = MagicMock(return_value=False)

    mock_cat.count.return_value = 3
    mock_dish.count.return_value = 8
    mock_analytics.filter.return_value = _analytics_qs_mock()
    mock_order.filter.return_value = _order_qs_mock()
    mock_lead.filter.return_value = _lead_qs_mock()
    if mock_orderitem is not None:
        mock_orderitem.filter.return_value = _orderitem_qs_mock()
    if mock_split is not None:
        mock_split.return_value = _SPLIT_ZERO

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

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("sales.views.Lead.objects")
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
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_split,
    ):
        """200 response must contain analytics_summary, upgrade_meta, upgrade_targets, and revenue_summary."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
            mock_split=mock_split,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in (
            "analytics_summary", "upgrade_meta", "upgrade_targets",
            "upgrade_requests", "revenue_summary",
            "today_reservations", "today_new_reservations",
        ):
            self.assertIn(key, resp.data, f"Missing top-level key: {key}")
        self.assertIn("interaction_rate_pct", resp.data["analytics_summary"])
        # Period-over-period analytics comparison fields
        self.assertIn("prev_counts", resp.data["analytics_summary"])
        self.assertIn("prev_interaction_rate_pct", resp.data["analytics_summary"])

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("sales.views.Lead.objects")
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
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_split,
    ):
        """?days=999 must be clamped to 90 in the response."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
            mock_split=mock_split,
        )
        resp = self.view(self._get({"days": 999}))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["analytics_summary"]["days"], 90)

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("sales.views.Lead.objects")
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
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_split,
    ):
        """Omitting ?days defaults to 30."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
            mock_split=mock_split,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["analytics_summary"]["days"], 30)

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("sales.views.Lead.objects")
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
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_split,
    ):
        """revenue_summary must contain total_revenue, order_count, avg_order_value, daily list, peak_hours, popular_dishes, prev_period, and fulfillment_breakdown."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
            mock_split=mock_split,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rs = resp.data["revenue_summary"]
        for key in (
            "total_revenue", "order_count", "avg_order_value", "daily", "days",
            "peak_hours", "popular_dishes", "prev_period", "fulfillment_breakdown",
            "currency", "loyalty_promo", "wallet_revenue", "cash_revenue",
            "payment_split", "top_items_by_revenue", "statement",
        ):
            self.assertIn(key, rs, f"Missing revenue_summary key: {key}")
        for key in ("promo_discount_total", "promo_order_count", "loyalty_discount_total",
                    "loyalty_order_count", "points_earned_total", "points_redeemed_total"):
            self.assertIn(key, rs["loyalty_promo"], f"Missing loyalty_promo key: {key}")
        self.assertEqual(rs["total_revenue"], 0.0)
        self.assertEqual(rs["order_count"], 0)
        self.assertIsInstance(rs["daily"], list)
        self.assertIsInstance(rs["popular_dishes"], list)
        self.assertIn("by_hour", rs["peak_hours"])
        self.assertIn("by_weekday", rs["peak_hours"])
        self.assertEqual(len(rs["peak_hours"]["by_hour"]), 24)
        self.assertEqual(len(rs["peak_hours"]["by_weekday"]), 7)
        # Previous-period comparison keys
        for key in ("total_revenue", "order_count", "avg_order_value",
                    "revenue_change_pct", "order_change_pct", "avg_change_pct"):
            self.assertIn(key, rs["prev_period"], f"Missing prev_period key: {key}")
        # No previous-period baseline (zero revenue) → change pct is None
        self.assertIsNone(rs["prev_period"]["revenue_change_pct"])
        # New statement keys
        for key in ("gross", "promo_discounts", "loyalty_discounts", "tips", "commission", "net"):
            self.assertIn(key, rs["statement"], f"Missing statement key: {key}")

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("sales.views.Lead.objects")
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
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_split,
    ):
        """avg_order_value must be 0.0 when there are no orders (no division-by-zero)."""
        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
            mock_split=mock_split,
        )
        resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["revenue_summary"]["avg_order_value"], 0.0)
