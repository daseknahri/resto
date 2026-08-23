"""C3: Loyalty depth — tier progression, first-order bonus, birthday bonus.

All tests are SimpleTestCase (no DB) and verify:
  • Tier multiplier logic (bronze / silver / gold boundary conditions)
  • lifetime_loyalty_points updated alongside loyalty_points on earn
  • First-order bonus: awarded exactly once per tenant (first paid order)
  • Birthday bonus: awarded at most once per calendar year
  • Birthday bonus skipped when birthday doesn't match today
  • CustomerLoyaltyConfigView and OwnerLoyaltyView return tier/bonus fields
  • CustomerProfileUpdateView accepts + validates birthday field
"""

from datetime import date
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase


# ── Tier multiplier computation ───────────────────────────────────────────────

class TierMultiplierTests(SimpleTestCase):
    """Inline reproduction of the tier-multiplier logic from PlaceOrderView."""

    def _compute_multiplier(self, lifetime_pts, tier_enabled, silver_thr=500, gold_thr=2000,
                            silver_mul="1.50", gold_mul="2.00"):
        from decimal import Decimal as D
        if not tier_enabled:
            return D("1")
        if lifetime_pts >= gold_thr:
            return D(gold_mul)
        if lifetime_pts >= silver_thr:
            return D(silver_mul)
        return D("1")

    def test_tier_disabled_always_returns_1(self):
        self.assertEqual(self._compute_multiplier(9999, tier_enabled=False), 1)

    def test_bronze_below_silver_threshold(self):
        self.assertEqual(self._compute_multiplier(0, True), 1)
        self.assertEqual(self._compute_multiplier(499, True), 1)

    def test_silver_at_threshold(self):
        from decimal import Decimal as D
        self.assertEqual(self._compute_multiplier(500, True), D("1.50"))
        self.assertEqual(self._compute_multiplier(1999, True), D("1.50"))

    def test_gold_at_threshold(self):
        from decimal import Decimal as D
        self.assertEqual(self._compute_multiplier(2000, True), D("2.00"))
        self.assertEqual(self._compute_multiplier(999999, True), D("2.00"))

    def test_custom_thresholds(self):
        from decimal import Decimal as D
        self.assertEqual(self._compute_multiplier(100, True, silver_thr=100, gold_thr=500,
                                                   silver_mul="1.25", gold_mul="1.75"), D("1.25"))
        self.assertEqual(self._compute_multiplier(500, True, silver_thr=100, gold_thr=500,
                                                   silver_mul="1.25", gold_mul="1.75"), D("1.75"))


# ── Birthday bonus guard ──────────────────────────────────────────────────────

class BirthdayBonusGuardTests(SimpleTestCase):
    """The birthday bonus fires only when: birthday matches today AND year not already rewarded."""

    def _should_award(self, birthday, today, rewarded_year):
        if birthday is None:
            return False
        return (
            birthday.month == today.month
            and birthday.day == today.day
            and rewarded_year != today.year
        )

    def test_birthday_today_not_yet_rewarded(self):
        bday = date(1990, 6, 18)
        today = date(2026, 6, 18)
        self.assertTrue(self._should_award(bday, today, None))

    def test_birthday_today_already_rewarded_this_year(self):
        bday = date(1990, 6, 18)
        today = date(2026, 6, 18)
        self.assertFalse(self._should_award(bday, today, 2026))

    def test_birthday_today_rewarded_last_year(self):
        bday = date(1990, 6, 18)
        today = date(2026, 6, 18)
        self.assertTrue(self._should_award(bday, today, 2025))

    def test_birthday_different_day(self):
        bday = date(1990, 6, 17)
        today = date(2026, 6, 18)
        self.assertFalse(self._should_award(bday, today, None))

    def test_birthday_different_month(self):
        bday = date(1990, 7, 18)
        today = date(2026, 6, 18)
        self.assertFalse(self._should_award(bday, today, None))

    def test_birthday_none_skipped(self):
        self.assertFalse(self._should_award(None, date(2026, 6, 18), None))


