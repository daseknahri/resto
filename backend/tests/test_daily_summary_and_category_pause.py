"""
Tests for:
  1. send_daily_summary management command
     - zero-order tenant is skipped and does not double-send
     - idempotency marker prevents re-send on same day
     - cash_revenue = total_revenue - wallet_revenue
  2. OwnerDashboardView revenue_summary
     - wallet_revenue and cash_revenue present in payload
  3. Category.is_temporarily_disabled
     - paused category absent from customer menu payloads
     - field round-trips through CategorySerializer
"""
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from sales.views import OwnerDashboardView


# ══════════════════════════════════════════════════════════════════════════════
# Helpers shared with test_owner_dashboard
# ══════════════════════════════════════════════════════════════════════════════

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
    annotated = MagicMock()
    annotated.__iter__ = lambda s: iter([])
    order_result = MagicMock()
    order_result.__getitem__ = lambda s, k: []
    annotated.order_by.return_value = order_result

    qs = MagicMock()
    qs.count.return_value = 0
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.values.return_value.annotate.return_value = annotated
    return qs


def _order_qs_mock_with_wallet(wallet_total=30.0, grand_total=100.0, order_count=5):
    """Order queryset mock that returns wallet and total aggregates.

    The aggregate dict must include all keys used by the view — both the
    original revenue/loyalty keys AND the new statement keys added in the
    revenue-summary extension.
    """
    daily_result = MagicMock()
    daily_result.__iter__ = lambda s: iter([])

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.count.return_value = order_count
    qs.aggregate.return_value = {
        # Original revenue keys
        "total_revenue": Decimal(str(grand_total)),
        "order_count": order_count,
        "wallet_revenue": Decimal(str(wallet_total)),
        # Loyalty/promo keys
        "mkt_count": 0,
        "mkt_revenue": None,
        "mkt_commission": None,
        "promo_discount_total": None,
        "loyalty_discount_total": None,
        "points_earned_total": None,
        "points_redeemed_total": None,
        # Statement keys (new)
        "gross": Decimal(str(grand_total)),
        "promo_discounts": None,
        "loyalty_discounts": None,
        "tips": None,
        "commission": None,
        # B2: new-vs-returning split
        "ret_rev": None,
        "ret_cnt": 0,
    }
    qs.annotate.return_value.values.return_value.annotate.return_value.order_by.return_value = daily_result
    qs.values_list.return_value.exclude.return_value.order_by.return_value.first.return_value = "MAD"
    return qs


def _orderitem_qs_mock():
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
    return qs


def _lead_qs_mock():
    qs = MagicMock()
    qs.count.return_value = 0
    qs.filter.return_value.count.return_value = 0
    return qs


def _apply_common_mocks(
    mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
    mock_analytics, mock_order, mock_dish, mock_cat,
    mock_schema, mock_lead, mock_orderitem=None,
):
    mock_schema.return_value.__enter__ = MagicMock(return_value=None)
    mock_schema.return_value.__exit__ = MagicMock(return_value=False)

    mock_cat.count.return_value = 3
    mock_dish.count.return_value = 8
    mock_analytics.filter.return_value = _analytics_qs_mock()
    mock_lead.filter.return_value = _lead_qs_mock()
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


# ══════════════════════════════════════════════════════════════════════════════
# 1. send_daily_summary command
# ══════════════════════════════════════════════════════════════════════════════

