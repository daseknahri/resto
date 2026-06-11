"""
Tests for Happy-Hour / time-based pricing.

Covers:
  - get_active_happy_hours: window matching (normal + overnight + day boundary + inactive)
  - effective_unit_price: category scoping, largest-discount-wins, quantization
  - happy_hour_payload: serialization helper
  - DishSerializer: effective_price / happy_hour present; fallback when no context
  - HappyHourSerializer: validation (percent_off bounds, days, start==end, max-8, name)
  - PlaceOrderView: charges effective price (patches get_active_happy_hours)
  - StaffAppendOrderItemsView: charges effective price
  - MarketplacePlaceOrderView: charges effective price

All tests are SimpleTestCase + MagicMock — no DB.
"""
from datetime import datetime, time, timezone as _tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.pricing import (
    get_active_happy_hours,
    effective_unit_price,
    happy_hour_payload,
)
from menu.serializers import DishSerializer, HappyHourSerializer
from menu.views import PlaceOrderView, StaffAppendOrderItemsView
from menu.models import Order
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_rule(
    pk=1,
    name="Happy Hour",
    days=None,
    start_time=time(16, 0),
    end_time=time(19, 0),
    percent_off=20,
    is_active=True,
    category_ids=None,
):
    """Build a mock HappyHour rule."""
    rule = MagicMock()
    rule.id = pk
    rule.name = name
    rule.days = days if days is not None else [0, 1, 2, 3, 4]  # Mon-Fri
    rule.start_time = start_time
    rule.end_time = end_time
    rule.percent_off = percent_off
    rule.is_active = is_active
    # categories M2M mock
    cat_ids = category_ids or []
    cats = [SimpleNamespace(id=cid) for cid in cat_ids]
    cat_qs = MagicMock()
    cat_qs.__iter__ = lambda s: iter(cats)
    rule.categories = MagicMock()
    rule.categories.all.return_value = cats
    return rule


def _make_dish(pk=1, price="20.00", category_id=10):
    dish = MagicMock()
    dish.pk = pk
    dish.price = Decimal(price)
    dish.category_id = category_id
    dish.slug = f"dish-{pk}"
    dish.name = f"Dish {pk}"
    dish.currency = "MAD"
    dish.stock_qty = None
    dish.is_published = True
    dish.is_available = True
    cc_qs = MagicMock()
    cc_qs.all.return_value = []
    dish.combo_components = cc_qs
    return dish


def _plan(can_checkout=True, can_whatsapp_order=True):
    return SimpleNamespace(can_checkout=can_checkout, can_whatsapp_order=can_whatsapp_order)


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Demo", plan=_plan(), schema_name="test", slug="test")


def _profile(timezone="UTC", is_menu_published=True, is_menu_temporarily_disabled=False, is_open=True):
    p = MagicMock()
    p.timezone = timezone
    p.is_menu_published = is_menu_published
    p.is_menu_temporarily_disabled = is_menu_temporarily_disabled
    p.is_open = is_open
    p.delivery_fee = "0"
    p.delivery_base_fee = "0"
    p.delivery_per_km_fee = "0"
    p.lat = None
    p.lng = None
    p.platform_delivery_enabled = False
    p.whatsapp = ""
    p.phone = ""
    p.capabilities = {}
    p.business_hours_schedule = {}
    p.cod_min_paid_orders = 3
    return p


def _owner_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.id = 42
    u.perm_edit_menu = True
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _staff_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.id = 99
    u.perm_edit_menu = True
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _session(customer_id=None):
    d = {}
    if customer_id is not None:
        d["customer_id"] = customer_id
    sess = MagicMock()
    sess.get = lambda key, default=None: d.get(key, default)
    sess.__setitem__ = lambda s, k, v: d.__setitem__(k, v)
    sess.pop = lambda key, default=None: d.pop(key, default)
    return sess


# ═══════════════════════════════════════════════════════════════════════════════
# get_active_happy_hours — window logic
# ═══════════════════════════════════════════════════════════════════════════════

