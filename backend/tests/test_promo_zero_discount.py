"""
L9 regression: a promo code that takes NOTHING off the order must not be attached to it,
so it never consumes one of the promotion's limited uses (``use_count`` / ``max_uses``).

Example: a ``free_delivery`` code on a PICKUP order computes a 0 discount. It used to be
accepted, attached (``applied_promotion_name``) and counted (``use_count + 1``), burning a
use for nothing. It is now refused with the same ``promo_invalid`` 400 a code below its
minimum order gets (the cart clears the code on that error and shows its localized message).

View-level through APIRequestFactory, all ORM access mocked â€” SimpleTestCase, no DB.
"""
from contextlib import ExitStack
from datetime import datetime, timezone as _tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import PlaceOrderView

_NOW = datetime(2026, 6, 8, 12, 0, tzinfo=_tz.utc)


def _profile():
    p = MagicMock()
    p.timezone = "UTC"
    p.is_menu_published = True
    p.is_menu_temporarily_disabled = False
    p.is_open = True
    p.orders_paused_until = None
    p.busy_extra_minutes = 0
    p.busy_extra_until = None
    p.auto_accept_orders = False
    p.default_prep_minutes = 20
    p.delivery_fee = "0"
    p.lat = None
    p.lng = None
    p.platform_delivery_enabled = False
    p.whatsapp = ""
    p.phone = ""
    p.capabilities = {}
    p.business_hours_schedule = {}
    return p


def _dish(price="40.00"):
    d = MagicMock()
    d.pk = 1
    d.slug = "dish-1"
    d.name = "Dish 1"
    d.price = Decimal(price)
    d.category_id = 10
    d.currency = "MAD"
    d.stock_qty = None
    d.combo_components.all.return_value = []
    d.option_groups.all.return_value = []
    return d


def _staff_user(tenant_id=1):
    # Tenant staff placing a counter order: exempt from the customer wallet-prepay gate.
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.id = 99
    u.pk = 99
    return u


def _promo(promo_type, discount_value="0", max_uses=None):
    return SimpleNamespace(
        pk=5, id=5, name="PROMO", code="PROMO", promo_type=promo_type,
        discount_value=Decimal(discount_value), min_order_amount=Decimal("0"),
        max_uses=max_uses, use_count=0, is_active=True,
    )


def _atomic_ctx():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class CodePromoZeroDiscountTests(SimpleTestCase):
    def setUp(self):
        cache.clear()  # PlaceOrderThrottle counts in the cache; don't inherit other tests' hits

    def _place(self, promo):
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
            stack.enter_context(patch("menu.views._is_promo_active_now", return_value=True))
            tx_mock = stack.enter_context(patch("menu.views.transaction"))
            stack.enter_context(patch("menu.views._generate_order_number", return_value="ORD-PROMO-1"))
            stack.enter_context(patch("menu.views._broadcast_order_change"))

            profile_mock.filter.return_value.first.return_value = _profile()
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [_dish()]
            hh_mock.objects.filter.return_value.prefetch_related.return_value = []
            promo_mock.filter.return_value.order_by.return_value.first.return_value = promo
            created = MagicMock(order_number="ORD-PROMO-1", status="pending", total=Decimal("0"),
                                delivery_fee=Decimal("0"), currency="MAD", estimated_ready_minutes=None,
                                payment_status="unpaid", id=1, pk=1)
            order_mock.create.return_value = created
            orderitem_mock.bulk_create.return_value = []
            tx_mock.atomic.return_value = _atomic_ctx()

            req = APIRequestFactory().post(
                "/api/place-order/",
                {
                    "items": [{"slug": "dish-1", "qty": 1}],
                    "fulfillment_type": "pickup",
                    "promo_code": "promo",
                },
                format="json",
            )
            req.tenant = SimpleNamespace(
                id=1, name="Demo", schema_name="test", slug="test",
                plan=SimpleNamespace(can_checkout=True, can_whatsapp_order=True),
            )
            req.user = _staff_user()
            resp = PlaceOrderView.as_view()(req)
        return resp, promo_mock, order_mock

    def test_free_delivery_code_on_pickup_is_refused_and_not_counted(self):
        resp, promo_mock, order_mock = self._place(_promo("free_delivery"))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data["code"], "promo_invalid")
        # No use consumed and no order placed with a zero-value promo attached.
        promo_mock.filter.return_value.update.assert_not_called()
        order_mock.create.assert_not_called()

    def test_capped_free_delivery_code_on_pickup_does_not_burn_a_use(self):
        # Bounded promo (max_uses set): the conditional use_count increment must not run either.
        resp, promo_mock, order_mock = self._place(_promo("free_delivery", max_uses=3))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data["code"], "promo_invalid")
        promo_mock.filter.return_value.update.assert_not_called()
        order_mock.create.assert_not_called()

    def test_zero_value_fixed_code_is_refused(self):
        resp, promo_mock, order_mock = self._place(_promo("fixed", discount_value="0"))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data["code"], "promo_invalid")
        promo_mock.filter.return_value.update.assert_not_called()

    def test_code_with_a_real_discount_still_applies_and_counts(self):
        # Guard: a code that does take money off is unchanged â€” applied, and one use consumed.
        resp, promo_mock, order_mock = self._place(_promo("percentage", discount_value="10"))
        self.assertEqual(resp.status_code, 201, resp.data)
        order_mock.create.assert_called_once()
        kwargs = order_mock.create.call_args.kwargs
        self.assertEqual(kwargs["promotion_discount"], Decimal("4.00"))  # 10% of 40.00
        self.assertEqual(kwargs["applied_promotion_name"], "PROMO")
        self.assertEqual(kwargs["total"], Decimal("36.00"))
        promo_mock.filter.return_value.update.assert_called_once()
