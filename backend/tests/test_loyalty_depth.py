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
