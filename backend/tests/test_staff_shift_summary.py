"""
Tests for StaffShiftSummaryView — GET /api/staff/shift-summary/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
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

    @patch("menu.views.Order.objects")
    def test_no_orders_returns_zeroed_summary(self, mock_order_objs):
        only_mock = MagicMock()
        only_mock.__iter__ = lambda s: iter([])
        only_mock.first.return_value = None

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.aggregate.return_value = {"total_count": 0, "total_revenue": None}
        qs.only.return_value = only_mock
        mock_order_objs.filter.return_value = qs

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders_handled"], 0)
        self.assertEqual(resp.data["total_revenue"], "0.00")
        self.assertIsNone(resp.data["average_prep_time_minutes"])
        self.assertEqual(resp.data["currency"], "")
        self.assertIn("since", resp.data)
        self.assertIn("period_hours", resp.data)

    @patch("menu.views.Order.objects")
    def test_response_includes_all_required_fields(self, mock_order_objs):
        first_order = MagicMock()
        first_order.currency = "MAD"
        only_mock = MagicMock()
        only_mock.__iter__ = lambda s: iter([])
        only_mock.first.return_value = first_order

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.aggregate.return_value = {"total_count": 5, "total_revenue": Decimal("150.00")}
        qs.only.return_value = only_mock
        mock_order_objs.filter.return_value = qs

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("orders_handled", "total_revenue", "currency",
                      "average_prep_time_minutes", "since", "period_hours"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    @patch("menu.views.Order.objects")
    def test_orders_handled_and_revenue_correct(self, mock_order_objs):
        first_order = MagicMock()
        first_order.currency = "EUR"
        only_mock = MagicMock()
        only_mock.__iter__ = lambda s: iter([])
        only_mock.first.return_value = first_order

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.aggregate.return_value = {"total_count": 12, "total_revenue": Decimal("480.00")}
        qs.only.return_value = only_mock
        mock_order_objs.filter.return_value = qs

        req = self._get()
        resp = self.view(req)

        self.assertEqual(resp.data["orders_handled"], 12)
        self.assertEqual(resp.data["total_revenue"], "480.00")
        self.assertEqual(resp.data["currency"], "EUR")

    # ── Average prep time ─────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_average_prep_time_computed(self, mock_order_objs):
        """Two orders with known durations → correct average in minutes."""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        o1 = MagicMock()
        o1.created_at = now - timedelta(minutes=20)
        o1.status_updated_at = now - timedelta(minutes=10)   # 10 min prep
        o2 = MagicMock()
        o2.created_at = now - timedelta(minutes=30)
        o2.status_updated_at = now - timedelta(minutes=10)   # 20 min prep

        first_order = MagicMock()
        first_order.currency = "MAD"
        # only() is called twice: once to iterate prep times, once for currency first()
        # We need a mock that supports both iteration and .first()
        call_count = {"n": 0}
        only_mock = MagicMock()
        only_mock.first.return_value = first_order
        # First call → yield prep-time orders; second call → currency lookup
        def _only_iter(s):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return iter([o1, o2])
            return iter([])
        only_mock.__iter__ = _only_iter

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.aggregate.return_value = {"total_count": 2, "total_revenue": Decimal("60.00")}
        qs.only.return_value = only_mock
        mock_order_objs.filter.return_value = qs

        req = self._get()
        resp = self.view(req)

        self.assertIsNotNone(resp.data["average_prep_time_minutes"])
        self.assertAlmostEqual(resp.data["average_prep_time_minutes"], 15.0, places=0)

    # ── `since` parameter ─────────────────────────────────────────────────────

    def _make_empty_qs(self):
        """Minimal queryset mock that satisfies the view's only()/aggregate()/first() calls."""
        only_mock = MagicMock()
        only_mock.__iter__ = lambda s: iter([])
        only_mock.first.return_value = None

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.aggregate.return_value = {"total_count": 0, "total_revenue": None}
        qs.only.return_value = only_mock
        return qs

    @patch("menu.views.Order.objects")
    def test_valid_since_param_is_used(self, mock_order_objs):
        """When a valid `since` ISO timestamp is supplied, it sets the window start."""
        mock_order_objs.filter.return_value = self._make_empty_qs()

        req = self._get(params={"since": "2026-05-27T06:00:00+00:00"})
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("2026-05-27", resp.data["since"])

    @patch("menu.views.Order.objects")
    def test_invalid_since_param_falls_back_to_default(self, mock_order_objs):
        """An unparseable `since` value silently falls back to the 8-hour default."""
        mock_order_objs.filter.return_value = self._make_empty_qs()

        req = self._get(params={"since": "not-a-date"})
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["period_hours"], 8.0, delta=0.1)
