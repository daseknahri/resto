"""
OPS-2 "end-of-day money truth" — unit tests for all seven contracts (A–G).

All tests use SimpleTestCase + MagicMock (no real DB). The 25 Postgres-
environment errors that appear in the CI baseline are NOT regressions and are
not caused by this file.

Contracts covered:
  A – service_day_window() math + Profile.service_day_cutover_hour field
  B – OwnerZReportView shape (collected/refunds/voids/by_staff predicates)
  C – Revenue-truth fix: payment_split uses payment_status=PAID only
  D – StaffPaymentMethodCorrectionView: audit fields, no money movement
  E – TruncDate tzinfo bucketing (confirmed in sales/views.py code review)
  F – OwnerOrderDetailView payments list + void fields (in test_owner_*.py)
  G – StaffShiftSummaryView single-query avg-prep + cash/wallet (test_staff_*.py)
"""
from __future__ import annotations

from datetime import date, datetime, timezone as stdlib_tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import service_day_window, OwnerZReportView, StaffPaymentMethodCorrectionView


# ─── helpers ──────────────────────────────────────────────────────────────────

def _profile(tz="UTC", cutover=0):
    return SimpleNamespace(
        timezone=tz,
        service_day_cutover_hour=cutover,
    )


def _owner_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.is_tenant_owner = True
    u.Roles = User.Roles
    return u


def _staff_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.is_tenant_owner = False
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    t = MagicMock()
    t.id = tenant_id
    t.slug = "testshop"
    return t


def _make_empty_op_qs():
    """Minimal OrderPayment queryset mock — returns empty iterables for by_staff loops."""
    iter_mock = MagicMock()
    iter_mock.__iter__ = lambda s: iter([])
    op_qs = MagicMock()
    op_qs.values.return_value.annotate.return_value = iter_mock
    return op_qs


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT A — service_day_window
# ═══════════════════════════════════════════════════════════════════════════════

