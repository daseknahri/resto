"""
Tests for StaffShiftSummaryView — GET /api/staff/shift-summary/

All tests are unit-level (SimpleTestCase + mocks — no real DB).

Contract G changes reflected here:
- avg prep time is now a single-query Avg(ExpressionWrapper(...)) stored in
  agg["avg_prep_duration"] (a timedelta or None), not a Python loop.
- currency is now from qs.values_list("currency", flat=True).exclude(...).order_by().first()
  (no more qs.only("currency").first()).
- split_revenue_for_orders is called when show_revenue=True, adding
  collected_cash / collected_wallet to the response.
"""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import StaffShiftSummaryView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    # effective_perm_view_revenue → True (staff can view revenue in these tests)
    u.effective_perm_view_revenue.return_value = True
    return u


def _outsider(tenant_id=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_qs(total_count=0, total_revenue=None, avg_prep_duration=None, currency=None):
    """Build a queryset mock compatible with the Contract G view implementation.

    The view calls:
      qs.aggregate(total_count=..., total_revenue=..., avg_prep_duration=...)
      qs.values_list("currency", flat=True).exclude(currency="").order_by().first()
      split_revenue_for_orders(qs)  — patched separately
    """
    qs = MagicMock()
    qs.filter.return_value = qs

    # Single aggregate (Contract G — no Python loop)
    qs.aggregate.return_value = {
        "total_count": total_count,
        "total_revenue": total_revenue,
        "avg_prep_duration": avg_prep_duration,
    }

    # Currency chain: qs.values_list(..., flat=True).exclude(...).order_by().first()
    vl_mock = MagicMock()
    vl_mock.exclude.return_value.order_by.return_value.first.return_value = currency
    qs.values_list.return_value = vl_mock

    return qs


# ── Tests ─────────────────────────────────────────────────────────────────────

class StaffShiftSummaryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffShiftSummaryView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/staff/shift-summary/", params or {})
        req.user = user or _staff()
        req.tenant = tenant or _tenant()
        return req

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_outsider_returns_403(self):
        req = self._get(user=_outsider())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Response shape ────────────────────────────────────────────────────────

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_no_orders_returns_zeroed_summary(self, mock_order_objs, mock_split):
        mock_split.return_value = {"cash": Decimal("0.00"), "wallet": Decimal("0.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=0, total_revenue=None, avg_prep_duration=None, currency=None
        )

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders_handled"], 0)
        self.assertEqual(resp.data["total_revenue"], "0.00")
        self.assertIsNone(resp.data["average_prep_time_minutes"])
        self.assertEqual(resp.data["currency"], "")
        self.assertIn("since", resp.data)
        self.assertIn("period_hours", resp.data)

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_response_includes_all_required_fields(self, mock_order_objs, mock_split):
        mock_split.return_value = {"cash": Decimal("50.00"), "wallet": Decimal("100.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=5, total_revenue=Decimal("150.00"),
            avg_prep_duration=None, currency="MAD"
        )

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in (
            "orders_handled", "total_revenue", "currency",
            "average_prep_time_minutes", "since", "period_hours",
            "collected_cash", "collected_wallet",
        ):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_orders_handled_and_revenue_correct(self, mock_order_objs, mock_split):
        mock_split.return_value = {"cash": Decimal("180.00"), "wallet": Decimal("300.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=12, total_revenue=Decimal("480.00"),
            avg_prep_duration=None, currency="EUR"
        )

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.data["orders_handled"], 12)
        self.assertEqual(resp.data["total_revenue"], "480.00")
        self.assertEqual(resp.data["currency"], "EUR")

    # ── Average prep time ─────────────────────────────────────────────────────

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_average_prep_time_computed(self, mock_order_objs, mock_split):
        """Single-query Avg returns a timedelta → view converts to minutes.

        Contract G: avg_prep_duration is the result of
        Avg(ExpressionWrapper(F('status_updated_at') - F('created_at'), ...))
        which returns a timedelta (or None). The view calls .total_seconds() / 60.

        Two orders: 10-min + 20-min → avg = 15.0 min.
        """
        mock_split.return_value = {"cash": Decimal("30.00"), "wallet": Decimal("30.00")}
        # timedelta equivalent of 15 minutes average
        avg_duration = timedelta(minutes=15)
        mock_order_objs.filter.return_value = _make_qs(
            total_count=2, total_revenue=Decimal("60.00"),
            avg_prep_duration=avg_duration, currency="MAD"
        )

        req = self._get()
        resp = self.view(req)

        self.assertIsNotNone(resp.data["average_prep_time_minutes"])
        self.assertAlmostEqual(resp.data["average_prep_time_minutes"], 15.0, places=0)

    # ── Contract G: cash/wallet split ─────────────────────────────────────────

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_collected_cash_and_wallet_present(self, mock_order_objs, mock_split):
        """collected_cash / collected_wallet must appear and match split result."""
        mock_split.return_value = {"cash": Decimal("70.00"), "wallet": Decimal("30.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=3, total_revenue=Decimal("100.00"),
            avg_prep_duration=None, currency="MAD"
        )

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["collected_cash"], "70.00")
        self.assertEqual(resp.data["collected_wallet"], "30.00")

    # ── `since` parameter ─────────────────────────────────────────────────────

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_valid_since_param_is_used(self, mock_order_objs, mock_split):
        """When a valid `since` ISO timestamp is supplied, it sets the window start."""
        mock_split.return_value = {"cash": Decimal("0.00"), "wallet": Decimal("0.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=0, total_revenue=None, avg_prep_duration=None, currency=None
        )

        req = self._get(params={"since": "2026-05-27T06:00:00+00:00"})
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("2026-05-27", resp.data["since"])

    @patch("menu.revenue.split_revenue_for_orders")
    @patch("menu.views.Order.objects")
    def test_invalid_since_param_falls_back_to_default(self, mock_order_objs, mock_split):
        """An unparseable `since` value silently falls back to the 8-hour default."""
        mock_split.return_value = {"cash": Decimal("0.00"), "wallet": Decimal("0.00")}
        mock_order_objs.filter.return_value = _make_qs(
            total_count=0, total_revenue=None, avg_prep_duration=None, currency=None
        )

        req = self._get(params={"since": "not-a-date"})
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["period_hours"], 8.0, delta=0.1)