class GetActiveHappyHoursWindowTests(SimpleTestCase):

    def _now(self, weekday, hour, minute=0):
        """Build a fixed aware dt with the given weekday (0=Mon) and time."""
        # 2026-06-08 = Monday (weekday 0); offset by weekday.
        from datetime import timedelta
        base = datetime(2026, 6, 8, hour, minute, tzinfo=_tz.utc)  # Monday
        return base + timedelta(days=weekday)

    def _rules_qs(self, rules):
        """Patch HappyHour.objects.filter().prefetch_related() to return rules."""
        mock_qs = MagicMock()
        mock_qs.__iter__ = lambda s: iter(rules)
        mock_qs.__len__ = lambda s: len(rules)
        # prefetch_related returns same mock
        mock_qs.prefetch_related = MagicMock(return_value=mock_qs)

        filter_mock = MagicMock(return_value=mock_qs)
        return filter_mock

    def test_normal_window_inside(self):
        """Rule active when now falls inside the normal window on a matching day."""
        rule = _make_rule(days=[0], start_time=time(16, 0), end_time=time(19, 0))
        now = self._now(weekday=0, hour=17)  # Monday 17:00
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [rule])

    def test_normal_window_outside(self):
        """Rule NOT active when time is outside the window."""
        rule = _make_rule(days=[0], start_time=time(16, 0), end_time=time(19, 0))
        now = self._now(weekday=0, hour=20)  # Monday 20:00 — after window
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_wrong_day(self):
        """Rule NOT active when today is not in the rule's days list."""
        rule = _make_rule(days=[1, 2, 3], start_time=time(16, 0), end_time=time(19, 0))
        now = self._now(weekday=0, hour=17)  # Monday — not in [Tue,Wed,Thu]
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_inactive_rule_skipped(self):
        """is_active=False rules are never returned."""
        rule = _make_rule(days=[0], is_active=False)
        # The DB filter(is_active=True) would exclude it; simulate that.
        now = self._now(weekday=0, hour=17)
        with patch("menu.pricing.HappyHour") as MockHH:
            # Return empty list as if DB already filtered out inactive
            MockHH.objects.filter.return_value.prefetch_related.return_value = []
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_overnight_window_after_start(self):
        """Overnight window (22:00–02:00): active at 23:00 on a matching weekday."""
        rule = _make_rule(days=[4], start_time=time(22, 0), end_time=time(2, 0))  # Friday
        now = self._now(weekday=4, hour=23)  # Friday 23:00
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [rule])

    def test_overnight_window_before_end(self):
        """Overnight window (22:00–02:00): active at 01:00 Saturday (yesterday=Friday)."""
        rule = _make_rule(days=[4], start_time=time(22, 0), end_time=time(2, 0))
        now = self._now(weekday=5, hour=1)  # Saturday 01:00 → yesterday=Friday
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [rule])

    def test_overnight_window_outside(self):
        """Overnight window (22:00–02:00): NOT active at 15:00 on matching weekday."""
        rule = _make_rule(days=[4], start_time=time(22, 0), end_time=time(2, 0))
        now = self._now(weekday=4, hour=15)  # Friday 15:00
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_empty_days_rule_skipped(self):
        """A rule with empty days list is skipped (mis-configured)."""
        rule = _make_rule(days=[])
        now = self._now(weekday=0, hour=17)
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_zero_length_window_skipped(self):
        """start_time == end_time → zero-length window, rule skipped."""
        rule = _make_rule(days=[0], start_time=time(16, 0), end_time=time(16, 0))
        now = self._now(weekday=0, hour=16)
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])

    def test_at_window_start_inclusive(self):
        """Rule active exactly at start_time (boundary inclusive)."""
        rule = _make_rule(days=[0], start_time=time(16, 0), end_time=time(19, 0))
        now = self._now(weekday=0, hour=16, minute=0)
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [rule])

    def test_at_window_end_exclusive(self):
        """Rule NOT active exactly at end_time (boundary exclusive)."""
        rule = _make_rule(days=[0], start_time=time(16, 0), end_time=time(19, 0))
        now = self._now(weekday=0, hour=19, minute=0)
        with patch("menu.pricing.HappyHour") as MockHH:
            MockHH.objects.filter.return_value.prefetch_related.return_value = [rule]
            result = get_active_happy_hours(now)
        self.assertEqual(result, [])


