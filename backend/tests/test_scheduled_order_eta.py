"""
L7 regression: a released scheduled (advance) order must not carry a stale ETA.

Before: PlaceOrderView stamped the busy-mode placement ETA (estimated_ready_minutes) even on a
SCHEDULED order, and release_scheduled_orders never touched it. The order page anchors the
countdown to estimated_ready_at, falling back to created_at + estimated_ready_minutes, so once
the order was released (days after it was placed) the customer saw "Ready any moment now".

After:
  * PlaceOrderView stamps NO placement ETA on a scheduled order (ASAP orders are unchanged).
  * release_scheduled_orders stamps the ETA the way a fresh placement would
    (menu.views._placement_eta_minutes) and anchors it at release time (estimated_ready_at),
    inside the same SCHEDULED -> PENDING conditional-update claim.

All ORM access mocked — SimpleTestCase, no DB.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone as _tz
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.models import Order
from menu.views import PlaceOrderView, _placement_eta_minutes

_NOW = datetime(2026, 6, 8, 12, 0, tzinfo=_tz.utc)


def _busy_profile(*, busy_minutes=15, prep=20):
    """A profile whose kitchen is slammed right now: +busy_minutes on every quote."""
    p = MagicMock()
    p.timezone = "UTC"
    p.is_menu_published = True
    p.is_menu_temporarily_disabled = False
    p.is_open = True
    p.orders_paused_until = None
    p.busy_extra_minutes = busy_minutes
    p.busy_extra_until = timezone.now() + timedelta(hours=1) if busy_minutes else None
    p.auto_accept_orders = False
    p.default_prep_minutes = prep
    p.delivery_fee = "0"
    p.lat = None
    p.lng = None
    p.platform_delivery_enabled = False
    p.whatsapp = ""
    p.phone = ""
    p.capabilities = {}
    p.business_hours_schedule = {}
    return p


class PlacementEtaHelperTests(SimpleTestCase):
    """The shared helper keeps PlaceOrderView's former inline busy/auto-accept ETA rule."""

    def test_busy_kitchen_quotes_prep_plus_bump(self):
        self.assertEqual(_placement_eta_minutes(_busy_profile(busy_minutes=15, prep=20)), 35)

    def test_not_busy_and_not_auto_accepted_has_no_eta(self):
        self.assertIsNone(_placement_eta_minutes(_busy_profile(busy_minutes=0)))

    def test_auto_accept_quotes_prep_even_when_not_busy(self):
        self.assertEqual(_placement_eta_minutes(_busy_profile(busy_minutes=0, prep=25), auto_accept=True), 25)

    def test_no_profile_has_no_eta(self):
        self.assertIsNone(_placement_eta_minutes(None))


# ── PlaceOrderView: no placement ETA on a scheduled order ─────────────────────


def _dish():
    d = MagicMock()
    d.pk = 1
    d.slug = "dish-1"
    d.name = "Dish 1"
    d.price = Decimal("40.00")
    d.category_id = 10
    d.currency = "MAD"
    d.stock_qty = None
    d.combo_components.all.return_value = []
    d.option_groups.all.return_value = []
    return d


def _staff_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.id = 98
    u.pk = 98
    return u


def _atomic_ctx():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class PlaceOrderScheduledEtaTests(SimpleTestCase):
    def setUp(self):
        cache.clear()  # PlaceOrderThrottle counts in the cache

    def _create_kwargs(self, *, scheduled):
        """Place one pickup line as tenant staff with the kitchen busy; return Order.create kwargs."""
        when = timezone.now() + timedelta(days=2)
        with ExitStack() as stack:
            stack.enter_context(patch("menu.models.RecipeLine"))
            promo_mock = stack.enter_context(patch("menu.views.Promotion.objects"))
            orderitem_mock = stack.enter_context(patch("menu.views.OrderItem.objects"))
            order_mock = stack.enter_context(patch("menu.views.Order.objects"))
            stack.enter_context(patch("menu.views.DishOption.objects"))
            dish_mock = stack.enter_context(patch("menu.views.Dish.objects"))
            profile_mock = stack.enter_context(patch("menu.views.Profile.objects"))
            hh_mock = stack.enter_context(patch("menu.pricing.HappyHour"))
            stack.enter_context(patch("menu.views._profile_now", return_value=_NOW))
            stack.enter_context(patch("menu.views.is_closure_date", return_value=False))
            stack.enter_context(patch(
                "menu.views._validate_scheduled_for", return_value=(when if scheduled else None, None),
            ))
            tx_mock = stack.enter_context(patch("menu.views.transaction"))
            stack.enter_context(patch("menu.views._generate_order_number", return_value="ORD-SCHED-1"))
            stack.enter_context(patch("menu.views._broadcast_order_change"))

            profile_mock.filter.return_value.first.return_value = _busy_profile(busy_minutes=15, prep=20)
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [_dish()]
            hh_mock.objects.filter.return_value.prefetch_related.return_value = []
            promo_mock.filter.return_value = []
            order_mock.create.return_value = MagicMock(
                order_number="ORD-SCHED-1", status="scheduled", total=Decimal("40.00"),
                delivery_fee=Decimal("0"), currency="MAD", estimated_ready_minutes=None,
                payment_status="unpaid", id=1, pk=1, scheduled_for=when if scheduled else None,
            )
            orderitem_mock.bulk_create.return_value = []
            tx_mock.atomic.return_value = _atomic_ctx()

            body = {"items": [{"slug": "dish-1", "qty": 1}], "fulfillment_type": "pickup"}
            if scheduled:
                body["scheduled_for"] = when.isoformat()
            req = APIRequestFactory().post("/api/place-order/", body, format="json")
            req.tenant = SimpleNamespace(
                id=1, name="Demo", schema_name="test", slug="test",
                plan=SimpleNamespace(can_checkout=True, can_whatsapp_order=True),
            )
            req.user = _staff_user()
            resp = PlaceOrderView.as_view()(req)

        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))
        order_mock.create.assert_called_once()
        return order_mock.create.call_args.kwargs

    def test_scheduled_order_gets_no_placement_eta_even_when_busy(self):
        kwargs = self._create_kwargs(scheduled=True)
        self.assertEqual(kwargs["status"], Order.Status.SCHEDULED)
        self.assertIsNone(kwargs["estimated_ready_minutes"])

    def test_asap_order_still_gets_the_busy_mode_eta(self):
        # Guard: a normal ASAP order keeps the busy-mode quote (20 prep + 15 bump).
        kwargs = self._create_kwargs(scheduled=False)
        self.assertEqual(kwargs["status"], Order.Status.PENDING)
        self.assertEqual(kwargs["estimated_ready_minutes"], 35)


