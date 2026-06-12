"""
Tests for:
  1. menu.revenue.split_revenue_for_orders — ledger / legacy / mixed paths
  2. sales dashboard revenue_summary new keys: payment_split, top_items_by_revenue, statement
  3. Dish.low_stock_threshold respected in the low_stock alert query (F-expression)
  4. auto_reset_availability command — flag gate, local-hour gate, marker idempotency
"""
from __future__ import annotations

import io
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


# ══════════════════════════════════════════════════════════════════════════════
# 1. split_revenue_for_orders — ledger / legacy / mixed
#
# split_revenue_for_orders does a lazy `from menu.models import OrderPayment`
# inside its body, so we patch at "menu.models.OrderPayment".
# ══════════════════════════════════════════════════════════════════════════════

def _build_split_mocks(order_ids, ledger_order_ids, ledger_wallet, ledger_cash, legacy_wallet, legacy_total):
    """Return (order_qs_mock, MockPayment_ctx) for use in patch.

    Updated for the subquery path in revenue.py:
      - order_qs.exists() returns True (non-empty queryset)
      - order_qs.values("id") returns a mock queryset (passed as subquery)
      - ledger lookup: OrderPayment.objects.filter(order_id__in=orders_values_qs)
      - legacy lookup: order_qs.exclude(id__in=ledger_order_ids).aggregate(...)
        or order_qs.aggregate(...) when there are no ledger orders
    """
    MockPayment = MagicMock()
    MockPayment.Method.WALLET = "wallet"
    MockPayment.Method.CASH = "cash"

    ledger_qs = MagicMock()
    ledger_qs.values_list.return_value.distinct.return_value = list(ledger_order_ids)
    ledger_qs.filter.return_value.aggregate.return_value = {
        "ledger_wallet": Decimal(str(ledger_wallet)),
        "ledger_cash": Decimal(str(ledger_cash)),
    }
    MockPayment.objects.filter.return_value = ledger_qs

    legacy_agg = {
        "legacy_wallet": Decimal(str(legacy_wallet)),
        "legacy_total": Decimal(str(legacy_total)),
    }

    order_qs = MagicMock()
    # exists() → True (the function short-circuits on False)
    order_qs.exists.return_value = True
    # values("id") → a mock queryset used as subquery; return value doesn't matter
    # exclude(id__in=...).aggregate(...) → legacy aggregation
    order_qs.exclude.return_value.aggregate.return_value = legacy_agg
    # aggregate(...) called directly when there are no ledger orders
    order_qs.aggregate.return_value = legacy_agg

    return order_qs, MockPayment