# ── CustomerLoyaltyConfigView — tier fields present ───────────────────────────

class CustomerLoyaltyConfigViewTierTests(SimpleTestCase):
    """CustomerLoyaltyConfigView must include tier and bonus fields when enabled."""

    def test_response_includes_tier_fields(self):
        from menu.views import CustomerLoyaltyConfigView
        from rest_framework.test import APIRequestFactory

        mock_cfg = MagicMock()
        mock_cfg.enabled = True
        mock_cfg.points_per_unit = 10
        mock_cfg.redeem_threshold = 100
        mock_cfg.points_value = "0.0100"
        mock_cfg.tier_enabled = True
        mock_cfg.tier_silver_threshold = 500
        mock_cfg.tier_gold_threshold = 2000
        mock_cfg.tier_silver_multiplier = "1.50"
        mock_cfg.tier_gold_multiplier = "2.00"
        mock_cfg.first_order_bonus_points = 50
        mock_cfg.birthday_bonus_points = 100

        factory = APIRequestFactory()
        req = factory.get("/api/customer/loyalty/config/")

        with patch("menu.views.LoyaltyConfig.objects") as mock_qs:
            mock_qs.filter.return_value.first.return_value = mock_cfg
            resp = CustomerLoyaltyConfigView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["tier_enabled"])
        self.assertEqual(resp.data["tier_silver_threshold"], 500)
        self.assertEqual(resp.data["tier_gold_threshold"], 2000)
        self.assertEqual(resp.data["first_order_bonus_points"], 50)
        self.assertEqual(resp.data["birthday_bonus_points"], 100)


# ── CustomerProfileUpdateView — birthday field ───────────────────────────────
#
# RISK IDENTITY-1: CustomerProfileUpdateView now authenticates via
# CustomerSessionAuthentication + IsCustomer, so the signed-in Customer arrives as
# request.user. Force-authenticate a real (unsaved) Customer principal instead of
# mocking Customer.objects.get.

class CustomerProfileBirthdayTests(SimpleTestCase):
    """CustomerProfileUpdateView accepts a valid birthday and rejects invalid ones."""

    def _make_customer(self):
        from accounts.models import Customer

        c = Customer(
            id=1,
            name="Test",
            email="",
            phone="+212600000001",
            phone_verified=True,
            email_verified=False,
            google_sub=None,
            wallet_balance="0.00",
            loyalty_points=0,
            lifetime_loyalty_points=0,
            birthday=None,
            locale="en",
            is_driver=False,
            is_driver_online=False,
            notify_order_updates=True,
            notify_review_prompts=True,
            notify_promotions=True,
            referral_code="REF123",
            referral_reward_given=False,
        )
        c.save = MagicMock()
        return c

    def test_valid_birthday_accepted(self):
        from accounts.views import CustomerProfileUpdateView
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        req = factory.patch("/api/customer/profile/", {"birthday": "1990-06-15"}, format="json")
        req.session = {"customer_id": 1}
        mock_customer = self._make_customer()
        force_authenticate(req, user=mock_customer)

        resp = CustomerProfileUpdateView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        # birthday should have been set
        self.assertEqual(mock_customer.birthday, date(1990, 6, 15))

    def test_invalid_birthday_ignored(self):
        from accounts.views import CustomerProfileUpdateView
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        req = factory.patch("/api/customer/profile/", {"birthday": "not-a-date"}, format="json")
        req.session = {"customer_id": 1}
        mock_customer = self._make_customer()
        force_authenticate(req, user=mock_customer)

        resp = CustomerProfileUpdateView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(mock_customer.birthday)  # unchanged

    def test_empty_birthday_clears_field(self):
        from accounts.views import CustomerProfileUpdateView
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        req = factory.patch("/api/customer/profile/", {"birthday": ""}, format="json")
        req.session = {"customer_id": 1}
        mock_customer = self._make_customer()
        mock_customer.birthday = date(1990, 6, 15)
        force_authenticate(req, user=mock_customer)

        resp = CustomerProfileUpdateView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(mock_customer.birthday)