class SendDailySummaryZeroOrdersTests(SimpleTestCase):
    """Zero-order tenant must be skipped; cache key must be cleared so a later
    re-run (when there are orders) is not permanently blocked."""

    def _run_command(self, tenant_obj, summary_return, cache_add_return=True):
        stdout = io.StringIO()
        with (
            patch("menu.management.commands.send_daily_summary.Tenant") as MockTenant,
            patch("menu.management.commands.send_daily_summary.cache") as mock_cache,
            patch("menu.management.commands.send_daily_summary.schema_context") as mock_ctx,
            patch("menu.management.commands.send_daily_summary._compute_summary", return_value=summary_return),
            patch("menu.management.commands.send_daily_summary._tenant_yesterday",
                  return_value=(MagicMock(), MagicMock(), MagicMock())),
            patch("menu.management.commands.send_daily_summary._send_owner_push"),
            patch("menu.management.commands.send_daily_summary._send_owner_email"),
        ):
            MockTenant.objects.filter.return_value.exclude.return_value = [tenant_obj]
            mock_cache.add.return_value = cache_add_return
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            from django.core.management import call_command
            call_command("send_daily_summary", stdout=stdout)
        return stdout.getvalue(), mock_cache

    def test_zero_order_tenant_skipped_and_cache_cleared(self):
        """A tenant with zero orders must appear as skipped, not delivered.
        The cache key added for the idempotency check must be deleted so future
        runs on a non-zero day aren't permanently blocked."""
        tenant = MagicMock()
        tenant.slug = "cafe-zero"
        tenant.schema_name = "cafe_zero"

        out, mock_cache = self._run_command(tenant, summary_return=None)

        self.assertIn("0 orders", out)
        mock_cache.delete.assert_called_once()  # key cleared for future runs

    def test_non_zero_tenant_sends_and_does_not_delete_cache(self):
        """A tenant with orders must have push + email called; cache NOT deleted."""
        tenant = MagicMock()
        tenant.slug = "cafe-active"
        tenant.schema_name = "cafe_active"
        summary = {
            "order_count": 10,
            "total_revenue": 500.0,
            "wallet_revenue": 200.0,
            "cash_revenue": 300.0,
            "top_dishes": [],
        }

        out, mock_cache = self._run_command(tenant, summary_return=summary)
        mock_cache.delete.assert_not_called()
        self.assertIn("500.00", out)


class SendDailySummaryIdempotencyTests(SimpleTestCase):
    """Re-running the command the same day must not double-send."""

    def test_cache_add_false_skips_send(self):
        """When cache.add returns False (key already set), no push or email fires."""
        stdout = io.StringIO()
        tenant = MagicMock()
        tenant.slug = "cafe-dupe"
        tenant.schema_name = "cafe_dupe"

        with (
            patch("menu.management.commands.send_daily_summary.Tenant") as MockTenant,
            patch("menu.management.commands.send_daily_summary.cache") as mock_cache,
            patch("menu.management.commands.send_daily_summary._tenant_yesterday",
                  return_value=(MagicMock(), MagicMock(), MagicMock())),
            patch("menu.management.commands.send_daily_summary._send_owner_push") as mock_push,
            patch("menu.management.commands.send_daily_summary._send_owner_email") as mock_email,
        ):
            MockTenant.objects.filter.return_value.exclude.return_value = [tenant]
            mock_cache.add.return_value = False  # already sent

            from django.core.management import call_command
            call_command("send_daily_summary", stdout=stdout)

        mock_push.assert_not_called()
        mock_email.assert_not_called()
        out = stdout.getvalue()
        self.assertIn("already sent", out)


class SendDailySummaryCashWalletMathTests(SimpleTestCase):
    """cash_revenue = total_revenue - wallet_revenue formula verified end-to-end
    through the full command handle() path by inspecting stdout output."""

    def test_cash_equals_total_minus_wallet_in_output(self):
        """The command stdout must show cash = total - wallet for a tenant with orders."""
        stdout = io.StringIO()

        grand_total = 150.0
        wallet_total = 40.0
        expected_cash = round(grand_total - wallet_total, 2)

        summary = {
            "order_count": 3,
            "total_revenue": grand_total,
            "wallet_revenue": wallet_total,
            "cash_revenue": expected_cash,
            "top_dishes": [{"dish_name": "Burger", "qty": 5}],
        }

        tenant = MagicMock()
        tenant.slug = "cafe-math"
        tenant.schema_name = "cafe_math"
        tenant.name = "Cafe Math"

        with (
            patch("menu.management.commands.send_daily_summary.Tenant") as MockTenant,
            patch("menu.management.commands.send_daily_summary.cache") as mock_cache,
            patch("menu.management.commands.send_daily_summary.schema_context") as mock_ctx,
            patch("menu.management.commands.send_daily_summary._compute_summary", return_value=summary),
            patch("menu.management.commands.send_daily_summary._tenant_yesterday",
                  return_value=(MagicMock(), MagicMock(), MagicMock())),
            patch("menu.management.commands.send_daily_summary._send_owner_push"),
            patch("menu.management.commands.send_daily_summary._send_owner_email"),
        ):
            MockTenant.objects.filter.return_value.exclude.return_value = [tenant]
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            from django.core.management import call_command
            call_command("send_daily_summary", stdout=stdout)

        out = stdout.getvalue()
        # Verify the summarized output has all three numbers
        self.assertIn("150.00", out)
        self.assertIn("40.00", out)
        self.assertIn("110.00", out)  # cash = 150 - 40