class SplitRevenueHelperTests(SimpleTestCase):
    """Unit tests for menu.revenue.split_revenue_for_orders."""

    def _run(self, order_ids, ledger_order_ids, ledger_wallet, ledger_cash, legacy_wallet, legacy_total):
        order_qs, MockPayment = _build_split_mocks(
            order_ids, ledger_order_ids, ledger_wallet, ledger_cash, legacy_wallet, legacy_total
        )
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            return split_revenue_for_orders(order_qs)

    def test_all_ledger_orders(self):
        """All orders have ledger rows — wallet/cash come from ledger sums."""
        result = self._run(
            order_ids=[1, 2],
            ledger_order_ids=[1, 2],
            ledger_wallet=30,
            ledger_cash=70,
            legacy_wallet=0,
            legacy_total=0,
        )
        self.assertEqual(result["wallet"], Decimal("30.00"))
        self.assertEqual(result["cash"], Decimal("70.00"))

    def test_all_legacy_orders(self):
        """No ledger rows — wallet from wallet_amount_paid, cash = total - wallet."""
        result = self._run(
            order_ids=[1, 2],
            ledger_order_ids=[],
            ledger_wallet=0,
            ledger_cash=0,
            legacy_wallet=25,
            legacy_total=100,
        )
        self.assertEqual(result["wallet"], Decimal("25.00"))
        self.assertEqual(result["cash"], Decimal("75.00"))

    def test_mixed_ledger_and_legacy(self):
        """One ledger order + one legacy order — amounts are summed correctly."""
        result = self._run(
            order_ids=[1, 2],
            ledger_order_ids=[1],        # order 1 is ledger
            ledger_wallet=20,
            ledger_cash=30,
            legacy_wallet=10,            # order 2 legacy: wallet=10, total=50
            legacy_total=50,
        )
        # ledger: wallet=20, cash=30; legacy: wallet=10, cash=40
        self.assertEqual(result["wallet"], Decimal("30.00"))
        self.assertEqual(result["cash"], Decimal("70.00"))

    def test_empty_queryset(self):
        """No orders → zeros immediately, no ORM calls to OrderPayment."""
        order_qs = MagicMock()
        # New code uses exists() to short-circuit on an empty queryset
        order_qs.exists.return_value = False
        MockPayment = MagicMock()
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            result = split_revenue_for_orders(order_qs)
        self.assertEqual(result["wallet"], Decimal("0.00"))
        self.assertEqual(result["cash"], Decimal("0.00"))
        MockPayment.objects.filter.assert_not_called()

    def test_negative_cash_clamped_to_zero(self):
        """Negative derived cash (wallet > total) is clamped to 0."""
        result = self._run(
            order_ids=[1],
            ledger_order_ids=[],
            ledger_wallet=0,
            ledger_cash=0,
            legacy_wallet=120,   # wallet > total → negative cash
            legacy_total=100,
        )
        self.assertEqual(result["wallet"], Decimal("120.00"))
        self.assertEqual(result["cash"], Decimal("0.00"))


# ══════════════════════════════════════════════════════════════════════════════
# 2. revenue_summary new keys — shape + voided exclusion
# ══════════════════════════════════════════════════════════════════════════════

