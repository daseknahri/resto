"""
B2 backend tests — OwnerRepeatAnalyticsView GET /api/owner/repeat-analytics/

Contracts:
  - 403 for non-owners and unauthenticated
  - 200 with all required keys in response
  - repeat_rate = 0 when no paid orders
  - repeat_rate computed correctly when customers have multiple orders
  - new vs. returning revenue split is correct
  - days param clamped to [7, 90]
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import OwnerRepeatAnalyticsView
from accounts.models import User


# ── helpers ────────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_tenant_owner = True
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.id = 1
    u.pk = 1
    return u


def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_tenant_owner = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.id = 2
    u.pk = 2
    return u


def _tenant(tenant_id=1):
    t = MagicMock()
    t.id = tenant_id
    return t


def _make_agg_mock(revenue=None, customers=0):
    return {"revenue": revenue, "customers": customers}


class _FakeQS:
    """Minimal queryset double for aggregation + chaining."""

    def __init__(self, count_val=0, agg_val=None, items=None):
        self._count = count_val
        self._agg = agg_val or {}
        self._items = items or []

    def filter(self, **kwargs):
        return self

    def exclude(self, **kwargs):
        return self

    def values(self, *fields):
        return self

    def distinct(self):
        return self

    def annotate(self, **kwargs):
        return self

    def count(self):
        return self._count

    def aggregate(self, **kwargs):
        return self._agg

    def __iter__(self):
        return iter(self._items)


class RepeatAnalyticsAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRepeatAnalyticsView.as_view()

    def _get(self, user=None, tenant_id=1, days=30):
        req = self.factory.get("/api/owner/repeat-analytics/", {"days": days})
        if user:
            force_authenticate(req, user=user)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req)

    def test_unauthenticated_is_403(self):
        resp = self._get(user=None)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_staff_is_403(self, _mock):
        resp = self._get(user=_staff())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class RepeatAnalyticsResponseShapeTests(SimpleTestCase):
    """Response must include all required keys."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRepeatAnalyticsView.as_view()

    def _get_with_mocks(self, days=30, order_mock=None):
        req = self.factory.get("/api/owner/repeat-analytics/", {"days": days})
        force_authenticate(req, user=_owner())
        req.tenant = _tenant()
        with patch("menu.views._is_tenant_owner", return_value=True), \
             patch("menu.views.Order.objects", order_mock or _empty_order_mock()):
            return self.view(req)

    def test_response_has_all_keys(self):
        resp = self._get_with_mocks()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("days", "unique_paying", "repeat_customers", "repeat_rate",
                    "total_revenue", "new_customers", "returning_customers",
                    "new_revenue", "returning_revenue"):
            self.assertIn(key, resp.data, f"Missing key: {key}")

    def test_zero_orders_gives_zero_repeat_rate(self):
        resp = self._get_with_mocks()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["repeat_rate"], 0.0)
        self.assertEqual(resp.data["unique_paying"], 0)
        self.assertEqual(resp.data["repeat_customers"], 0)

    def test_days_param_returned(self):
        resp = self._get_with_mocks(days=60)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["days"], 60)

    def test_days_clamped_to_min_7(self):
        resp = self._get_with_mocks(days=1)
        self.assertEqual(resp.data["days"], 7)

    def test_days_clamped_to_max_90(self):
        resp = self._get_with_mocks(days=365)
        self.assertEqual(resp.data["days"], 90)