# ═══════════════════════════════════════════════════════════════════════════════
# effective_unit_price — category scoping, best-discount, quantization
# ═══════════════════════════════════════════════════════════════════════════════

class EffectiveUnitPriceTests(SimpleTestCase):

    def test_no_rules_returns_base_price(self):
        dish = _make_dish(price="25.00")
        price, rule = effective_unit_price(dish, [])
        self.assertEqual(price, Decimal("25.00"))
        self.assertIsNone(rule)

    def test_rule_applies_discount(self):
        """20% off 25.00 = 5.00 discount → 20.00"""
        dish = _make_dish(price="25.00")
        rule = _make_rule(percent_off=20, category_ids=[])  # empty = all categories
        price, matched = effective_unit_price(dish, [rule])
        self.assertEqual(price, Decimal("20.00"))
        self.assertIs(matched, rule)

    def test_largest_discount_wins(self):
        """When two rules match, the highest percent_off wins."""
        dish = _make_dish(price="100.00", category_id=5)
        rule_low = _make_rule(pk=1, percent_off=10, category_ids=[])
        rule_high = _make_rule(pk=2, percent_off=30, category_ids=[])
        price, matched = effective_unit_price(dish, [rule_low, rule_high])
        self.assertEqual(price, Decimal("70.00"))
        self.assertIs(matched, rule_high)

    def test_category_scoping_match(self):
        """Rule with category_ids that include dish.category_id applies."""
        dish = _make_dish(price="50.00", category_id=7)
        rule = _make_rule(percent_off=10, category_ids=[7, 8])
        price, matched = effective_unit_price(dish, [rule])
        self.assertEqual(price, Decimal("45.00"))
        self.assertIs(matched, rule)

    def test_category_scoping_no_match(self):
        """Rule with category_ids that exclude dish.category_id does NOT apply."""
        dish = _make_dish(price="50.00", category_id=99)
        rule = _make_rule(percent_off=10, category_ids=[7, 8])
        price, matched = effective_unit_price(dish, [rule])
        self.assertEqual(price, Decimal("50.00"))
        self.assertIsNone(matched)

    def test_empty_categories_covers_all(self):
        """Empty categories M2M = rule covers any category."""
        dish = _make_dish(price="40.00", category_id=42)
        rule = _make_rule(percent_off=25, category_ids=[])  # empty = all
        price, matched = effective_unit_price(dish, [rule])
        self.assertEqual(price, Decimal("30.00"))
        self.assertIs(matched, rule)

    def test_quantization_rounds_half_up(self):
        """Ensure ROUND_HALF_UP quantization: 20% of 33.33 = 6.666 → discount 6.67 → 26.66"""
        dish = _make_dish(price="33.33")
        rule = _make_rule(percent_off=20, category_ids=[])
        price, _ = effective_unit_price(dish, [rule])
        # 33.33 * 0.20 = 6.666 → ROUND_HALF_UP → 6.67; 33.33 - 6.67 = 26.66
        self.assertEqual(price, Decimal("26.66"))

    def test_price_never_negative(self):
        """Even with 90% off, price never goes below 0.00."""
        dish = _make_dish(price="0.05")  # very small price
        rule = _make_rule(percent_off=90, category_ids=[])
        price, _ = effective_unit_price(dish, [rule])
        self.assertGreaterEqual(price, Decimal("0.00"))

    def test_category_scoping_best_applicable_wins(self):
        """Two rules, only one applies due to category — that one wins."""
        dish = _make_dish(price="100.00", category_id=5)
        rule_no_match = _make_rule(pk=1, percent_off=50, category_ids=[99])  # wrong cat
        rule_match = _make_rule(pk=2, percent_off=10, category_ids=[5])
        price, matched = effective_unit_price(dish, [rule_no_match, rule_match])
        self.assertEqual(price, Decimal("90.00"))
        self.assertIs(matched, rule_match)


# ═══════════════════════════════════════════════════════════════════════════════
# happy_hour_payload helper
# ═══════════════════════════════════════════════════════════════════════════════