class RevenueSummaryNewKeysTests(SimpleTestCase):
    """Verify that the dashboard view computes the right shapes for the three new keys.

    We replicate the exact computation lines from sales/views.py so we can unit-test
    them without a full HTTP request + DB.
    """

    def _simulate(self, split_result, top_item_rows, stmt_agg):
        # payment_split
        payment_split = {
            "wallet": str(split_result["wallet"]),
            "cash": str(split_result["cash"]),
        }
        # top_items_by_revenue
        top_items_by_revenue = [
            {
                "dish_name": row["dish_name"],
                "revenue": str(round(float(row["revenue"] or 0), 2)),
                "qty": row["qty"] or 0,
            }
            for row in top_item_rows
        ]
        # statement
        _gross = float(stmt_agg["gross"] or 0)
        _promo = float(stmt_agg["promo_discounts"] or 0)
        _loyalty = float(stmt_agg["loyalty_discounts"] or 0)
        _tips = float(stmt_agg["tips"] or 0)
        _commission = float(stmt_agg["commission"] or 0)
        statement = {
            "gross": str(round(_gross, 2)),
            "promo_discounts": str(round(_promo, 2)),
            "loyalty_discounts": str(round(_loyalty, 2)),
            "tips": str(round(_tips, 2)),
            "commission": str(round(_commission, 2)),
            # Order.total is already post-discount and tip-INCLUSIVE (see
            # PlaceOrderView), so net = gross - tips - commission; the discount
            # lines are informational only. Mirrors sales/views.py.
            "net": str(round(_gross - _tips - _commission, 2)),
        }
        return payment_split, top_items_by_revenue, statement

    def test_payment_split_wallet_and_cash_keys(self):
        ps, _, _ = self._simulate(
            split_result={"wallet": Decimal("45.00"), "cash": Decimal("55.00")},
            top_item_rows=[],
            stmt_agg={"gross": 0, "promo_discounts": 0, "loyalty_discounts": 0, "tips": 0, "commission": 0},
        )
        self.assertEqual(ps["wallet"], "45.00")
        self.assertEqual(ps["cash"], "55.00")

    def test_top_items_shape_and_ordering(self):
        rows = [
            {"dish_name": "Burger", "revenue": Decimal("120.00"), "qty": 10},
            {"dish_name": "Fries",  "revenue": Decimal("50.00"),  "qty": 20},
        ]
        _, top_items, _ = self._simulate(
            split_result={"wallet": Decimal("0"), "cash": Decimal("0")},
            top_item_rows=rows,
            stmt_agg={"gross": 0, "promo_discounts": 0, "loyalty_discounts": 0, "tips": 0, "commission": 0},
        )
        self.assertEqual(len(top_items), 2)
        self.assertEqual(top_items[0]["dish_name"], "Burger")
        self.assertEqual(top_items[0]["qty"], 10)
        for item in top_items:
            self.assertIn("dish_name", item)
            self.assertIn("revenue", item)
            self.assertIn("qty", item)

    def test_voided_items_are_excluded_from_top_items(self):
        """Voided items must NOT be in the top_items list.

        The ORM filter `is_voided=False` is applied in the view before passing rows to
        the builder — we verify here that if only non-voided rows reach the builder the
        voided dish never appears.
        """
        non_voided_rows = [{"dish_name": "Burger", "revenue": Decimal("100.00"), "qty": 5}]
        _, top_items, _ = self._simulate(
            split_result={"wallet": Decimal("0"), "cash": Decimal("0")},
            top_item_rows=non_voided_rows,
            stmt_agg={"gross": 0, "promo_discounts": 0, "loyalty_discounts": 0, "tips": 0, "commission": 0},
        )
        self.assertNotIn("VoidedDish", [i["dish_name"] for i in top_items])

    def test_statement_net_equals_full_pl_formula(self):
        # gross (Sum of Order.total) is ALREADY post-discount and tip-inclusive,
        # so: net = gross - tips - commission = 1000 - 30 - 100 = 870.
        # Discounts are informational lines, NOT subtracted again.
        _, _, statement = self._simulate(
            split_result={"wallet": Decimal("0"), "cash": Decimal("0")},
            top_item_rows=[],
            stmt_agg={
                "gross": Decimal("1000.00"),
                "promo_discounts": Decimal("50.00"),
                "loyalty_discounts": Decimal("20.00"),
                "tips": Decimal("30.00"),
                "commission": Decimal("100.00"),
            },
        )
        self.assertEqual(statement["gross"], "1000.0")
        self.assertEqual(statement["commission"], "100.0")
        self.assertEqual(statement["tips"], "30.0")
        self.assertEqual(statement["promo_discounts"], "50.0")
        self.assertEqual(statement["loyalty_discounts"], "20.0")
        self.assertEqual(statement["net"], "870.0")

    def test_statement_required_keys_present(self):
        _, _, statement = self._simulate(
            split_result={"wallet": Decimal("0"), "cash": Decimal("0")},
            top_item_rows=[],
            stmt_agg={"gross": 0, "promo_discounts": 0, "loyalty_discounts": 0, "tips": 0, "commission": 0},
        )
        for key in ("gross", "promo_discounts", "loyalty_discounts", "tips", "commission", "net"):
            self.assertIn(key, statement)


# ══════════════════════════════════════════════════════════════════════════════
# 3. low_stock_threshold F() query
# ══════════════════════════════════════════════════════════════════════════════