class RepeatAnalyticsComputationTests(SimpleTestCase):
    """Verify repeat rate and new/returning split arithmetic."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRepeatAnalyticsView.as_view()

    def _get(self, order_mock):
        req = self.factory.get("/api/owner/repeat-analytics/", {"days": 30})
        force_authenticate(req, user=_owner())
        req.tenant = _tenant()
        with patch("menu.views._is_tenant_owner", return_value=True), \
             patch("menu.views.Order.objects", order_mock):
            return self.view(req)

    def test_repeat_rate_50_pct(self):
        """2 out of 4 unique paying customers ordered 2+ times → 50%."""
        mock_objs = _repeat_order_mock(
            unique_paying=4,
            repeat_customers=2,
            returning_revenue=Decimal("200.00"),
            returning_customers=2,
            new_revenue=Decimal("100.00"),
            new_customers=2,
            total_revenue=Decimal("300.00"),
        )
        resp = self._get(mock_objs)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["repeat_rate"], 50.0)
        self.assertEqual(resp.data["unique_paying"], 4)
        self.assertEqual(resp.data["repeat_customers"], 2)

    def test_revenue_split_values(self):
        """new + returning revenue sums match aggregates."""
        mock_objs = _repeat_order_mock(
            unique_paying=3,
            repeat_customers=1,
            returning_revenue=Decimal("150.00"),
            returning_customers=1,
            new_revenue=Decimal("80.50"),
            new_customers=2,
            total_revenue=Decimal("230.50"),
        )
        resp = self._get(mock_objs)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["new_revenue"], "80.50")
        self.assertEqual(resp.data["returning_revenue"], "150.00")
        self.assertEqual(resp.data["total_revenue"], "230.50")
        self.assertEqual(resp.data["new_customers"], 2)
        self.assertEqual(resp.data["returning_customers"], 1)


# ── Mock builders ──────────────────────────────────────────────────────────────

def _empty_order_mock():
    """Order.objects mock that returns zeroes everywhere."""
    qs = _FakeQS(
        count_val=0,
        agg_val={"revenue": None, "customers": 0, "total": None},
    )
    m = MagicMock()
    m.filter.return_value = qs
    m.PaymentStatus.PAID = "paid"
    return m


def _repeat_order_mock(
    unique_paying,
    repeat_customers,
    returning_revenue,
    returning_customers,
    new_revenue,
    new_customers,
    total_revenue,
):
    """
    Build an Order.objects mock that returns controlled aggregate values.

    Call sequence in the view:
      1. Order.objects.filter(payment_status=PAID, paid_at__gte=..., ..., customer__isnull=False)
         → in_window_qs
      2. Order.objects.filter(payment_status=PAID, paid_at__lt=..., customer__isnull=False)
         .values("customer_id").distinct()
         → prior_cids_qs
      3. in_window_qs.filter(customer_id__in=prior_cids_qs).aggregate(revenue=, customers=)
         → returning_agg
      4. in_window_qs.exclude(customer_id__in=prior_cids_qs).aggregate(revenue=, customers=)
         → new_agg
      5. in_window_qs.aggregate(revenue=)
         → total_agg
      6. in_window_qs.values("customer_id").distinct().count()
         → unique_paying
      7. in_window_qs.values("customer_id").annotate(_n=Count("id")).filter(_n__gte=2).count()
         → repeat_customers
    """

    class _InWindowQS:
        """Chain proxy — tracks annotate() calls so count() can return the right value."""

        def __init__(self, annotated=False):
            self._annotated = annotated

        def filter(self, **kw):
            if "customer_id__in" in kw:
                return _ReturningQS()
            return _InWindowQS(annotated=self._annotated)

        def exclude(self, **kw):
            if "customer_id__in" in kw:
                return _NewQS()
            return _InWindowQS(annotated=self._annotated)

        def values(self, *_):
            return _InWindowQS(annotated=self._annotated)

        def distinct(self):
            return _InWindowQS(annotated=self._annotated)

        def annotate(self, **_):
            return _InWindowQS(annotated=True)

        def count(self):
            return repeat_customers if self._annotated else unique_paying

        def aggregate(self, **_):
            return {"revenue": total_revenue, "customers": 0}

    class _ReturningQS:
        def values(self, *_): return self
        def distinct(self): return self
        def annotate(self, **_): return self
        def filter(self, **_): return self
        def exclude(self, **_): return self
        def count(self): return repeat_customers

        def aggregate(self, **_):
            return {"revenue": returning_revenue, "customers": returning_customers}

    class _NewQS:
        def values(self, *_): return self
        def distinct(self): return self
        def annotate(self, **_): return self
        def filter(self, **_): return self
        def count(self): return 0

        def aggregate(self, **_):
            return {"revenue": new_revenue, "customers": new_customers}

    class _PriorCidsQS:
        def values(self, *_): return self
        def distinct(self): return self

    m = MagicMock()
    m.PaymentStatus.PAID = "paid"

    call_count = [0]

    def _filter_side_effect(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: in_window
            return _InWindowQS()
        # Second call: prior_cids
        return _PriorCidsQS()

    m.filter.side_effect = _filter_side_effect
    return m