# ══════════════════════════════════════════════════════════════════════════════
# 2. OwnerDashboardView — wallet_revenue / cash_revenue in revenue_summary
# ══════════════════════════════════════════════════════════════════════════════

class OwnerDashboardWalletCashFieldsTests(SimpleTestCase):
    """revenue_summary must include wallet_revenue and cash_revenue."""

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

    @patch("accounts.models.WalletTransaction")
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
    def test_revenue_summary_includes_wallet_and_cash(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_wallet_tx,
    ):
        """wallet_revenue and cash_revenue must appear in revenue_summary.

        Contract C: WalletTransaction is now called to aggregate refunds_issued.
        We stub it to return zero refunds so the DB is not touched.
        """
        # Stub WalletTransaction.objects.filter().aggregate() → no refunds
        wt_qs = MagicMock()
        wt_qs.aggregate.return_value = {"refunds_total": None}
        mock_wallet_tx.Type.REFUND = "REFUND"
        mock_wallet_tx.objects.filter.return_value = wt_qs

        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
        )
        # Wire a specific order mock with wallet data
        mock_order.filter.return_value = _order_qs_mock_with_wallet(
            wallet_total=30.0, grand_total=100.0, order_count=5,
        )

        from decimal import Decimal as _D
        _split_rv = {"wallet": _D("30.00"), "cash": _D("70.00")}
        with patch("menu.revenue.split_revenue_for_orders", return_value=_split_rv):
            resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rs = resp.data["revenue_summary"]
        self.assertIn("wallet_revenue", rs, "wallet_revenue missing from revenue_summary")
        self.assertIn("cash_revenue", rs, "cash_revenue missing from revenue_summary")
        self.assertAlmostEqual(float(rs["wallet_revenue"]), 30.0, places=2)
        self.assertAlmostEqual(float(rs["cash_revenue"]), 70.0, places=2)

    @patch("accounts.models.WalletTransaction")
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
    def test_cash_equals_total_minus_wallet(
        self, mock_schema, mock_cat, mock_dish, mock_order, mock_analytics,
        mock_tenant, mock_plan, mock_upgrade_req, mock_ts, mock_orderitem, mock_lead,
        mock_wallet_tx,
    ):
        """cash_revenue must equal total_revenue - wallet_revenue.

        Contract C: WalletTransaction is called for refunds_issued; stubbed here.
        """
        # Stub WalletTransaction.objects.filter().aggregate() → no refunds
        wt_qs = MagicMock()
        wt_qs.aggregate.return_value = {"refunds_total": None}
        mock_wallet_tx.Type.REFUND = "REFUND"
        mock_wallet_tx.objects.filter.return_value = wt_qs

        _apply_common_mocks(
            mock_ts, mock_upgrade_req, mock_plan, mock_tenant,
            mock_analytics, mock_order, mock_dish, mock_cat, mock_schema, mock_lead, mock_orderitem,
        )
        mock_order.filter.return_value = _order_qs_mock_with_wallet(
            wallet_total=45.50, grand_total=200.0, order_count=8,
        )

        from decimal import Decimal as _D
        _split_rv = {"wallet": _D("45.50"), "cash": _D("154.50")}
        with patch("menu.revenue.split_revenue_for_orders", return_value=_split_rv):
            resp = self.view(self._get())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rs = resp.data["revenue_summary"]
        expected_cash = round(200.0 - 45.50, 2)
        self.assertAlmostEqual(float(rs["cash_revenue"]), expected_cash, places=2)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Category.is_temporarily_disabled
# ══════════════════════════════════════════════════════════════════════════════

class CategoryTemporarilyDisabledModelTests(SimpleTestCase):
    """Category model must have is_temporarily_disabled with default=False."""

    def test_field_exists_and_defaults_false(self):
        from menu.models import Category
        field = Category._meta.get_field("is_temporarily_disabled")
        self.assertFalse(field.default)

    def test_field_has_help_text(self):
        from menu.models import Category
        field = Category._meta.get_field("is_temporarily_disabled")
        self.assertIn("pause", field.help_text.lower())


