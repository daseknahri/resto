"""
Tests for owner export/report views:
  - OwnerOrderExportView         GET /api/owner/orders/export/
  - OwnerCommissionStatementView GET /api/owner/commission-statement/
  - OwnerDataExportView          GET /api/owner/data-export/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerOrderExportView, OwnerCommissionStatementView, OwnerDataExportView
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


def _tenant(tenant_id=1, slug="myrestaurant"):
    return SimpleNamespace(id=tenant_id, slug=slug, schema_name="tenant1")


# ── OwnerOrderExportView ──────────────────────────────────────────────────────

class OwnerOrderExportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderExportView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/orders/export/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_status_filter_returns_400(self):
        resp = self._get(params={"status": "invalid_status_xyz"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_from_date_returns_400(self):
        resp = self._get(params={"from": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_to_date_returns_400(self):
        resp = self._get(params={"to": "13/99/2026"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_from_after_to_returns_400(self):
        resp = self._get(params={"from": "2026-12-01", "to": "2026-01-01"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_csv_response(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.prefetch_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: []
            mock_order.Status = MagicMock()
            mock_order.Status.__iter__ = lambda s: iter([])  # empty status set
            resp = self._get()

        # CSV response returns HttpResponse (not DRF Response), won't have .data
        # Check content type
        self.assertIn("csv", resp.get("Content-Type", "").lower())

    def test_returns_csv_with_header_row(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.prefetch_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: []
            mock_order.Status = MagicMock()
            mock_order.Status.__iter__ = lambda s: iter([])
            resp = self._get()

        content = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        self.assertIn(b"order_number", content)

    def test_content_disposition_set(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.prefetch_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: []
            mock_order.Status = MagicMock()
            mock_order.Status.__iter__ = lambda s: iter([])
            resp = self._get()

        self.assertIn("attachment", resp.get("Content-Disposition", ""))


# ── OwnerCommissionStatementView ──────────────────────────────────────────────

class OwnerCommissionStatementViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCommissionStatementView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/commission-statement/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_year_returns_400(self):
        resp = self._get(params={"year": "not-a-year", "month": "1"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_month_returns_400(self):
        resp = self._get(params={"year": "2026", "month": "13"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_month_zero_returns_400(self):
        resp = self._get(params={"year": "2026", "month": "0"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_json_structure(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.filter.return_value.order_by.return_value = qs
            qs.aggregate.return_value = {
                "order_count": 5,
                "total_revenue": "500.00",
                "total_commission": "50.00",
            }
            qs.__iter__ = lambda s: iter([])
            mock_order.Source = MagicMock()
            mock_order.Source.MARKETPLACE = "marketplace"
            resp = self._get(params={"year": "2026", "month": "5"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("year", "month", "month_name", "summary", "orders"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        for field in ("order_count", "total_revenue", "total_commission", "net_payout"):
            self.assertIn(field, resp.data["summary"], f"Missing summary field: {field}")

    def test_defaults_to_current_month(self):
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            mock_order.objects.filter.return_value.order_by.return_value = qs
            qs.aggregate.return_value = {
                "order_count": 0,
                "total_revenue": None,
                "total_commission": None,
            }
            qs.__iter__ = lambda s: iter([])
            mock_order.Source = MagicMock()
            mock_order.Source.MARKETPLACE = "marketplace"
            resp = self._get()  # no year/month params

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("year", resp.data)
        self.assertIn("month", resp.data)

    def test_net_payout_is_revenue_minus_commission(self):
        """net_payout = total_revenue - total_commission. A5-followup: totals are now
        derived from the actual (non-cancelled) order rows, not a DB aggregate, so we
        feed real rows whose revenue/commission sum to 1000/100 → net_payout 900."""
        from datetime import datetime, timezone as _utc
        from decimal import Decimal as _D
        from types import SimpleNamespace

        rows = [
            SimpleNamespace(
                order_number=f"ORD-{i}",
                created_at=datetime(2026, 6, 10, 12, 0, tzinfo=_utc.utc),
                customer_name="Diner",
                total=_D("100.00"),
                commission_amount=_D("10.00"),
                commission_rate_applied=_D("0.10"),
                currency="MAD",
                status="completed",
            )
            for i in range(10)
        ]
        with patch("menu.views.Order") as mock_order:
            qs = MagicMock()
            qs.exclude.return_value = qs
            qs.order_by.return_value = qs
            mock_order.objects.filter.return_value = qs
            qs.__iter__ = lambda s: iter(rows)
            mock_order.Source = MagicMock()
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status = MagicMock()
            mock_order.Status.CANCELLED = "cancelled"
            resp = self._get(params={"year": "2026", "month": "6"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["summary"]["total_revenue"], 1000.0)
        self.assertAlmostEqual(resp.data["summary"]["total_commission"], 100.0)
        self.assertAlmostEqual(resp.data["summary"]["net_payout"], 900.0)


# ── OwnerDataExportView ───────────────────────────────────────────────────────

class OwnerDataExportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDataExportView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/data-export/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_json_download(self):
        """Returns a JSON file attachment response."""
        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.get.side_effect = Exception("no profile")
            with patch("menu.views.SuperCategory") as mock_sc:
                mock_sc.objects.values.return_value = []
                with patch("menu.views.Category") as mock_cat:
                    mock_cat.objects.select_related.return_value.values.return_value = []
                    with patch("menu.views.Dish") as mock_dish:
                        mock_dish.objects.select_related.return_value.values.return_value = []
                        with patch("menu.views.OptionGroup") as mock_og:
                            mock_og.objects.prefetch_related.return_value.values.return_value = []
                            with patch("menu.views.Order") as mock_order:
                                mock_order.objects.prefetch_related.return_value.order_by.return_value = []
                                with patch("menu.views.Rating") as mock_rating:
                                    mock_rating.objects.values.return_value = []
                                    with patch("menu.views.TableLink") as mock_tl:
                                        mock_tl.objects.values.return_value = []
                                        with patch("menu.models.ClosureDate") as mock_cd:
                                            mock_cd.objects.order_by.return_value = []
                                            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content_type = resp.get("Content-Type", "")
        self.assertIn("json", content_type)
        self.assertIn("attachment", resp.get("Content-Disposition", ""))