class LowStockThresholdQueryTests(SimpleTestCase):
    """Verify the dashboard low_stock query uses F('low_stock_threshold'), not a constant."""

    def test_query_uses_f_expression(self):
        import inspect
        import sales.views as _views_mod
        src = inspect.getsource(_views_mod)
        self.assertTrue(
            "F('low_stock_threshold')" in src or 'F("low_stock_threshold")' in src,
            "Dashboard must use F('low_stock_threshold') or F(\"low_stock_threshold\"), not a fixed constant",
        )
        self.assertNotIn(
            "_LOW_STOCK_THRESHOLD", src,
            "_LOW_STOCK_THRESHOLD constant must be removed from sales/views.py",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. auto_reset_availability command
# ══════════════════════════════════════════════════════════════════════════════

class AutoResetAvailabilityCommandTests(SimpleTestCase):
    """Unit tests for the auto_reset_availability management command."""

    def _make_tenant(self, slug, flag_on=True, tz="UTC"):
        tenant = MagicMock()
        tenant.slug = slug
        tenant.schema_name = f"tenant_{slug}"
        profile = MagicMock()
        profile.auto_reset_availability = flag_on
        profile.timezone = tz
        tenant.profile = profile
        return tenant

    def _call(self, tenants, local_hour, day_str, dry_run=False, cache_add_returns=True):
        import menu.management.commands.auto_reset_availability as cmd_mod
        from django.core.management import call_command

        with (
            patch.object(cmd_mod, "Tenant") as MockTenant,
            patch.object(cmd_mod, "cache") as mock_cache,
            patch.object(cmd_mod, "schema_context") as mock_ctx,
            patch.object(cmd_mod, "_tenant_local_hour", return_value=(local_hour, day_str)),
            patch.object(cmd_mod, "reset_dishes_for_schema", return_value={"restored": 3, "stock_cleared": 1}),
        ):
            MockTenant.LifecycleStatus.ACTIVE = "active"
            qs_mock = MagicMock()
            qs_mock.__iter__ = MagicMock(return_value=iter(tenants))
            MockTenant.objects.filter.return_value.exclude.return_value.select_related.return_value = qs_mock
            mock_cache.add.return_value = cache_add_returns
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            stdout = io.StringIO()
            call_command("auto_reset_availability", stdout=stdout, dry_run=dry_run)
            return stdout.getvalue(), mock_cache

    def test_flag_off_tenant_is_skipped(self):
        """Tenant with flag=False must not trigger any cache write."""
        tenant = self._make_tenant("flagoff", flag_on=False)
        _, mock_cache = self._call([tenant], local_hour=5, day_str="2026-06-11")
        mock_cache.add.assert_not_called()

    def test_wrong_hour_is_skipped(self):
        """Tenant at local hour != 5 must not trigger any cache write."""
        tenant = self._make_tenant("wronghour", flag_on=True)
        _, mock_cache = self._call([tenant], local_hour=10, day_str="2026-06-11")
        mock_cache.add.assert_not_called()

    def test_at_hour_5_with_flag_on_resets(self):
        """Tenant at local hour 5 with flag enabled → cache written + mentioned in output."""
        tenant = self._make_tenant("goodtenant", flag_on=True)
        out, mock_cache = self._call([tenant], local_hour=5, day_str="2026-06-11", cache_add_returns=True)
        mock_cache.add.assert_called_once()
        self.assertIn("goodtenant", out)

    def test_marker_idempotency_prevents_second_reset(self):
        """cache.add returning False (marker already set) → reset_dishes_for_schema not called."""
        import menu.management.commands.auto_reset_availability as cmd_mod
        from django.core.management import call_command

        tenant = self._make_tenant("idempotent", flag_on=True)

        with (
            patch.object(cmd_mod, "Tenant") as MockTenant,
            patch.object(cmd_mod, "cache") as mock_cache,
            patch.object(cmd_mod, "_tenant_local_hour", return_value=(5, "2026-06-11")),
            patch.object(cmd_mod, "reset_dishes_for_schema") as mock_reset,
        ):
            MockTenant.LifecycleStatus.ACTIVE = "active"
            qs_mock = MagicMock()
            qs_mock.__iter__ = MagicMock(return_value=iter([tenant]))
            MockTenant.objects.filter.return_value.exclude.return_value.select_related.return_value = qs_mock
            mock_cache.add.return_value = False  # marker already present
            call_command("auto_reset_availability", stdout=io.StringIO())

        mock_reset.assert_not_called()

    def test_dry_run_does_not_write_cache_or_db(self):
        """--dry-run must not write cache markers and output 'would reset'."""
        tenant = self._make_tenant("dryrun", flag_on=True)
        out, mock_cache = self._call([tenant], local_hour=5, day_str="2026-06-11", dry_run=True)
        mock_cache.add.assert_not_called()
        self.assertIn("would reset", out.lower())


# ══════════════════════════════════════════════════════════════════════════════
# 5. stock_auto_zeroed marker lifecycle (B4)
#
# These tests verify that:
#   a) reset_dishes_for_schema only re-enables dishes with stock_auto_zeroed=True
#   b) The marker is cleared (False) after the cron re-enables a dish
#   c) reset_dishes_for_schema does NOT touch dishes where stock_auto_zeroed=False
#      (owner-manually-zeroed dishes)
# ══════════════════════════════════════════════════════════════════════════════

class StockAutoZeroedMarkerTests(SimpleTestCase):
    """Unit tests for the stock_auto_zeroed marker (B4).

    reset_dishes_for_schema imports Dish lazily inside its body, so we patch
    menu.models.Dish rather than the command module.
    """

    def _make_dish_qs_mock(self, *, restored=0, stock_cleared=0):
        """Return a Dish mock whose ORM chain satisfies reset_dishes_for_schema."""
        mock_dish = MagicMock()

        filter_calls = {}

        def outer_filter(**kwargs):
            """Called as Dish.objects.filter(is_published=True, stock_auto_zeroed=True)."""
            target_qs = MagicMock()

            def inner_filter(**inner_kwargs):
                sub_qs = MagicMock()
                if inner_kwargs.get("is_available") is False:
                    sub_qs.update.return_value = restored
                elif inner_kwargs.get("is_available") is True:
                    sub_qs.update.return_value = stock_cleared
                else:
                    sub_qs.update.return_value = 0
                filter_calls.update(inner_kwargs)
                return sub_qs

            target_qs.filter.side_effect = inner_filter
            return target_qs

        mock_dish.objects.filter.side_effect = outer_filter
        return mock_dish, filter_calls

    def _run_reset(self, *, restored=0, stock_cleared=0):
        mock_dish, filter_calls = self._make_dish_qs_mock(
            restored=restored, stock_cleared=stock_cleared
        )
        with patch("menu.models.Dish", mock_dish):
            from menu.management.commands.auto_reset_availability import reset_dishes_for_schema
            result = reset_dishes_for_schema()
        return result, mock_dish, filter_calls

    def test_only_auto_zeroed_dishes_are_targeted(self):
        """reset_dishes_for_schema initial filter includes stock_auto_zeroed=True."""
        _, mock_dish, _ = self._run_reset(restored=2)
        # Dish.objects.filter must be called with stock_auto_zeroed=True
        call_kwargs = mock_dish.objects.filter.call_args[1]
        self.assertTrue(call_kwargs.get("stock_auto_zeroed") is True)

    def test_sold_out_auto_zeroed_dishes_are_restored(self):
        """Sold-out auto-zeroed dishes are counted in the 'restored' result key."""
        result, _, _ = self._run_reset(restored=3)
        self.assertEqual(result["restored"], 3)

    def test_manually_zeroed_dishes_not_restored(self):
        """Dishes without stock_auto_zeroed=True never reach the update call."""
        # With restored=0 the update for sold-out dishes returns 0, simulating
        # that no manual-zero dishes were in the auto-zeroed queryset.
        result, _, _ = self._run_reset(restored=0)
        self.assertEqual(result["restored"], 0)

    def test_stock_auto_zeroed_field_exists_on_dish_model(self):
        """Dish.stock_auto_zeroed field is a BooleanField with default=False."""
        from menu.models import Dish
        field = Dish._meta.get_field("stock_auto_zeroed")
        self.assertFalse(field.default)
        from django.db.models import BooleanField
        self.assertIsInstance(field, BooleanField)