# ── release_scheduled_orders: fresh ETA stamped inside the claim ──────────────


class ReleaseScheduledOrdersEtaTests(SimpleTestCase):
    def _run_release(self, profile, *, claimed=1):
        """Run the command over one tenant with one due SCHEDULED order.

        Returns (order_objects_mock, in_memory_order)."""
        from menu.management.commands.release_scheduled_orders import Command

        tenant = SimpleNamespace(id=1, slug="demo", name="Demo", schema_name="demo", profile=profile)
        order = SimpleNamespace(
            pk=7, order_number="ORD-REL-1", status=Order.Status.SCHEDULED,
            scheduled_for=timezone.now() + timedelta(minutes=30),
            fulfillment_type=Order.FulfillmentType.PICKUP,
            customer_name="", total=Decimal("40.00"), currency="MAD",
            # A stale placement-time ETA from older code / the marketplace checkout.
            estimated_ready_minutes=35, estimated_ready_at=None,
        )
        mod = "menu.management.commands.release_scheduled_orders"
        with ExitStack() as stack:
            tenant_cls = stack.enter_context(patch(f"{mod}.Tenant"))
            stack.enter_context(patch(f"{mod}.schema_context"))
            order_cls = stack.enter_context(patch("menu.models.Order"))
            stack.enter_context(patch("menu.views._broadcast_order_change"))
            stack.enter_context(patch("menu.views._notify_restaurant_new_order"))
            stack.enter_context(patch("menu.push.push_new_order"))

            tenant_cls.objects.filter.return_value.exclude.return_value.select_related.return_value = [tenant]
            order_cls.Status = Order.Status
            order_cls.FulfillmentType = Order.FulfillmentType
            order_cls.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [order]
            order_cls.objects.filter.return_value.update.return_value = claimed

            Command(stdout=StringIO(), stderr=StringIO()).handle(dry_run=False)
        return order_cls.objects, order

    def test_release_stamps_a_fresh_eta_anchored_at_release_when_busy(self):
        objects, order = self._run_release(_busy_profile(busy_minutes=15, prep=20))
        # The claim stays a single conditional SCHEDULED -> PENDING update...
        objects.filter.assert_any_call(pk=7, status=Order.Status.SCHEDULED)
        objects.filter.return_value.update.assert_called_once()
        kw = objects.filter.return_value.update.call_args.kwargs
        self.assertEqual(kw["status"], Order.Status.PENDING)
        # ...that now also stamps the fresh quote, anchored at release time (not created_at).
        self.assertEqual(kw["estimated_ready_minutes"], 35)
        self.assertEqual(kw["estimated_ready_at"] - kw["status_updated_at"], timedelta(minutes=35))
        # The in-memory instance used for the broadcast reflects it too.
        self.assertEqual(order.estimated_ready_minutes, 35)
        self.assertEqual(order.estimated_ready_at, kw["estimated_ready_at"])

    def test_release_clears_a_stale_placement_eta_when_not_busy(self):
        # A fresh non-busy placement has no ETA until the owner confirms — so must a release.
        objects, order = self._run_release(_busy_profile(busy_minutes=0))
        kw = objects.filter.return_value.update.call_args.kwargs
        self.assertIsNone(kw["estimated_ready_minutes"])
        self.assertIsNone(kw["estimated_ready_at"])
        self.assertIsNone(order.estimated_ready_minutes)

    def test_lost_claim_leaves_the_order_untouched(self):
        # Concurrency guard intact: another run already released it (0 rows) -> no side effects.
        objects, order = self._run_release(_busy_profile(busy_minutes=15), claimed=0)
        self.assertEqual(order.status, Order.Status.SCHEDULED)
        self.assertEqual(order.estimated_ready_minutes, 35)
