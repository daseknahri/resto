"""
Unit tests for model methods in accounts/models.py:
  - User.is_platform_admin / is_tenant_owner / is_tenant_staff properties
  - User.effective_perm_manage_orders / effective_perm_view_revenue / effective_perm_edit_menu
  - PlatformFlashSale.is_live
  - DeliveryZone.compute_fee
  - DeliveryJob.is_terminal

All tests are unit-level (SimpleTestCase — no real DB).
Uses __new__ to instantiate model classes without __init__ DB access.
"""
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from accounts.models import User, PlatformFlashSale, DeliveryZone, DeliveryJob


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_OWNER, **kwargs):
    u = User.__new__(User)
    u.role = role
    for k, v in kwargs.items():
        setattr(u, k, v)
    return u


# ══════════════════════════════════════════════════════════════════════════════
# User role properties
# ══════════════════════════════════════════════════════════════════════════════

class UserRolePropertyTests(SimpleTestCase):
    def test_is_platform_admin_true_for_platform_superadmin(self):
        u = _user(role=User.Roles.PLATFORM_SUPERADMIN)
        self.assertTrue(u.is_platform_admin)

    def test_is_platform_admin_false_for_tenant_owner(self):
        u = _user(role=User.Roles.TENANT_OWNER)
        self.assertFalse(u.is_platform_admin)

    def test_is_tenant_owner_true(self):
        u = _user(role=User.Roles.TENANT_OWNER)
        self.assertTrue(u.is_tenant_owner)

    def test_is_tenant_owner_false_for_staff(self):
        u = _user(role=User.Roles.TENANT_STAFF)
        self.assertFalse(u.is_tenant_owner)

    def test_is_tenant_staff_true(self):
        u = _user(role=User.Roles.TENANT_STAFF)
        self.assertTrue(u.is_tenant_staff)

    def test_is_tenant_staff_false_for_owner(self):
        u = _user(role=User.Roles.TENANT_OWNER)
        self.assertFalse(u.is_tenant_staff)

    def test_mutually_exclusive_roles(self):
        owner = _user(role=User.Roles.TENANT_OWNER)
        self.assertTrue(owner.is_tenant_owner)
        self.assertFalse(owner.is_tenant_staff)
        self.assertFalse(owner.is_platform_admin)


# ══════════════════════════════════════════════════════════════════════════════
# User.effective_perm_*
# ══════════════════════════════════════════════════════════════════════════════

class UserEffectivePermTests(SimpleTestCase):
    def test_owner_always_can_manage_orders(self):
        u = _user(role=User.Roles.TENANT_OWNER, perm_manage_orders=False)
        self.assertTrue(u.effective_perm_manage_orders())

    def test_staff_with_perm_can_manage_orders(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_manage_orders=True)
        self.assertTrue(u.effective_perm_manage_orders())

    def test_staff_without_perm_cannot_manage_orders(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_manage_orders=False)
        self.assertFalse(u.effective_perm_manage_orders())

    def test_owner_always_can_view_revenue(self):
        u = _user(role=User.Roles.TENANT_OWNER, perm_view_revenue=False)
        self.assertTrue(u.effective_perm_view_revenue())

    def test_staff_with_perm_can_view_revenue(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_view_revenue=True)
        self.assertTrue(u.effective_perm_view_revenue())

    def test_staff_without_perm_cannot_view_revenue(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_view_revenue=False)
        self.assertFalse(u.effective_perm_view_revenue())

    def test_owner_always_can_edit_menu(self):
        u = _user(role=User.Roles.TENANT_OWNER, perm_edit_menu=False)
        self.assertTrue(u.effective_perm_edit_menu())

    def test_staff_with_perm_can_edit_menu(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_edit_menu=True)
        self.assertTrue(u.effective_perm_edit_menu())

    def test_staff_without_perm_cannot_edit_menu(self):
        u = _user(role=User.Roles.TENANT_STAFF, perm_edit_menu=False)
        self.assertFalse(u.effective_perm_edit_menu())


# ══════════════════════════════════════════════════════════════════════════════
# PlatformFlashSale.is_live
# ══════════════════════════════════════════════════════════════════════════════