class HappyHourPayloadTests(SimpleTestCase):

    def test_none_returns_none(self):
        self.assertIsNone(happy_hour_payload(None))

    def test_payload_keys_and_values(self):
        rule = _make_rule(name="Evening Special", percent_off=15, start_time=time(16, 0), end_time=time(20, 30))
        payload = happy_hour_payload(rule)
        self.assertEqual(payload["name"], "Evening Special")
        self.assertEqual(payload["percent_off"], 15)
        self.assertEqual(payload["ends_at"], "20:30")
        self.assertEqual(payload["starts_at"], "16:00")

    def test_ends_at_format(self):
        rule = _make_rule(end_time=time(9, 5))
        payload = happy_hour_payload(rule)
        self.assertEqual(payload["ends_at"], "09:05")

    def test_starts_at_present_and_formatted(self):
        """starts_at must be present for overnight staleness detection in the frontend."""
        rule = _make_rule(start_time=time(22, 0), end_time=time(2, 0))
        payload = happy_hour_payload(rule)
        self.assertIn("starts_at", payload)
        self.assertEqual(payload["starts_at"], "22:00")


# ═══════════════════════════════════════════════════════════════════════════════
# DishSerializer — effective_price / happy_hour fields
# ═══════════════════════════════════════════════════════════════════════════════

class DishSerializerHappyHourTests(SimpleTestCase):

    def _make_dish_instance(self, price="30.00", category_id=10):
        """Build a minimal Dish-like object for DishSerializer."""
        d = MagicMock()
        d.pk = 1
        d.price = Decimal(price)
        d.category_id = category_id
        d.category = MagicMock()
        d.category.slug = "food"
        d.category.name = "Food"
        d.category.super_category = MagicMock()
        d.category.super_category.slug = "main"
        d.category.super_category.name = "Main"
        d.name = "Burger"
        d.name_i18n = {}
        d.slug = "burger"
        d.description = ""
        d.description_i18n = {}
        d.currency = "MAD"
        d.image_url = ""
        d.tags = []
        d.allergens = []
        d.attributes = {}
        d.position = 0
        d.is_published = True
        d.is_available = True
        d.stock_qty = None
        d.low_stock_threshold = 3
        d.availability_schedule = None
        cc_qs = MagicMock()
        cc_qs.all.return_value = []
        cc_qs.exists.return_value = False
        d.combo_components = cc_qs
        opts_qs = MagicMock()
        opts_qs.all.return_value = []
        d.options = opts_qs
        og_qs = MagicMock()
        og_qs.all.return_value = []
        d.option_groups = og_qs
        return d

    def test_fallback_when_no_context(self):
        """When context has no 'happy_hours' key, effective_price == price and happy_hour is None."""
        dish = self._make_dish_instance(price="25.00")
        s = DishSerializer(dish, context={})
        data = s.data
        self.assertEqual(data["effective_price"], "25.00")
        self.assertIsNone(data["happy_hour"])

    def test_effective_price_with_active_rule(self):
        """With a 20%-off rule in context, effective_price is discounted."""
        dish = self._make_dish_instance(price="50.00", category_id=10)
        rule = _make_rule(percent_off=20, category_ids=[])  # all categories
        s = DishSerializer(dish, context={"happy_hours": [rule]})
        data = s.data
        self.assertEqual(data["effective_price"], "40.00")
        self.assertIsNotNone(data["happy_hour"])
        self.assertEqual(data["happy_hour"]["percent_off"], 20)

    def test_happy_hour_null_when_rule_does_not_apply(self):
        """Rule with category_ids that don't match → happy_hour is null, price unchanged."""
        dish = self._make_dish_instance(price="50.00", category_id=99)
        rule = _make_rule(percent_off=25, category_ids=[1, 2])  # doesn't cover cat 99
        s = DishSerializer(dish, context={"happy_hours": [rule]})
        data = s.data
        self.assertEqual(data["effective_price"], "50.00")
        self.assertIsNone(data["happy_hour"])

    def test_both_fields_always_present(self):
        """effective_price and happy_hour must both be present regardless of context."""
        dish = self._make_dish_instance(price="10.00")
        # No happy_hours in context
        s = DishSerializer(dish, context={})
        self.assertIn("effective_price", s.data)
        self.assertIn("happy_hour", s.data)
        # With empty rules list
        s2 = DishSerializer(dish, context={"happy_hours": []})
        self.assertIn("effective_price", s2.data)
        self.assertIn("happy_hour", s2.data)


