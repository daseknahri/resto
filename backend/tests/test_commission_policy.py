"""Shared marketplace-commission policy — menu.commission.

Pins the two policy facts that used to live (and drift) inline at three call sites:

  * COMMISSIONABLE_STATUSES — which order statuses have EARNED commission. Proven
    here to (a) match the live Order.Status enum, (b) include out_for_delivery (the
    bug: the old analytics list dropped it), (c) exclude pending/scheduled/cancelled,
    and (d) be the *identical object* used by both the owner statement (menu.views)
    and owner analytics (sales.views) — so the two can never disagree again.
  * commissionable_food_base — the POST-discount food base commission is charged on.

Pure SimpleTestCase / unit level — no DB, no schema switch.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

import menu.commission
import menu.views
import sales.views
from menu.commission import COMMISSIONABLE_STATUSES, commissionable_food_base


class CommissionableFoodBaseTests(SimpleTestCase):
    """The base is food_subtotal minus BOTH discounts, floored at zero, and never
    includes the delivery fee or tip (the caller passes only the food figures)."""

    def test_no_discount_base_is_food_subtotal(self):
        self.assertEqual(
            commissionable_food_base(Decimal("20.00"), Decimal("0"), Decimal("0")),
            Decimal("20.00"),
        )

    def test_promo_discount_is_subtracted(self):
        # 20.00 food − 5.00 promo → 15.00 base.
        self.assertEqual(
            commissionable_food_base(Decimal("20.00"), Decimal("5.00"), Decimal("0")),
            Decimal("15.00"),
        )

    def test_both_discounts_are_subtracted(self):
        # 20.00 food − 5.00 promo − 3.00 loyalty → 12.00 base.
        self.assertEqual(
            commissionable_food_base(Decimal("20.00"), Decimal("5.00"), Decimal("3.00")),
            Decimal("12.00"),
        )

    def test_base_floors_at_zero_when_discounts_exceed_food(self):
        # A discount larger than the food subtotal must never yield a negative
        # commission base (which would become a negative commission = paying the
        # restaurant to take the order).
        self.assertEqual(
            commissionable_food_base(Decimal("10.00"), Decimal("12.00"), Decimal("0")),
            Decimal("0"),
        )


class CommissionableStatusSetTests(SimpleTestCase):
    def test_matches_live_order_status_enum(self):
        """Drift guard: the raw-string constant equals the live Order.Status values,
        in order — CONFIRMED, PREPARING, READY, OUT_FOR_DELIVERY, COMPLETED."""
        from menu.models import Order

        self.assertEqual(
            COMMISSIONABLE_STATUSES,
            [
                Order.Status.CONFIRMED,
                Order.Status.PREPARING,
                Order.Status.READY,
                Order.Status.OUT_FOR_DELIVERY,
                Order.Status.COMPLETED,
            ],
        )

    def test_includes_out_for_delivery(self):
        """The bug fix: an order in flight to the customer is committed revenue and
        MUST be billable (the old analytics list silently dropped it)."""
        from menu.models import Order

        self.assertIn(Order.Status.OUT_FOR_DELIVERY, COMMISSIONABLE_STATUSES)

    def test_excludes_not_yet_earned_and_refunded_statuses(self):
        """PENDING / SCHEDULED can still cancel before the kitchen commits, and a
        CANCELLED order was refunded — none of them have earned commission."""
        from menu.models import Order

        for s in (Order.Status.PENDING, Order.Status.SCHEDULED, Order.Status.CANCELLED):
            self.assertNotIn(s, COMMISSIONABLE_STATUSES)

    def test_statement_and_analytics_use_the_identical_object(self):
        """The whole point of the shared module: the owner commission statement
        (menu.views) and owner analytics (sales.views) reference the SAME list object,
        so the status set they bill on can never drift apart."""
        self.assertIs(menu.views.COMMISSIONABLE_STATUSES, menu.commission.COMMISSIONABLE_STATUSES)
        self.assertIs(sales.views.COMMISSIONABLE_STATUSES, menu.commission.COMMISSIONABLE_STATUSES)


class RecomputeMarketplaceCommissionTests(SimpleTestCase):
    """D-02: _recompute_marketplace_commission (menu.views) — the shared
    void/comp recompute — bills on the DECIDED post-discount basis:
    commissionable_food_base(remaining food, promo, loyalty) × snapshotted
    rate, floored at zero. Direct orders and zero-rate orders are untouched."""

    def _order(self, *, source="marketplace", rate="0.15", promo="0",
               loyalty="0", amount="0.00"):
        return SimpleNamespace(
            source=source,
            commission_rate_applied=Decimal(rate),
            promotion_discount=Decimal(promo),
            loyalty_discount=Decimal(loyalty),
            commission_amount=Decimal(amount),
        )

    def test_post_discount_base_nets_out_promo_and_loyalty(self):
        # Remaining food 20.00, promo 5.00, loyalty 3.00 → base 12.00.
        o = self._order(promo="5.00", loyalty="3.00", amount="6.00")
        self.assertTrue(
            menu.views._recompute_marketplace_commission(o, Decimal("20.00"))
        )
        self.assertEqual(o.commission_amount, Decimal("1.80"))

    def test_no_discount_base_is_remaining_food(self):
        o = self._order(amount="6.00")
        self.assertTrue(
            menu.views._recompute_marketplace_commission(o, Decimal("20.00"))
        )
        self.assertEqual(o.commission_amount, Decimal("3.00"))

    def test_base_floors_at_zero_when_discounts_exceed_remaining_food(self):
        o = self._order(promo="5.00", amount="6.00")
        self.assertTrue(
            menu.views._recompute_marketplace_commission(o, Decimal("4.00"))
        )
        self.assertEqual(o.commission_amount, Decimal("0.00"))

    def test_direct_order_untouched(self):
        from menu.models import Order

        o = self._order(source=Order.Source.DIRECT, amount="6.00")
        self.assertFalse(
            menu.views._recompute_marketplace_commission(o, Decimal("20.00"))
        )
        self.assertEqual(o.commission_amount, Decimal("6.00"))

    def test_zero_rate_untouched(self):
        o = self._order(rate="0.00", amount="6.00")
        self.assertFalse(
            menu.views._recompute_marketplace_commission(o, Decimal("20.00"))
        )
        self.assertEqual(o.commission_amount, Decimal("6.00"))