class PlatformFlashSaleIsLiveTests(SimpleTestCase):
    def _sale(self, *, is_active=True, from_delta=-1, until_delta=1,
              max_redemptions=None, redemption_count=0):
        s = PlatformFlashSale.__new__(PlatformFlashSale)
        s.is_active = is_active
        now = timezone.now()
        s.active_from = now + timedelta(days=from_delta)
        s.active_until = now + timedelta(days=until_delta)
        s.max_redemptions = max_redemptions
        s.redemption_count = redemption_count
        return s

    def test_active_sale_in_window_is_live(self):
        self.assertTrue(self._sale().is_live())

    def test_inactive_sale_is_not_live(self):
        self.assertFalse(self._sale(is_active=False).is_live())

    def test_sale_not_started_is_not_live(self):
        self.assertFalse(self._sale(from_delta=1, until_delta=2).is_live())

    def test_sale_past_window_is_not_live(self):
        self.assertFalse(self._sale(from_delta=-3, until_delta=-1).is_live())

    def test_max_redemptions_not_reached_is_live(self):
        self.assertTrue(self._sale(max_redemptions=10, redemption_count=9).is_live())

    def test_max_redemptions_reached_is_not_live(self):
        self.assertFalse(self._sale(max_redemptions=10, redemption_count=10).is_live())

    def test_no_max_redemptions_always_live_in_window(self):
        self.assertTrue(self._sale(max_redemptions=None, redemption_count=9999).is_live())


# ══════════════════════════════════════════════════════════════════════════════
# DeliveryZone.compute_fee
# ══════════════════════════════════════════════════════════════════════════════

class DeliveryZoneComputeFeeTests(SimpleTestCase):
    def _zone(self, fee_tiers=None):
        z = DeliveryZone.__new__(DeliveryZone)
        z.fee_tiers = fee_tiers
        return z

    def test_no_tiers_returns_zero(self):
        self.assertEqual(self._zone(fee_tiers=None).compute_fee(5.0), 0.0)

    def test_empty_tiers_returns_zero(self):
        self.assertEqual(self._zone(fee_tiers=[]).compute_fee(5.0), 0.0)

    def test_first_tier_applies_within_range(self):
        tiers = [{"km_up_to": 5, "fee": 10}, {"km_up_to": 10, "fee": 20}]
        self.assertEqual(self._zone(fee_tiers=tiers).compute_fee(3.0), 10.0)

    def test_second_tier_applies_when_beyond_first(self):
        tiers = [{"km_up_to": 5, "fee": 10}, {"km_up_to": 10, "fee": 20}]
        self.assertEqual(self._zone(fee_tiers=tiers).compute_fee(7.0), 20.0)

    def test_unlimited_tier_matches_any_distance(self):
        """km_up_to=None means no upper bound — always applies."""
        tiers = [{"km_up_to": 5, "fee": 10}, {"km_up_to": None, "fee": 30}]
        self.assertEqual(self._zone(fee_tiers=tiers).compute_fee(100.0), 30.0)

    def test_exactly_at_boundary_applies_tier(self):
        tiers = [{"km_up_to": 5, "fee": 15}]
        self.assertEqual(self._zone(fee_tiers=tiers).compute_fee(5.0), 15.0)

    def test_beyond_all_tiers_returns_zero(self):
        tiers = [{"km_up_to": 5, "fee": 10}]
        # 10 km > 5 km boundary; no tier covers it → 0
        self.assertEqual(self._zone(fee_tiers=tiers).compute_fee(10.0), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# DeliveryJob.is_terminal
# ══════════════════════════════════════════════════════════════════════════════

class DeliveryJobIsTerminalTests(SimpleTestCase):
    def _job(self, status):
        j = DeliveryJob.__new__(DeliveryJob)
        j.status = status
        return j

    def test_delivered_is_terminal(self):
        self.assertTrue(self._job(DeliveryJob.Status.DELIVERED).is_terminal)

    def test_failed_is_terminal(self):
        self.assertTrue(self._job(DeliveryJob.Status.FAILED).is_terminal)

    def test_searching_is_not_terminal(self):
        self.assertFalse(self._job(DeliveryJob.Status.SEARCHING).is_terminal)

    def test_assigned_is_not_terminal(self):
        self.assertFalse(self._job(DeliveryJob.Status.ASSIGNED).is_terminal)

    def test_picked_up_is_not_terminal(self):
        self.assertFalse(self._job(DeliveryJob.Status.PICKED_UP).is_terminal)

    def test_at_restaurant_is_not_terminal(self):
        self.assertFalse(self._job(DeliveryJob.Status.AT_RESTAURANT).is_terminal)