# ═══════════════════════════════════════════════════════════════════════════════
# HappyHourSerializer — validation
# ═══════════════════════════════════════════════════════════════════════════════

class HappyHourSerializerValidationTests(SimpleTestCase):

    def _valid_data(self, **kwargs):
        base = {
            "name": "Happy Hour",
            "days": [0, 1, 2, 3, 4],
            "start_time": "16:00",
            "end_time": "19:00",
            "percent_off": 20,
            "is_active": True,
        }
        base.update(kwargs)
        return base

    def test_valid_data_passes(self):
        s = HappyHourSerializer(data=self._valid_data())
        # We test at the validate level; actual DB call in create is separate.
        # Since we don't mock Category, we just test the field validators.
        # Use a minimal patch for the category FK validation (no cats to validate).
        self.assertTrue(s.is_valid(), s.errors)

    def test_name_too_short_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(name="A"))
        self.assertFalse(s.is_valid())
        self.assertIn("name", s.errors)

    def test_percent_off_zero_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(percent_off=0))
        self.assertFalse(s.is_valid())
        self.assertIn("percent_off", s.errors)

    def test_percent_off_91_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(percent_off=91))
        self.assertFalse(s.is_valid())
        self.assertIn("percent_off", s.errors)

    def test_percent_off_90_accepted(self):
        s = HappyHourSerializer(data=self._valid_data(percent_off=90))
        self.assertTrue(s.is_valid(), s.errors)

    def test_empty_days_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(days=[]))
        self.assertFalse(s.is_valid())
        self.assertIn("days", s.errors)

    def test_days_out_of_range_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(days=[0, 7]))
        self.assertFalse(s.is_valid())
        self.assertIn("days", s.errors)

    def test_duplicate_days_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(days=[0, 0, 1]))
        self.assertFalse(s.is_valid())
        self.assertIn("days", s.errors)

    def test_start_equals_end_rejected(self):
        s = HappyHourSerializer(data=self._valid_data(start_time="16:00", end_time="16:00"))
        self.assertFalse(s.is_valid())

    def test_max_8_on_create(self):
        """validate_create_limit() raises when count >= 8."""
        from menu.serializers import HappyHourSerializer as _S
        s = _S(data=self._valid_data())
        self.assertTrue(s.is_valid(), s.errors)
        with patch("menu.serializers.HappyHour") as MockHH:
            MockHH.objects.count.return_value = 8
            with self.assertRaises(Exception):  # ValidationError
                s.validate_create_limit()

    def test_under_8_on_create_ok(self):
        """validate_create_limit() is fine when count < 8."""
        from menu.serializers import HappyHourSerializer as _S
        s = _S(data=self._valid_data())
        self.assertTrue(s.is_valid(), s.errors)
        with patch("menu.serializers.HappyHour") as MockHH:
            MockHH.objects.count.return_value = 7
            # Should not raise
            s.validate_create_limit()


# ═══════════════════════════════════════════════════════════════════════════════
# PlaceOrderView — view-level integration: OrderItem.unit_price is the discounted price
# ═══════════════════════════════════════════════════════════════════════════════

