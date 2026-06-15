"""
Unit tests for private helper functions in menu/views.py:
  - _is_promo_active_now
  - _compute_promo_discount
  - _serialize_promotion
  - _is_tenant_owner
  - _can_edit_tenant_order

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


def _utc_today():
    """Today's date on the SAME clock _is_promo_active_now defaults to.

    The promo window is now evaluated from ONE consistent clock (the wrapper
    defaults to datetime.now(UTC)) instead of mixing date.today() (server-local)
    with datetime.utcnow() — the historic timezone bug. The date-boundary tests
    below anchor on UTC so an exact-today bound is deterministic regardless of the
    server's local offset (e.g. this host runs UTC+1, where local midnight is the
    previous day in UTC).
    """
    return datetime.now(timezone.utc).date()

from menu.views import (
    _is_promo_active_now,
    _compute_promo_discount,
    _serialize_promotion,
    _is_tenant_owner,
    _can_edit_tenant_order,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _promo(
    *,
    active_from=None,
    active_until=None,
    days=None,
    time_start="",
    time_end="",
    promo_type="percentage",
    discount_value="10.00",
    min_order_amount="0.00",
    is_active=True,
    max_uses=None,
    use_count=0,
    code="",
    is_platform_flash=False,
    name="Deal",
    description="",
    id=1,
):
    created_at = date.today()
    return SimpleNamespace(
        id=id,
        name=name,
        description=description,
        promo_type=promo_type,
        discount_value=Decimal(discount_value),
        min_order_amount=Decimal(min_order_amount),
        days=days or [],
        time_start=time_start,
        time_end=time_end,
        active_from=active_from,
        active_until=active_until,
        is_active=is_active,
        max_uses=max_uses,
        use_count=use_count,
        code=code,
        is_platform_flash=is_platform_flash,
        created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00"),
    )


def _user(
    *,
    authenticated=True,
    superuser=False,
    staff=False,
    platform_admin=False,
    role=None,
    tenant_id=1,
):
    from accounts.models import User
    u = MagicMock(spec=User)
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.is_staff = staff
    u.is_platform_admin = platform_admin
    u.role = role or User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _request(user=None, tenant=None):
    return SimpleNamespace(
        user=user or _user(),
        tenant=tenant,
    )


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


# ══════════════════════════════════════════════════════════════════════════════
# _is_promo_active_now
# ══════════════════════════════════════════════════════════════════════════════

class IsPromoActiveNowTests(SimpleTestCase):
    def test_no_restrictions_returns_true(self):
        self.assertTrue(_is_promo_active_now(_promo()))

    def test_future_active_from_returns_false(self):
        tomorrow = _utc_today() + timedelta(days=1)
        self.assertFalse(_is_promo_active_now(_promo(active_from=tomorrow)))

    def test_past_active_from_returns_true(self):
        yesterday = _utc_today() - timedelta(days=1)
        self.assertTrue(_is_promo_active_now(_promo(active_from=yesterday)))

    def test_expired_active_until_returns_false(self):
        yesterday = _utc_today() - timedelta(days=1)
        self.assertFalse(_is_promo_active_now(_promo(active_until=yesterday)))

    def test_future_active_until_returns_true(self):
        tomorrow = _utc_today() + timedelta(days=1)
        self.assertTrue(_is_promo_active_now(_promo(active_until=tomorrow)))

    def test_today_as_active_from_returns_true(self):
        today = _utc_today()
        self.assertTrue(_is_promo_active_now(_promo(active_from=today)))

    def test_today_as_active_until_returns_true(self):
        today = _utc_today()
        self.assertTrue(_is_promo_active_now(_promo(active_until=today)))

    def test_days_restriction_current_day_allowed(self):
        """All seven days allowed → always passes day check."""
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.assertTrue(_is_promo_active_now(_promo(days=all_days)))

    def test_time_range_all_day_passes(self):
        """00:00–23:59 always passes time check."""
        self.assertTrue(_is_promo_active_now(_promo(time_start="00:00", time_end="23:59")))

    def test_no_time_range_set_passes(self):
        self.assertTrue(_is_promo_active_now(_promo(time_start="", time_end="")))


# ══════════════════════════════════════════════════════════════════════════════
# _compute_promo_discount
# ══════════════════════════════════════════════════════════════════════════════

class ComputePromoDiscountTests(SimpleTestCase):
    def test_percentage_discount(self):
        promo = _promo(promo_type="percentage", discount_value="10.00")
        result = _compute_promo_discount(promo, Decimal("100.00"), Decimal("5.00"))
        self.assertEqual(result, Decimal("10.00"))

    def test_percentage_capped_at_100(self):
        promo = _promo(promo_type="percentage", discount_value="150.00")
        result = _compute_promo_discount(promo, Decimal("50.00"), Decimal("0.00"))
        self.assertEqual(result, Decimal("50.00"))

    def test_percentage_floor_at_0(self):
        promo = _promo(promo_type="percentage", discount_value="-10.00")
        result = _compute_promo_discount(promo, Decimal("50.00"), Decimal("0.00"))
        self.assertEqual(result, Decimal("0.00"))

    def test_fixed_discount_less_than_subtotal(self):
        promo = _promo(promo_type="fixed", discount_value="5.00")
        result = _compute_promo_discount(promo, Decimal("30.00"), Decimal("0.00"))
        self.assertEqual(result, Decimal("5.00"))

    def test_fixed_discount_capped_at_subtotal(self):
        promo = _promo(promo_type="fixed", discount_value="200.00")
        result = _compute_promo_discount(promo, Decimal("50.00"), Decimal("0.00"))
        self.assertEqual(result, Decimal("50.00"))

    def test_free_delivery_returns_delivery_fee(self):
        promo = _promo(promo_type="free_delivery", discount_value="0.00")
        result = _compute_promo_discount(promo, Decimal("40.00"), Decimal("7.50"))
        self.assertEqual(result, Decimal("7.50"))

    def test_unknown_type_returns_zero(self):
        promo = _promo(promo_type="mystery", discount_value="10.00")
        result = _compute_promo_discount(promo, Decimal("40.00"), Decimal("5.00"))
        self.assertEqual(result, Decimal("0"))

    def test_result_has_two_decimal_places(self):
        promo = _promo(promo_type="percentage", discount_value="33.00")
        result = _compute_promo_discount(promo, Decimal("10.00"), Decimal("0.00"))
        self.assertEqual(result, Decimal("3.30"))


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_promotion
# ══════════════════════════════════════════════════════════════════════════════

class SerializePromotionTests(SimpleTestCase):
    def test_required_fields_present(self):
        result = _serialize_promotion(_promo())
        for key in ("id", "name", "promo_type", "discount_value", "min_order_amount",
                    "days", "time_start", "time_end", "is_active", "max_uses",
                    "use_count", "code", "created_at"):
            self.assertIn(key, result, f"Missing field: {key!r}")

    def test_discount_value_is_string(self):
        result = _serialize_promotion(_promo(discount_value="15.00"))
        self.assertEqual(result["discount_value"], "15.00")

    def test_none_active_from_is_null(self):
        result = _serialize_promotion(_promo(active_from=None))
        self.assertIsNone(result["active_from"])

    def test_active_from_isoformat(self):
        d = date(2025, 6, 1)
        result = _serialize_promotion(_promo(active_from=d))
        self.assertEqual(result["active_from"], "2025-06-01")

    def test_days_defaults_to_empty_list(self):
        result = _serialize_promotion(_promo(days=None))
        self.assertEqual(result["days"], [])

    def test_code_defaults_to_empty_string(self):
        result = _serialize_promotion(_promo(code=None))
        self.assertEqual(result["code"], "")


# ══════════════════════════════════════════════════════════════════════════════
# _is_tenant_owner
# ══════════════════════════════════════════════════════════════════════════════

class IsTenantOwnerTests(SimpleTestCase):
    def test_unauthenticated_returns_false(self):
        req = _request(user=_user(authenticated=False))
        self.assertFalse(_is_tenant_owner(req))

    def test_superuser_returns_true(self):
        req = _request(user=_user(superuser=True))
        self.assertTrue(_is_tenant_owner(req))

    def test_staff_alone_returns_false(self):
        # OPS-5d: a Django is_staff flag is no longer a tenant-owner bypass.
        req = _request(user=_user(staff=True))
        self.assertFalse(_is_tenant_owner(req))

    def test_platform_admin_returns_true(self):
        req = _request(user=_user(platform_admin=True))
        self.assertTrue(_is_tenant_owner(req))

    def test_no_tenant_returns_false(self):
        req = _request(user=_user(tenant_id=1), tenant=None)
        self.assertFalse(_is_tenant_owner(req))

    def test_wrong_tenant_returns_false(self):
        req = _request(user=_user(tenant_id=99), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))

    def test_tenant_owner_with_matching_tenant_returns_true(self):
        from accounts.models import User
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(_is_tenant_owner(req))

    def test_tenant_staff_with_matching_tenant_returns_false(self):
        """Staff are excluded from the owner-only gate (security fix)."""
        from accounts.models import User
        req = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertFalse(_is_tenant_owner(req))


# ══════════════════════════════════════════════════════════════════════════════
# _can_edit_tenant_order
# ══════════════════════════════════════════════════════════════════════════════

class CanEditTenantOrderTests(SimpleTestCase):
    def test_unauthenticated_returns_false(self):
        req = _request(user=_user(authenticated=False))
        self.assertFalse(_can_edit_tenant_order(req))

    def test_superuser_returns_true(self):
        req = _request(user=_user(superuser=True))
        self.assertTrue(_can_edit_tenant_order(req))

    def test_staff_alone_returns_false(self):
        # OPS-5d: a Django is_staff flag is no longer a cross-tenant order-edit bypass.
        req = _request(user=_user(staff=True))
        self.assertFalse(_can_edit_tenant_order(req))

    def test_platform_admin_returns_true(self):
        req = _request(user=_user(platform_admin=True))
        self.assertTrue(_can_edit_tenant_order(req))

    def test_no_tenant_returns_false(self):
        req = _request(user=_user(tenant_id=1), tenant=None)
        self.assertFalse(_can_edit_tenant_order(req))

    def test_wrong_tenant_id_returns_false(self):
        req = _request(user=_user(tenant_id=99), tenant=_tenant(1))
        self.assertFalse(_can_edit_tenant_order(req))

    def test_tenant_owner_matching_tenant_returns_true(self):
        from accounts.models import User
        req = _request(user=_user(role=User.Roles.TENANT_OWNER, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(_can_edit_tenant_order(req))

    def test_tenant_staff_matching_tenant_returns_true(self):
        from accounts.models import User
        req = _request(user=_user(role=User.Roles.TENANT_STAFF, tenant_id=1), tenant=_tenant(1))
        self.assertTrue(_can_edit_tenant_order(req))

    def test_no_user_attribute_returns_false(self):
        req = SimpleNamespace(tenant=_tenant(1))
        self.assertFalse(_can_edit_tenant_order(req))