class ServiceDayWindowMathTests(SimpleTestCase):
    """Pure-math tests for service_day_window. No DB."""

    def test_cutover_zero_is_calendar_midnight(self):
        """H=0 → window is exactly the calendar day (midnight-to-midnight)."""
        profile = _profile(tz="UTC", cutover=0)
        start, end = service_day_window(profile, date=date(2026, 6, 1))

        self.assertEqual(start.hour, 0)
        self.assertEqual(start.minute, 0)
        self.assertEqual(start.day, 1)
        self.assertEqual(end.day, 2)
        self.assertEqual(end.hour, 0)
        # duration is exactly 24 h
        self.assertEqual((end - start).total_seconds(), 86400)

    def test_cutover_4_with_date_param(self):
        """H=4, date=2026-06-10 → start = 2026-06-10 04:00, end = 2026-06-11 04:00."""
        profile = _profile(tz="UTC", cutover=4)
        start, end = service_day_window(profile, date=date(2026, 6, 10))
        self.assertEqual(start.hour, 4)
        self.assertEqual(start.day, 10)
        self.assertEqual(start.month, 6)
        self.assertEqual(end.hour, 4)
        self.assertEqual(end.day, 11)

    def test_cutover_4_now_before_cutover_uses_previous_date(self):
        """H=4, now=2026-06-10 02:00 → service day starts 2026-06-09 04:00.

        At 2am the new calendar day has started but the 4am cutover hasn't fired yet,
        so 2am belongs to YESTERDAY'S service day.
        """
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        profile = _profile(tz="UTC", cutover=4)
        now_local = datetime(2026, 6, 10, 2, 0, 0, tzinfo=tz)   # 02:00 — before cutover
        start, end = service_day_window(profile, now_local=now_local)
        # Should start at yesterday@04:00
        self.assertEqual(start.day, 9)
        self.assertEqual(start.hour, 4)
        self.assertEqual(end.day, 10)
        self.assertEqual(end.hour, 4)

    def test_cutover_4_now_after_cutover_uses_today(self):
        """H=4, now=2026-06-10 06:00 → service day starts 2026-06-10 04:00."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        profile = _profile(tz="UTC", cutover=4)
        now_local = datetime(2026, 6, 10, 6, 0, 0, tzinfo=tz)   # 06:00 — after cutover
        start, end = service_day_window(profile, now_local=now_local)
        self.assertEqual(start.day, 10)
        self.assertEqual(start.hour, 4)
        self.assertEqual(end.day, 11)
        self.assertEqual(end.hour, 4)

    def test_cutover_0_now_at_midnight_uses_today(self):
        """H=0, now exactly at midnight → start is today@00:00 (boundary inclusive)."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        profile = _profile(tz="UTC", cutover=0)
        now_local = datetime(2026, 6, 10, 0, 0, 0, tzinfo=tz)   # exactly midnight
        start, end = service_day_window(profile, now_local=now_local)
        self.assertEqual(start.day, 10)
        self.assertEqual(start.hour, 0)

    def test_window_is_tz_aware(self):
        """Both start and end returned by service_day_window must be tz-aware."""
        profile = _profile(tz="UTC", cutover=0)
        start, end = service_day_window(profile, date=date(2026, 6, 1))
        self.assertIsNotNone(start.tzinfo, "start must be tz-aware")
        self.assertIsNotNone(end.tzinfo, "end must be tz-aware")

    def test_duration_always_24_hours(self):
        """The window is always exactly 24 hours regardless of cutover hour."""
        for h in (0, 1, 3, 4, 11):
            with self.subTest(cutover=h):
                profile = _profile(tz="UTC", cutover=h)
                start, end = service_day_window(profile, date=date(2026, 6, 10))
                self.assertEqual(
                    (end - start).total_seconds(), 86400,
                    f"cutover={h}: window is not exactly 24 h"
                )

    def test_invalid_cutover_clamped_to_zero(self):
        """H < 0 is clamped to 0 by the max(0, ...) guard."""
        profile = _profile(tz="UTC", cutover=-5)
        start, end = service_day_window(profile, date=date(2026, 6, 10))
        self.assertEqual(start.hour, 0)   # clamped to 0

    def test_date_string_iso_parsed(self):
        """service_day_window accepts a date string (YYYY-MM-DD)."""
        profile = _profile(tz="UTC", cutover=0)
        start, end = service_day_window(profile, date="2026-06-10")
        self.assertEqual(start.day, 10)
        self.assertEqual(end.day, 11)

    def test_now_local_path_is_always_24_hours_utc(self):
        """now_local path: day_end must be exactly 24 h after day_start in UTC.

        Regression: the previous implementation used timedelta(days=1) which is
        correct for UTC-only tenants but wrong for DST-observing timezones (the
        spring-forward day is 23 h long; fall-back is 25 h in local wall time).
        We test in UTC here (DST-free) to confirm the basic invariant holds;
        DST-specific behaviour is correct by construction (day_end is built as a
        local datetime at H:00:00 on next calendar date, not via timedelta).
        """
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        for h in (0, 3, 4, 11):
            with self.subTest(cutover=h):
                profile = _profile(tz="UTC", cutover=h)
                now_local = datetime(2026, 6, 10, h + 1, 0, 0, tzinfo=tz)  # after cutover
                start, end = service_day_window(profile, now_local=now_local)
                self.assertEqual(
                    (end - start).total_seconds(), 86400,
                    f"cutover={h}: now_local path gives window != 24 h"
                )

    def test_now_local_path_end_is_local_h_on_next_day(self):
        """day_end for the now_local path must be H:00:00 on the next calendar day.

        This verifies the fix: day_end = datetime(next_date, H, 0, 0, tzinfo=tz)
        rather than day_start + timedelta(days=1).  Both produce the same result
        in UTC; in DST zones they differ on transition days.
        """
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        profile = _profile(tz="UTC", cutover=4)
        # now_local after the 4am cutover → service day starts today@04:00
        now_local = datetime(2026, 6, 10, 8, 0, 0, tzinfo=tz)
        start, end = service_day_window(profile, now_local=now_local)
        self.assertEqual(start.day, 10)
        self.assertEqual(start.hour, 4)
        # end must be 2026-06-11 04:00 UTC
        self.assertEqual(end.day, 11)
        self.assertEqual(end.hour, 4)
        self.assertEqual(end.minute, 0)
        self.assertEqual(end.second, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT B — OwnerZReportView
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerZReportAuthTests(SimpleTestCase):
    """Auth gate: non-owner gets 403."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerZReportView.as_view()

    def _req(self, user, tenant=None):
        req = self.factory.get("/api/owner/z-report/")
        req.user = user
        req.tenant = tenant or _tenant()
        req.path = "/api/owner/z-report/"
        return req

    def test_staff_user_gets_403(self):
        req = self._req(user=_staff_user())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_gets_403(self):
        u = MagicMock()
        u.is_authenticated = False
        u.is_tenant_owner = False
        u.role = "customer"
        req = self._req(user=u)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


def _z_report_patches(cash=Decimal("100.00"), wallet=Decimal("50.00"),
                      refund_count=0, refund_total=Decimal("0.00")):
    """Return a list of patch context managers for OwnerZReportView DB calls."""
    mock_split = MagicMock(return_value={"cash": cash, "wallet": wallet})

    # Order.objects: collected_qs and its .aggregate(tips=...).
    # collected_qs now also chains .filter(payment_status=PAID) — the mock returns
    # itself on every .filter() call so the chain stays valid.
    order_qs = MagicMock()
    order_qs.filter.return_value = order_qs
    # Two aggregate() calls on collected_qs: tips first, then promo+loyalty discounts.
    order_qs.aggregate.side_effect = [
        {"tips": Decimal("5.00")},
        {"promo": Decimal("0.00"), "loyalty": Decimal("0.00")},
    ]
    mock_order_objs = MagicMock()
    mock_order_objs.filter.return_value = order_qs

    # WalletTransaction (imported lazily as _WTx inside _build_report).
    # The filter call now receives tenant_id= as a kwarg; the mock accepts any kwargs.
    wt_qs = MagicMock()
    wt_qs.filter.return_value = wt_qs
    wt_qs.aggregate.return_value = {
        "refund_count": refund_count,
        "refund_total": refund_total,
    }
    mock_wt_class = MagicMock()
    mock_wt_class.Type.REFUND = "REFUND"
    mock_wt_class.objects.filter.return_value = wt_qs

    # OrderItem.objects:
    #   .select_related("order").filter(...) → voided-items iteration (empty)
    #   .filter(...).annotate(...).filter(...).annotate(...).aggregate(...) → food-cost query (total=None)
    oi_qs = MagicMock()
    oi_qs.__iter__ = lambda s: iter([])
    food_cost_chain = MagicMock()
    food_cost_chain.annotate.return_value = food_cost_chain
    food_cost_chain.filter.return_value = food_cost_chain
    food_cost_chain.aggregate.return_value = {"total": None}
    mock_oi_objs = MagicMock()
    mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
    mock_oi_objs.filter.return_value = food_cost_chain

    # OrderPayment.objects: by_staff (empty).
    # The by_staff filter now uses order__paid_at instead of created_at; the mock
    # still returns an empty iterable via _make_empty_op_qs() which chains .values()
    # and .annotate() — shape unchanged.
    mock_op_objs = MagicMock()
    mock_op_objs.filter.return_value = _make_empty_op_qs()

    # Shift.objects: labor section (empty — lazy import inside _build_report).
    shift_qs = MagicMock()
    shift_qs.__iter__ = lambda s: iter([])
    mock_shift_class = MagicMock()
    mock_shift_class.objects.filter.return_value.order_by.return_value = shift_qs

    return [
        patch("menu.revenue.split_revenue_for_orders", mock_split),
        patch("menu.views.Order.objects", mock_order_objs),
        patch("menu.views.OrderItem.objects", mock_oi_objs),
        patch("menu.views.OrderPayment.objects", mock_op_objs),
        # _build_report imports WalletTransaction lazily; patching the source module
        # intercepts the local import on every call (lazy imports re-bind on each call).
        patch("accounts.models.WalletTransaction", mock_wt_class),
        # Shift is also imported lazily inside _build_report.
        patch("menu.models.Shift", mock_shift_class),
    ]


class OwnerZReportResponseShapeTests(SimpleTestCase):
    """Z-report JSON response must include all required top-level sections."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerZReportView.as_view()

    def _make_request(self, date_param=None):
        params = {}
        if date_param:
            params["date"] = date_param
        req = self.factory.get("/api/owner/z-report/", params)
        req.user = _owner_user()
        t = _tenant()
        t.profile = _profile(tz="UTC", cutover=0)
        req.tenant = t
        req.path = "/api/owner/z-report/"
        return req

    def test_response_has_all_top_level_keys(self):
        patches = _z_report_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        for key in ("window", "collected", "refunds", "voids", "tips", "by_staff",
                    "food_cost", "labor", "net_cash_position", "net"):
            self.assertIn(key, resp.data, f"Missing top-level key: {key}")

    def test_collected_cash_plus_wallet_equals_total(self):
        """collected.cash + collected.wallet must equal collected.total."""
        patches = _z_report_patches(cash=Decimal("100.00"), wallet=Decimal("50.00"))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        c = resp.data["collected"]
        cash = Decimal(c["cash"])
        wallet = Decimal(c["wallet"])
        total = Decimal(c["total"])
        self.assertEqual(cash + wallet, total, "cash + wallet != total in collected section")

    def test_refunds_predicate_wallet_only_basis(self):
        """refunds.basis must state that cash refunds are not tracked."""
        patches = _z_report_patches(refund_count=2, refund_total=Decimal("30.00"))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        basis = resp.data["refunds"]["basis"]
        self.assertIn("cash", basis.lower(), "basis should mention cash refunds limitation")

    def test_voids_list_shape(self):
        """voids.items must be a list (may be empty)."""
        patches = _z_report_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        self.assertIsInstance(resp.data["voids"]["items"], list)

    def test_window_section_has_service_day_and_cutover(self):
        patches = _z_report_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        w = resp.data["window"]
        self.assertIn("service_day", w)
        self.assertIn("cutover_hour", w)
        self.assertEqual(w["cutover_hour"], 0)

    def test_net_cash_position_equals_collected_cash(self):
        """net_cash_position = collected.cash (no cash-refund ledger)."""
        patches = _z_report_patches(cash=Decimal("123.45"), wallet=Decimal("0.00"))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            req = self._make_request(date_param="2026-06-10")
            resp = self.view(req)
        self.assertEqual(
            Decimal(resp.data["net_cash_position"]),
            Decimal(resp.data["collected"]["cash"]),
        )


class OwnerZReportVoidItemShapeTests(SimpleTestCase):
    """When voided items exist, the voids list must carry correct fields."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerZReportView.as_view()

    def test_void_item_has_required_fields_and_voided_by_propagated(self):
        """Each void entry: order_number, dish_name, qty, line_total, reason, voided_by.
        voided_by propagates OrderItem.voided_by_user_id (integer or null).
        """
        fake_item = MagicMock()
        fake_item.order.order_number = "ORD-001"
        fake_item.dish_name = "Espresso"
        fake_item.qty = 2
        fake_item.unit_price = Decimal("4.50")
        fake_item.void_reason = "wrong size"
        fake_item.voided_by_user_id = 7

        # Order queryset
        order_qs = MagicMock()
        order_qs.filter.return_value = order_qs
        order_qs.aggregate.return_value = {"tips": Decimal("0")}

        # WalletTransaction class
        wt_qs = MagicMock()
        wt_qs.filter.return_value = wt_qs
        wt_qs.aggregate.return_value = {"refund_count": 0, "refund_total": None}
        mock_wt_class = MagicMock()
        mock_wt_class.Type.REFUND = "REFUND"
        mock_wt_class.objects.filter.return_value = wt_qs

        # One voided item
        oi_qs = MagicMock()
        oi_qs.__iter__ = lambda s: iter([fake_item])

        _void_shift_qs = MagicMock()
        _void_shift_qs.__iter__ = lambda s: iter([])
        _mock_shift_cls = MagicMock()
        _mock_shift_cls.objects.filter.return_value.order_by.return_value = _void_shift_qs

        with (
            patch("menu.revenue.split_revenue_for_orders",
                  return_value={"cash": Decimal("0"), "wallet": Decimal("0")}),
            patch("menu.views.Order.objects") as mock_order_objs,
            patch("menu.views.OrderItem.objects") as mock_oi_objs,
            patch("menu.views.OrderPayment.objects") as mock_op_objs,
            patch("accounts.models.WalletTransaction", mock_wt_class),
            patch("menu.models.Shift", _mock_shift_cls),
        ):
            mock_order_objs.filter.return_value = order_qs
            mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
            _fc_chain = MagicMock()
            _fc_chain.annotate.return_value = _fc_chain
            _fc_chain.filter.return_value = _fc_chain
            _fc_chain.aggregate.return_value = {"total": None}
            mock_oi_objs.filter.return_value = _fc_chain
            mock_op_objs.filter.return_value = _make_empty_op_qs()

            req = self.factory.get("/api/owner/z-report/", {"date": "2026-06-10"})
            req.user = _owner_user()
            t = _tenant()
            t.profile = _profile(tz="UTC", cutover=0)
            req.tenant = t
            req.path = "/api/owner/z-report/"
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        voids = resp.data["voids"]["items"]
        self.assertEqual(len(voids), 1)
        item = voids[0]
        for field in ("order_number", "dish_name", "qty", "line_total", "reason", "voided_by"):
            self.assertIn(field, item, f"void item missing field: {field}")
        self.assertEqual(item["voided_by"], 7, "voided_by must propagate voided_by_user_id")
        self.assertEqual(item["reason"], "wrong size")
        self.assertEqual(Decimal(item["line_total"]), Decimal("9.00"))  # 2 × 4.50


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT B (security) — Z-report refund query must include tenant_id filter
# ═══════════════════════════════════════════════════════════════════════════════

class ZReportRefundTenantFilterTests(SimpleTestCase):
    """The WalletTransaction refund query in _build_report MUST filter by tenant_id.

    WalletTransaction lives in the shared public schema — without a tenant_id
    predicate the query aggregates refunds from every tenant on the platform,
    causing cross-tenant data leakage.

    We verify that WalletTransaction.objects.filter is called with tenant_id=<id>
    matching the tenant on the request.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerZReportView.as_view()

    def test_refund_query_includes_tenant_id_filter(self):
        """WalletTransaction.objects.filter must be called with tenant_id= kwarg."""
        # Tenant id=42; we verify this is forwarded to the WalletTransaction filter.
        TEST_TENANT_ID = 42

        order_qs = MagicMock()
        order_qs.filter.return_value = order_qs
        order_qs.aggregate.return_value = {"tips": Decimal("0")}

        wt_qs = MagicMock()
        wt_qs.filter.return_value = wt_qs
        wt_qs.aggregate.return_value = {"refund_count": 0, "refund_total": None}
        mock_wt_class = MagicMock()
        mock_wt_class.Type.REFUND = "REFUND"
        mock_wt_class.objects.filter.return_value = wt_qs

        oi_qs = MagicMock()
        oi_qs.__iter__ = lambda s: iter([])

        _rf_shift_qs = MagicMock()
        _rf_shift_qs.__iter__ = lambda s: iter([])
        _rf_shift_cls = MagicMock()
        _rf_shift_cls.objects.filter.return_value.order_by.return_value = _rf_shift_qs

        with (
            patch("menu.revenue.split_revenue_for_orders",
                  return_value={"cash": Decimal("0"), "wallet": Decimal("0")}),
            patch("menu.views.Order.objects") as mock_order_objs,
            patch("menu.views.OrderItem.objects") as mock_oi_objs,
            patch("menu.views.OrderPayment.objects") as mock_op_objs,
            patch("accounts.models.WalletTransaction", mock_wt_class),
            patch("menu.models.Shift", _rf_shift_cls),
        ):
            mock_order_objs.filter.return_value = order_qs
            mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
            _rfc_chain = MagicMock()
            _rfc_chain.annotate.return_value = _rfc_chain
            _rfc_chain.filter.return_value = _rfc_chain
            _rfc_chain.aggregate.return_value = {"total": None}
            mock_oi_objs.filter.return_value = _rfc_chain
            mock_op_objs.filter.return_value = _make_empty_op_qs()

            req = self.factory.get("/api/owner/z-report/", {"date": "2026-06-10"})
            req.user = _owner_user(tenant_id=TEST_TENANT_ID)
            t = _tenant(tenant_id=TEST_TENANT_ID)
            t.profile = _profile(tz="UTC", cutover=0)
            req.tenant = t
            req.path = "/api/owner/z-report/"
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        # Verify that WalletTransaction.objects.filter was called with tenant_id=42.
        filter_calls = mock_wt_class.objects.filter.call_args_list
        self.assertTrue(
            filter_calls,
            "WalletTransaction.objects.filter was never called"
        )
        all_kwargs = {k: v for call in filter_calls for k, v in call.kwargs.items()}
        self.assertIn(
            "tenant_id", all_kwargs,
            "WalletTransaction refund filter is missing tenant_id — cross-tenant leak!"
        )
        self.assertEqual(
            all_kwargs["tenant_id"], TEST_TENANT_ID,
            f"tenant_id in filter is {all_kwargs.get('tenant_id')}, expected {TEST_TENANT_ID}"
        )

    def test_collected_predicate_includes_payment_status_paid(self):
        """collected_qs must filter on payment_status=PAID in addition to status=COMPLETED.

        This prevents a future status-flow change that could mark an order COMPLETED
        without PAID from silently inflating the drawer total.
        """
        factory = APIRequestFactory()
        view = OwnerZReportView.as_view()

        order_filter_kwargs_list = []

        order_qs = MagicMock()
        order_qs.filter.return_value = order_qs
        order_qs.aggregate.return_value = {"tips": Decimal("0")}

        def capture_filter(**kwargs):
            order_filter_kwargs_list.append(kwargs)
            return order_qs

        oi_qs = MagicMock()
        oi_qs.__iter__ = lambda s: iter([])

        wt_qs = MagicMock()
        wt_qs.filter.return_value = wt_qs
        wt_qs.aggregate.return_value = {"refund_count": 0, "refund_total": None}
        mock_wt_class = MagicMock()
        mock_wt_class.Type.REFUND = "REFUND"
        mock_wt_class.objects.filter.return_value = wt_qs

        with (
            patch("menu.revenue.split_revenue_for_orders",
                  return_value={"cash": Decimal("0"), "wallet": Decimal("0")}),
            patch("menu.views.Order.objects") as mock_order_objs,
            patch("menu.views.OrderItem.objects") as mock_oi_objs,
            patch("menu.views.OrderPayment.objects") as mock_op_objs,
            patch("accounts.models.WalletTransaction", mock_wt_class),
        ):
            mock_order_objs.filter.side_effect = capture_filter
            mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
            mock_op_objs.filter.return_value = _make_empty_op_qs()

            req = factory.get("/api/owner/z-report/", {"date": "2026-06-10"})
            req.user = _owner_user()
            t = _tenant()
            t.profile = _profile(tz="UTC", cutover=0)
            req.tenant = t
            req.path = "/api/owner/z-report/"
            view(req)

        # At least one Order.objects.filter call must include payment_status
        all_filter_keys = {k for call_kwargs in order_filter_kwargs_list for k in call_kwargs}
        self.assertIn(
            "payment_status",
            all_filter_keys,
            "collected_qs Order.objects.filter is missing payment_status — COMPLETED orders "
            "without PAID status could inflate the drawer total."
        )

    def test_by_staff_uses_order_paid_at_not_created_at(self):
        """OrderPayment.objects.filter in by_staff must use order__paid_at, not created_at.

        Filtering by OrderPayment.created_at (instead of the parent order's paid_at)
        causes split-bill instalments to land in a different service day from the
        collected header, breaking Sum(by_staff) == collected.total reconciliation.
        """
        op_filter_kwargs_list = []

        def op_filter(**kwargs):
            op_filter_kwargs_list.append(kwargs)
            return _make_empty_op_qs()

        order_qs = MagicMock()
        order_qs.filter.return_value = order_qs
        order_qs.aggregate.return_value = {"tips": Decimal("0")}

        oi_qs = MagicMock()
        oi_qs.__iter__ = lambda s: iter([])

        wt_qs = MagicMock()
        wt_qs.filter.return_value = wt_qs
        wt_qs.aggregate.return_value = {"refund_count": 0, "refund_total": None}
        mock_wt_class = MagicMock()
        mock_wt_class.Type.REFUND = "REFUND"
        mock_wt_class.objects.filter.return_value = wt_qs

        factory = APIRequestFactory()
        view = OwnerZReportView.as_view()

        with (
            patch("menu.revenue.split_revenue_for_orders",
                  return_value={"cash": Decimal("0"), "wallet": Decimal("0")}),
            patch("menu.views.Order.objects") as mock_order_objs,
            patch("menu.views.OrderItem.objects") as mock_oi_objs,
            patch("menu.views.OrderPayment.objects") as mock_op_objs,
            patch("accounts.models.WalletTransaction", mock_wt_class),
        ):
            mock_order_objs.filter.return_value = order_qs
            mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
            mock_op_objs.filter.side_effect = op_filter

            req = factory.get("/api/owner/z-report/", {"date": "2026-06-10"})
            req.user = _owner_user()
            t = _tenant()
            t.profile = _profile(tz="UTC", cutover=0)
            req.tenant = t
            req.path = "/api/owner/z-report/"
            view(req)

        all_op_keys = {k for call_kwargs in op_filter_kwargs_list for k in call_kwargs}
        self.assertIn(
            "order__paid_at__gte", all_op_keys,
            "by_staff OrderPayment filter must use order__paid_at__gte (not created_at__gte) "
            "so that staff totals reconcile with the collected header."
        )
        self.assertIn(
            "order__paid_at__lt", all_op_keys,
            "by_staff OrderPayment filter must use order__paid_at__lt (not created_at__lt)"
        )
        self.assertNotIn(
            "created_at__gte", all_op_keys,
            "by_staff must NOT filter on OrderPayment.created_at__gte — "
            "use order__paid_at__gte instead."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT C — Revenue-truth: payment_split uses PAID orders only
# ═══════════════════════════════════════════════════════════════════════════════

class RevenueTruthPaymentSplitTests(SimpleTestCase):
    """Dine-in orders in PREPARING/READY/CONFIRMED must NOT be counted as collected cash.

    The fix (Contract C): filter payment_split by payment_status=PAID so only
    orders that have actually been paid contribute to the cash/wallet drawer.
    """

    def test_send_daily_summary_calls_split_on_paid_qs_only(self):
        """Confirm split_revenue_for_orders is called with the PAID-filtered queryset,
        not the gross_statuses queryset.
        """
        import menu.management.commands.send_daily_summary as _mod
        from menu.management.commands.send_daily_summary import _compute_summary

        mock_split = MagicMock(return_value={"cash": Decimal("0"), "wallet": Decimal("0")})

        mock_payment = MagicMock()
        mock_payment.Method.WALLET = "wallet"
        mock_payment.Method.CASH = "cash"
        ledger_qs = MagicMock()
        ledger_qs.values_list.return_value.distinct.return_value = []
        ledger_qs.filter.return_value.aggregate.return_value = {
            "ledger_wallet": Decimal("0"),
            "ledger_cash": Decimal("0"),
        }
        mock_payment.objects.filter.return_value = ledger_qs

        with (
            patch.object(_mod, "Order") as mock_order,
            patch.object(_mod, "OrderItem") as mock_item,
            patch("menu.models.OrderPayment", mock_payment),
            patch("menu.revenue.split_revenue_for_orders", mock_split),
        ):
            mock_order.Status.COMPLETED = "completed"
            mock_order.Status.READY = "ready"
            mock_order.Status.PREPARING = "preparing"
            mock_order.Status.CONFIRMED = "confirmed"
            mock_order.PaymentStatus.PAID = "paid"

            # paid_qs = qs.filter(payment_status="paid") → distinct mock
            paid_qs_mock = MagicMock()
            paid_qs_mock.exists.return_value = False

            qs = MagicMock()
            qs.filter.return_value = paid_qs_mock
            qs.aggregate.return_value = {
                "order_count": 2,
                "total_revenue": Decimal("100.00"),
            }
            qs.exists.return_value = True
            mock_order.objects.filter.return_value = qs

            item_qs = MagicMock()
            item_qs.filter.return_value = item_qs
            item_qs.exclude.return_value = item_qs
            item_qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
            mock_item.objects = item_qs

            _compute_summary("schema", MagicMock(), MagicMock())

        # split_revenue_for_orders must have been called with paid_qs (not the gross qs)
        self.assertTrue(mock_split.called, "split_revenue_for_orders was not called")
        args, _ = mock_split.call_args
        actual_qs = args[0] if args else None
        self.assertIs(
            actual_qs, paid_qs_mock,
            "split_revenue_for_orders was called with qs instead of paid_qs. "
            "Revenue-truth fix (Contract C) is not working."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT D — Payment method correction
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentMethodCorrectionTests(SimpleTestCase):
    """StaffPaymentMethodCorrectionView — relabels method, writes audit fields,
    does NOT touch wallet balance, WalletTransaction, or wallet_amount_paid."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffPaymentMethodCorrectionView.as_view()

    def _make_payment(self, method="cash", original_method="", order_tenant_id=1):
        payment = MagicMock()
        payment.id = 99
        payment.order_id = 10
        payment.amount = Decimal("50.00")
        payment.method = method
        payment.original_method = original_method
        payment.recorded_by_name = "Alice"
        payment.note = ""
        payment.created_at = datetime(2026, 6, 10, 12, 0, tzinfo=stdlib_tz.utc)
        payment.corrected_at = None
        payment.corrected_by_name = ""
        order = MagicMock()
        order.order_number = "ORD-010"
        order.tenant_id = order_tenant_id
        payment.order = order
        return payment

    def _req(self, body, user=None, tenant=None, order_id=10, payment_id=99):
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/payments/{payment_id}/correct-method/",
            body,
            format="json",
        )
        req.user = user or _staff_user()
        req.tenant = tenant or _tenant()
        return req

    def _patch_payment_lookup(self, payment):
        """Patch OrderPayment.objects so the view finds our mock payment."""
        mock_objs = MagicMock()
        mock_objs.select_related.return_value.filter.return_value.first.return_value = payment
        return patch("menu.views.OrderPayment.objects", mock_objs)

    def test_method_updated_on_success(self):
        """POST with valid new_method updates the payment.method field."""
        payment = self._make_payment(method="cash")
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "wallet"})
            resp = self.view(req, order_id=10, payment_id=99)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(payment.method, "wallet")

    def test_original_method_captured_on_first_correction(self):
        """original_method must be set to the old method on first correction only."""
        payment = self._make_payment(method="cash", original_method="")
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "wallet"})
            self.view(req, order_id=10, payment_id=99)
        self.assertEqual(payment.original_method, "cash")

    def test_original_method_not_overwritten_on_second_correction(self):
        """If original_method is already set, it must not be changed again."""
        payment = self._make_payment(method="wallet", original_method="cash")
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "cash"})
            self.view(req, order_id=10, payment_id=99)
        # original_method must still be "cash", not "wallet"
        self.assertEqual(payment.original_method, "cash")

    def test_corrected_at_and_by_name_written(self):
        """corrected_at and corrected_by_name must be written."""
        payment = self._make_payment(method="cash")
        user = _staff_user()
        user.get_full_name.return_value = "Bob Smith"
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "wallet"}, user=user)
            self.view(req, order_id=10, payment_id=99)
        self.assertIsNotNone(payment.corrected_at)
        self.assertIn("Bob", payment.corrected_by_name)

    def test_wallet_balance_not_touched(self):
        """WalletTransaction must never be called from this endpoint."""
        payment = self._make_payment(method="cash")
        with (
            self._patch_payment_lookup(payment),
            patch("accounts.models.WalletTransaction") as mock_wt,
        ):
            req = self._req({"method": "wallet"})
            self.view(req, order_id=10, payment_id=99)
        mock_wt.objects.create.assert_not_called()
        mock_wt.objects.filter.assert_not_called()

    def test_invalid_method_returns_400(self):
        """A method value other than cash/wallet returns 400."""
        payment = self._make_payment(method="cash")
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "bitcoin"})
            resp = self.view(req, order_id=10, payment_id=99)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_method_returns_409(self):
        """Correcting to the same method as currently recorded returns 409 Conflict."""
        payment = self._make_payment(method="cash")
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "cash"})
            resp = self.view(req, order_id=10, payment_id=99)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_non_staff_gets_403(self):
        """Users from a different tenant are denied by _can_edit_tenant_order."""
        payment = self._make_payment(method="cash")
        outsider = _staff_user(tenant_id=999)
        outsider.is_superuser = False
        outsider.is_staff = False
        outsider.is_platform_admin = False
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "wallet"}, user=outsider)
            resp = self.view(req, order_id=10, payment_id=99)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_includes_audit_fields(self):
        """Response payload must include original_method, corrected_at, corrected_by_name."""
        payment = self._make_payment(method="cash", original_method="")
        user = _staff_user()
        user.get_full_name.return_value = "Alice"
        with self._patch_payment_lookup(payment):
            req = self._req({"method": "wallet"}, user=user)
            resp = self.view(req, order_id=10, payment_id=99)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("original_method", "corrected_at", "corrected_by_name"):
            self.assertIn(field, resp.data, f"Missing audit field: {field}")


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT A (serializer validation) — service_day_cutover_hour validator
# ═══════════════════════════════════════════════════════════════════════════════

class ServiceDayCutoverHourValidatorTests(SimpleTestCase):
    """ProfileSerializer must reject out-of-range values for service_day_cutover_hour."""

    def _validate(self, value):
        from tenancy.serializers import ProfileSerializer
        return ProfileSerializer().validate_service_day_cutover_hour(value)

    def test_zero_is_valid(self):
        self.assertEqual(self._validate(0), 0)

    def test_eleven_is_valid(self):
        self.assertEqual(self._validate(11), 11)

    def test_four_is_valid(self):
        self.assertEqual(self._validate(4), 4)

    def test_negative_raises(self):
        from rest_framework import serializers
        with self.assertRaises(serializers.ValidationError):
            self._validate(-1)

    def test_twelve_raises(self):
        from rest_framework import serializers
        with self.assertRaises(serializers.ValidationError):
            self._validate(12)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT B — Z-report collected predicate uses paid_at, not created_at
# ═══════════════════════════════════════════════════════════════════════════════

class ZReportCollectedPredicateTests(SimpleTestCase):
    """The collected queryset must filter on paid_at (not created_at or status_updated_at)."""

    def test_filter_uses_paid_at_field(self):
        """Order.objects.filter(...) must be called with paid_at__gte and paid_at__lt."""
        factory = APIRequestFactory()
        view = OwnerZReportView.as_view()

        called_with = {}

        order_qs = MagicMock()
        order_qs.filter.return_value = order_qs
        order_qs.aggregate.return_value = {"tips": Decimal("0")}

        def capture_filter(**kwargs):
            called_with.update(kwargs)
            return order_qs

        oi_qs = MagicMock()
        oi_qs.__iter__ = lambda s: iter([])

        wt_qs = MagicMock()
        wt_qs.filter.return_value = wt_qs
        wt_qs.aggregate.return_value = {"refund_count": 0, "refund_total": None}
        mock_wt_class = MagicMock()
        mock_wt_class.Type.REFUND = "REFUND"
        mock_wt_class.objects.filter.return_value = wt_qs

        with (
            patch("menu.revenue.split_revenue_for_orders",
                  return_value={"cash": Decimal("0"), "wallet": Decimal("0")}),
            patch("menu.views.Order.objects") as mock_order_objs,
            patch("menu.views.OrderItem.objects") as mock_oi_objs,
            patch("menu.views.OrderPayment.objects") as mock_op_objs,
            patch("accounts.models.WalletTransaction", mock_wt_class),
        ):
            mock_order_objs.filter.side_effect = capture_filter
            mock_oi_objs.select_related.return_value.filter.return_value = oi_qs
            mock_op_objs.filter.return_value = _make_empty_op_qs()

            req = factory.get("/api/owner/z-report/", {"date": "2026-06-10"})
            req.user = _owner_user()
            t = _tenant()
            t.profile = _profile(tz="UTC", cutover=0)
            req.tenant = t
            req.path = "/api/owner/z-report/"
            view(req)

        self.assertIn("paid_at__gte", called_with,
                      "collected_qs filter must use paid_at__gte (not created_at)")
        self.assertIn("paid_at__lt", called_with,
                      "collected_qs filter must use paid_at__lt (not created_at)")
        self.assertNotIn("created_at__gte", called_with,
                         "collected_qs must NOT filter on created_at__gte")