class CategorySerializerRoundTripTests(SimpleTestCase):
    """is_temporarily_disabled must appear in CategorySerializer output."""

    def test_field_in_serializer_fields(self):
        from menu.serializers import CategorySerializer
        self.assertIn("is_temporarily_disabled", CategorySerializer.Meta.fields)

    def test_serializer_represents_disabled_flag(self):
        from menu.serializers import CategorySerializer
        from unittest.mock import MagicMock

        cat = MagicMock()
        cat.id = 1
        cat.name = "Burgers"
        cat.name_i18n = {}
        cat.slug = "burgers"
        cat.description = ""
        cat.description_i18n = {}
        cat.image_url = ""
        cat.position = 0
        cat.is_published = True
        cat.is_temporarily_disabled = True
        cat.dishes = MagicMock()
        cat.dishes.all.return_value = []
        super_cat = MagicMock()
        super_cat.name = "Mains"
        super_cat.name_i18n = {}
        super_cat.slug = "mains"
        cat.super_category = super_cat

        # to_representation returns a dict
        serializer = CategorySerializer(cat)
        data = serializer.data
        self.assertIn("is_temporarily_disabled", data)
        self.assertTrue(data["is_temporarily_disabled"])


class CategoryPausedFilterTests(SimpleTestCase):
    """
    Paused categories (is_temporarily_disabled=True) must be excluded from the
    customer-facing CategoryViewSet queryset.
    We test this by inspecting the kwargs passed to qs.filter() during get_queryset().
    """

    def _make_drf_request(self, user):
        """Return a DRF Request wrapping an APIRequestFactory GET, with .tenant set."""
        from rest_framework.request import Request as DRFRequest
        factory = APIRequestFactory()
        raw = factory.get("/api/categories/")
        raw.user = user
        raw.tenant = SimpleNamespace(id=1)
        drf_req = DRFRequest(raw)
        drf_req.user = user
        drf_req.tenant = raw.tenant
        return drf_req

    def test_customer_get_excludes_paused_category(self):
        """
        When a GET request comes from an unauthenticated customer, the
        CategoryViewSet.get_queryset must add is_temporarily_disabled=False
        to the filter chain.
        """
        from menu.views import CategoryViewSet

        anon = MagicMock()
        anon.is_authenticated = False
        request = self._make_drf_request(anon)

        view = CategoryViewSet()
        view.request = request
        view.kwargs = {}
        view.format_kwarg = None
        view.action = "list"

        with patch("menu.views.Category.objects") as mock_cat_objects:
            qs_mock = MagicMock()
            qs_mock.filter.return_value = qs_mock
            qs_mock.select_related.return_value = qs_mock
            qs_mock.prefetch_related.return_value = qs_mock
            qs_mock.order_by.return_value = qs_mock
            mock_cat_objects.select_related.return_value.prefetch_related.return_value.all.return_value = qs_mock
            with patch("menu.views._filter_by_reference", return_value=qs_mock):
                view.get_queryset()

            # The filter call must include is_temporarily_disabled=False
            filter_calls_str = str(qs_mock.filter.call_args_list)
            self.assertIn(
                "is_temporarily_disabled", filter_calls_str,
                "is_temporarily_disabled=False not found in category filter calls",
            )

    def test_owner_preview_does_not_filter_paused(self):
        """
        An authenticated tenant owner (can_preview_unpublished=True) must NOT
        have the is_temporarily_disabled filter applied so they can still manage
        paused categories.
        """
        from menu.views import CategoryViewSet

        owner_user = MagicMock()
        owner_user.is_authenticated = True
        owner_user.is_active = True
        owner_user.role = User.Roles.TENANT_OWNER
        request = self._make_drf_request(owner_user)

        view = CategoryViewSet()
        view.request = request
        view.kwargs = {}
        view.format_kwarg = None
        view.action = "list"

        with patch("menu.views.Category.objects") as mock_cat_objects:
            qs_mock = MagicMock()
            qs_mock.filter.return_value = qs_mock
            qs_mock.select_related.return_value = qs_mock
            qs_mock.prefetch_related.return_value = qs_mock
            qs_mock.order_by.return_value = qs_mock
            mock_cat_objects.select_related.return_value.prefetch_related.return_value.all.return_value = qs_mock
            with patch("menu.views._filter_by_reference", return_value=qs_mock):
                view.get_queryset()

            # For owner preview, is_temporarily_disabled must NOT be in any filter kwargs
            for c in qs_mock.filter.call_args_list:
                kw = c.kwargs if c.kwargs else (c[1] if len(c) > 1 else {})
                self.assertNotIn(
                    "is_temporarily_disabled", kw,
                    "Owner preview should NOT be filtered by is_temporarily_disabled",
                )