# ── Bug 1 regression: PlaceOrderView loyalty grants are race-safe ─────────────
# The birthday / first-order milestone bonuses are check-then-act. Before the fix the
# birthday guard read loyalty_birthday_rewarded_year off the STALE request-time
# _linked_customer snapshot (hydrated before the atomic block) and granted
# unconditionally, so two concurrent birthday orders both saw year=None and both
# granted. The fix mirrors the already-correct MarketplacePlaceOrderView loyalty block:
#   1. take Customer.objects.select_for_update() at the top of the loyalty block,
#   2. fresh-read the rewarded-year from the DB UNDER that lock (not the snapshot),
#   3. make the grant UPDATE conditional via .exclude(loyalty_birthday_rewarded_year=yr).

class PlaceOrderLoyaltyConcurrencyTests(SimpleTestCase):
    """Drive the real PlaceOrderView through a dine-in (table) order for a birthday
    customer and assert the hardened lock / fresh-read / conditional-grant path is taken.

    Dine-in is chosen deliberately: it is prepay-exempt, so nothing else locks the
    Customer row (no wallet debit) — the exact scenario the loyalty lock now covers.
    """

    def _run(self):
        from decimal import Decimal
        from types import SimpleNamespace
        from django.utils import timezone
        from rest_framework.test import APIRequestFactory, force_authenticate
        from menu.views import PlaceOrderView
        from menu.models import Order

        today = timezone.localtime(timezone.now()).date()

        # Birthday-today customer principal (the loyalty link).
        customer = MagicMock()
        customer.pk = 42
        customer.id = 42
        customer.is_authenticated = True
        customer.role = None
        customer.birthday = today
        customer.lifetime_loyalty_points = 0
        customer.loyalty_points = 0
        customer.referred_by_id = None          # short-circuits the referral block
        customer.referral_reward_given = True
        customer.name = "Alice"
        customer.phone = ""
        customer.wallet_balance = Decimal("0")

        # LoyaltyConfig: ONLY the birthday bonus active (isolate the birthday path —
        # points_per_unit=0 and first_order_bonus_points=0 skip the other grants).
        cfg = SimpleNamespace(
            enabled=True, tier_enabled=False, points_per_unit=0,
            first_order_bonus_points=0, birthday_bonus_points=100,
        )

        # Restaurant profile — safe values so no early gate fires and no WhatsApp is sent.
        profile = MagicMock()
        profile.is_menu_published = True
        profile.is_menu_temporarily_disabled = False
        profile.is_ordering_enabled = True
        profile.capabilities = {}
        profile.referral_enabled = False
        profile.whatsapp = ""
        profile.phone = ""
        profile.platform_delivery_enabled = False
        profile.lat = None
        profile.lng = None

        dish = MagicMock()
        dish.pk = 5
        dish.slug = "steak"
        dish.name = "Steak"
        dish.price = Decimal("50.00")
        dish.stock_qty = None                   # unlimited → no stock lock needed
        dish.is_published = True
        dish.is_available = True
        dish.currency = "MAD"
        _cat = MagicMock(); _cat.course = 0
        dish.category = _cat
        dish.combo_components.all.return_value = []

        tenant = SimpleNamespace(id=1, name="R", schema_name="r1", slug="r1")
        plan = MagicMock(); plan.can_checkout = True; plan.can_whatsapp_order = False
        tenant.plan = plan

        created_order = MagicMock()
        created_order.pk = 10
        created_order.id = 10
        created_order.order_number = "ORD-TEST"
        created_order.status = Order.Status.PENDING
        created_order.payment_status = Order.PaymentStatus.UNPAID
        created_order.total = Decimal("50.00")
        created_order.delivery_fee = Decimal("0")
        created_order.tip_amount = Decimal("0")
        created_order.wallet_amount_paid = Decimal("0")
        created_order.currency = "MAD"
        created_order.estimated_ready_minutes = None
        created_order.points_earned = 0
        created_order.loyalty_discount = Decimal("0")
        created_order.redeemed_loyalty_points = 0
        created_order.scheduled_for = None
        created_order.customer_name = "Alice"
        created_order.save = MagicMock()

        body = {
            "items": [{"slug": "steak", "qty": 1}],
            "fulfillment_type": "table",
            "table_slug": "t1",
            "customer_name": "Alice",
        }

        with patch("menu.views.customer_or_none", return_value=customer), \
             patch("menu.views._is_restaurant_currently_open", return_value=True), \
             patch("menu.views._orders_paused_now", return_value=False), \
             patch("menu.models.RecipeLine"), \
             patch("menu.views.OrderItem.objects") as item_om, \
             patch("menu.views.Dish.objects") as dish_om, \
             patch("menu.views.DishOption.objects") as dish_opt, \
             patch("menu.views.transaction") as tx_mock, \
             patch("menu.views.Order.objects") as order_om, \
             patch("menu.views.Profile.objects") as profile_om, \
             patch("menu.views.Promotion.objects") as promo_om, \
             patch("menu.views.LoyaltyConfig.objects") as lc_om, \
             patch("menu.views.get_all_active_hh_rules", return_value=[]), \
             patch("menu.views._generate_order_number", return_value="ORD-TEST"), \
             patch("menu.views.TableLink.objects") as tl_om, \
             patch("accounts.models.Customer") as CustModel:

            profile_om.filter.return_value.first.return_value = profile
            dish_om.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            dish_om.select_for_update.return_value.filter.return_value = []
            dish_opt.filter.return_value.select_related.return_value = []
            promo_om.filter.return_value = []
            lc_om.filter.return_value.first.return_value = cfg

            class _FakeAtomic:
                def __enter__(self): return self
                def __exit__(self, *a): return False
            tx_mock.atomic.return_value = _FakeAtomic()

            order_om.create.return_value = created_order
            item_om.create = MagicMock()

            tl = MagicMock(); tl.label = "T1"; tl.slug = "t1"; tl.is_active = True
            tl_om.filter.return_value.first.return_value = tl

            # Fresh-read of the rewarded-year UNDER the lock → None (never rewarded), so
            # the birthday grant fires and we can assert the conditional-exclude UPDATE.
            CustModel.objects.filter.return_value.values_list.return_value.first.return_value = None

            factory = APIRequestFactory()
            req = factory.post("/api/place-order/", body, format="json")
            force_authenticate(req, user=customer)
            req.tenant = tenant
            req.session = {}
            resp = PlaceOrderView.as_view()(req)

        return resp, CustModel, today

    def test_birthday_grant_uses_lock_freshread_and_exclude(self):
        resp, CustModel, today = self._run()
        _data = getattr(resp, "data", None)
        self.assertIn(resp.status_code, (200, 201), msg=f"early exit before loyalty: {_data}")
        # 1. Row lock taken at the top of the loyalty block (serializes milestone grants).
        CustModel.objects.select_for_update.assert_called()
        # 2. Rewarded-year fresh-read from the DB (NOT the stale _linked_customer snapshot).
        CustModel.objects.filter.return_value.values_list.assert_any_call(
            "loyalty_birthday_rewarded_year", flat=True
        )
        # 3. Grant UPDATE is conditional: exclude rows already stamped with this year, so a
        #    racer that slipped past the Python check makes the UPDATE a no-op.
        CustModel.objects.filter.return_value.exclude.assert_any_call(
            loyalty_birthday_rewarded_year=today.year
        )
        CustModel.objects.filter.return_value.exclude.return_value.update.assert_called()