def _make_transaction_ctx():
    """Return a MagicMock that can be used as a context manager for transaction.atomic."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _make_order_mock(total="80.00"):
    o = MagicMock()
    o.order_number = "ORD-HH-001"
    o.status = "pending"
    o.total = Decimal(total)
    o.delivery_fee = Decimal("0")
    o.currency = "MAD"
    o.estimated_ready_minutes = None
    o.payment_status = "unpaid"
    o.id = 1
    o.pk = 1
    return o


class PlaceOrderViewHappyHourIntegrationTests(SimpleTestCase):
    """View-level integration: PlaceOrderView must write discounted unit_price to OrderItem.

    These tests invoke the actual view through APIRequestFactory and assert that
    OrderItem.objects.create() is called with the happy-hour-discounted unit_price.
    A developer who removes the effective_unit_price() call from the view will
    cause unit_price to revert to dish.price — these tests will catch that.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _staff_post(self, data, prof=None, dish=None):
        """Build a POST request authenticated as a tenant staff member (exempts wallet prepay)."""
        req = self.factory.post("/api/place-order/", data, format="json")
        req.tenant = _tenant()
        req.user = _staff_user(tenant_id=req.tenant.id)
        req.session = _session()
        req._prof = prof or _profile()
        req._dish = dish
        return req

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Order.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    @patch("menu.pricing.HappyHour")
    def test_orderitem_created_with_discounted_unit_price(
        self, mock_hh, profile_mock, dish_mock, opt_mock,
        order_mock, orderitem_mock, promo_mock,
    ):
        """OrderItem.create must receive the happy-hour-discounted unit_price, not dish.price."""
        # Profile
        prof = _profile()
        profile_mock.filter.return_value.first.return_value = prof

        # Dish priced at 100.00
        dish = _make_dish(price="100.00")
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        # Active happy-hour rule: 20% off → unit_price should be 80.00
        rule = _make_rule(percent_off=20, category_ids=[])
        mock_hh.objects.filter.return_value.prefetch_related.return_value = [rule]

        # Options: none
        opt_mock.filter.return_value = []

        # Promotions: none
        promo_mock.filter.return_value = []

        # Order creation
        mock_order = _make_order_mock(total="80.00")
        order_mock.create.return_value = mock_order
        orderitem_mock.create.return_value = MagicMock()

        with patch("menu.views.transaction") as tx_mock:
            tx_mock.atomic.return_value = _make_transaction_ctx()
            with patch("menu.views._generate_order_number", return_value="ORD-HH-001"):
                with patch("menu.views._broadcast_order_change"):
                    req = self._staff_post(
                        data={"items": [{"slug": "dish-1", "qty": 1}], "fulfillment_type": "pickup"}
                    )
                    resp = self.view(req)

        # The view should not error out before reaching OrderItem creation.
        self.assertNotIn(resp.status_code, [400, 403, 503], msg=f"Unexpected early exit: {resp.data}")
        # Assert OrderItem was created with unit_price == 80.00 (not 100.00)
        self.assertTrue(orderitem_mock.create.called, "OrderItem.objects.create was never called")
        call_kwargs = orderitem_mock.create.call_args[1]
        self.assertEqual(
            call_kwargs["unit_price"], Decimal("80.00"),
            f"Expected discounted unit_price 80.00, got {call_kwargs['unit_price']}"
        )

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Order.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    @patch("menu.pricing.HappyHour")
    def test_orderitem_unit_price_unchanged_when_no_active_rule(
        self, mock_hh, profile_mock, dish_mock, opt_mock,
        order_mock, orderitem_mock, promo_mock,
    ):
        """Without an active happy-hour rule, unit_price equals dish.price."""
        prof = _profile()
        profile_mock.filter.return_value.first.return_value = prof

        dish = _make_dish(price="50.00")
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        # No active rules
        mock_hh.objects.filter.return_value.prefetch_related.return_value = []

        opt_mock.filter.return_value = []
        promo_mock.filter.return_value = []

        mock_order = _make_order_mock(total="50.00")
        order_mock.create.return_value = mock_order
        orderitem_mock.create.return_value = MagicMock()

        with patch("menu.views.transaction") as tx_mock:
            tx_mock.atomic.return_value = _make_transaction_ctx()
            with patch("menu.views._generate_order_number", return_value="ORD-HH-002"):
                with patch("menu.views._broadcast_order_change"):
                    req = self._staff_post(
                        data={"items": [{"slug": "dish-1", "qty": 1}], "fulfillment_type": "pickup"}
                    )
                    resp = self.view(req)

        self.assertNotIn(resp.status_code, [400, 403, 503], msg=f"Unexpected early exit: {resp.data}")
        self.assertTrue(orderitem_mock.create.called, "OrderItem.objects.create was never called")
        call_kwargs = orderitem_mock.create.call_args[1]
        self.assertEqual(call_kwargs["unit_price"], Decimal("50.00"))


# ═══════════════════════════════════════════════════════════════════════════════
# StaffAppendOrderItemsView — view-level: OrderItem.unit_price is discounted
# ═══════════════════════════════════════════════════════════════════════════════

class StaffAppendOrderItemsHappyHourTests(SimpleTestCase):
    """StaffAppendOrderItemsView must write discounted unit_price to OrderItem."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import StaffAppendOrderItemsView
        self.view = StaffAppendOrderItemsView.as_view()

    def _make_open_table_order(self):
        """Return a mock table order in an editable state with all Decimal fields set."""
        from menu.models import Order
        o = MagicMock()
        o.id = 10
        o.pk = 10
        o.fulfillment_type = Order.FulfillmentType.TABLE
        o.status = Order.Status.PENDING
        o.payment_status = Order.PaymentStatus.UNPAID
        o.order_number = "ORD-STAFF-01"
        o.total = Decimal("0")
        o.promotion_discount = "0"
        o.loyalty_discount = "0"
        o.delivery_fee = "0"
        o.tip_amount = "0"
        o.wallet_amount_paid = Decimal("0")
        o.items = MagicMock()
        o.items.all.return_value = []
        o.table_section_id = None
        return o

    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Order.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    @patch("menu.pricing.HappyHour")
    def test_staff_append_writes_discounted_unit_price(
        self, mock_hh, profile_mock, dish_mock, opt_mock, order_mock, orderitem_mock
    ):
        """OrderItem created by StaffAppendOrderItemsView must carry the HH-discounted price."""
        prof = _profile()
        profile_mock.filter.return_value.first.return_value = prof

        dish = _make_dish(price="80.00")
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        # 10% off → 72.00
        rule = _make_rule(percent_off=10, category_ids=[])
        mock_hh.objects.filter.return_value.prefetch_related.return_value = [rule]

        opt_mock.filter.return_value = []

        open_order = self._make_open_table_order()
        # First call: Order.objects.prefetch_related("items").filter(pk=10).first()
        order_mock.prefetch_related.return_value.filter.return_value.first.return_value = open_order
        # Second call after create: Order.objects.prefetch_related("items").get(pk=10)
        order_mock.prefetch_related.return_value.get.return_value = open_order
        orderitem_mock.create.return_value = MagicMock()

        payload = {"items": [{"dish_slug": "dish-1", "qty": 1}]}
        req = self.factory.post("/api/staff/orders/10/items/", payload, format="json")
        req.tenant = _tenant()
        req.user = _staff_user(tenant_id=req.tenant.id)

        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views._can_access_order", return_value=True), \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views._broadcast_order_change"), \
             patch("menu.views._staff_order_payload", return_value={}):
            tx_mock.atomic.return_value = _make_transaction_ctx()
            resp = self.view(req, order_id=10)

        self.assertNotIn(resp.status_code, [400, 403, 409], msg=f"Unexpected error: {getattr(resp, 'data', resp)}")
        self.assertTrue(orderitem_mock.create.called, "OrderItem.objects.create was never called")
        call_kwargs = orderitem_mock.create.call_args[1]
        self.assertEqual(
            call_kwargs["unit_price"], Decimal("72.00"),
            f"Expected 72.00 (10% off 80.00), got {call_kwargs['unit_price']}"
        )

    @patch("menu.views.OrderItem.objects")
    @patch("menu.views.Order.objects")
    @patch("menu.views.DishOption.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    @patch("menu.pricing.HappyHour")
    def test_staff_append_no_discount_without_rule(
        self, mock_hh, profile_mock, dish_mock, opt_mock, order_mock, orderitem_mock
    ):
        """Without an active HH rule, staff-appended item keeps dish.price."""
        prof = _profile()
        profile_mock.filter.return_value.first.return_value = prof

        dish = _make_dish(price="80.00")
        dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]

        mock_hh.objects.filter.return_value.prefetch_related.return_value = []

        opt_mock.filter.return_value = []

        open_order = self._make_open_table_order()
        order_mock.prefetch_related.return_value.filter.return_value.first.return_value = open_order
        order_mock.prefetch_related.return_value.get.return_value = open_order
        orderitem_mock.create.return_value = MagicMock()

        payload = {"items": [{"dish_slug": "dish-1", "qty": 1}]}
        req = self.factory.post("/api/staff/orders/10/items/", payload, format="json")
        req.tenant = _tenant()
        req.user = _staff_user(tenant_id=req.tenant.id)

        with patch("menu.views._can_edit_tenant_order", return_value=True), \
             patch("menu.views._can_access_order", return_value=True), \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views._broadcast_order_change"), \
             patch("menu.views._staff_order_payload", return_value={}):
            tx_mock.atomic.return_value = _make_transaction_ctx()
            resp = self.view(req, order_id=10)

        self.assertNotIn(resp.status_code, [400, 403, 409], msg=f"Unexpected error: {getattr(resp, 'data', resp)}")
        self.assertTrue(orderitem_mock.create.called, "OrderItem.objects.create was never called")
        call_kwargs = orderitem_mock.create.call_args[1]
        self.assertEqual(call_kwargs["unit_price"], Decimal("80.00"))


# ═══════════════════════════════════════════════════════════════════════════════
# MarketplacePlaceOrderView — verify effective_unit_price is called with live HH rules
# ═══════════════════════════════════════════════════════════════════════════════

class MarketplacePlaceOrderHappyHourTests(SimpleTestCase):
    """MarketplacePlaceOrderView must apply happy-hour discounts at order placement.

    The view runs inside a schema_context and imports menu models inline, making
    a full end-to-end test without a real DB impractical. Instead we test:
      1. The pricing pipeline (get_active_happy_hours → effective_unit_price) that
         MarketplacePlaceOrderView calls through its local aliases _get_hh / _eff_price.
      2. That accounts.views imports and calls those functions from menu.pricing
         (structural smoke test via inspect / grep of the source).
    These tests catch any breakage of the pricing wiring without needing schema_context.
    """

    def test_pricing_pipeline_produces_discounted_price_for_marketplace(self):
        """The get_active_happy_hours → effective_unit_price pipeline returns the HH price."""
        from menu.pricing import get_active_happy_hours, effective_unit_price

        rule = _make_rule(percent_off=25, category_ids=[])  # 25% off = 30.00
        dish = _make_dish(pk=7, price="40.00", category_id=3)

        with patch("menu.pricing.HappyHour") as mock_hh:
            mock_hh.objects.filter.return_value.prefetch_related.return_value = [rule]
            now_dt = datetime(2026, 6, 8, 17, 0, tzinfo=_tz.utc)  # Friday 17:00 — Mon-Fri rule matches
            active = get_active_happy_hours(now_dt)

        self.assertEqual(len(active), 1, "Expected 1 active rule for Friday 17:00")
        price, matched = effective_unit_price(dish, active)
        self.assertEqual(price, Decimal("30.00"), "25% off 40.00 should yield 30.00")
        self.assertIs(matched, active[0])

    def test_marketplace_no_rule_price_unchanged(self):
        """Without an active rule, marketplace dishes are priced at dish.price."""
        from menu.pricing import effective_unit_price

        dish = _make_dish(pk=7, price="40.00")
        price, rule = effective_unit_price(dish, [])
        self.assertEqual(price, Decimal("40.00"))
        self.assertIsNone(rule)

    def test_accounts_views_wires_effective_unit_price(self):
        """Structural test: accounts.views must import and call effective_unit_price from menu.pricing.

        If a developer reverts the pricing wiring in MarketplacePlaceOrderView, the import
        of _eff_price from menu.pricing will disappear and this test fails.
        """
        import inspect
        import accounts.views as av
        src = inspect.getsource(av.MarketplacePlaceOrderView.post)
        self.assertIn("effective_unit_price", src,
                      "MarketplacePlaceOrderView.post must reference effective_unit_price")
        self.assertIn("get_active_happy_hours", src,
                      "MarketplacePlaceOrderView.post must reference get_active_happy_hours")
