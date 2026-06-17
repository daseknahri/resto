"""
Unit tests for private helpers in accounts/views.py and tenancy/api.py:
  accounts.views:
    - serialize_user_session
    - _haversine_km
    - _serialize_flash_sale
    - _serialize_delivery_job
    - _serialize_zone
  tenancy.api:
    - _safe_extension
    - _can_edit_tenant

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from django.utils import timezone

from accounts.views import (
    serialize_user_session,
    _haversine_km,
    _serialize_flash_sale,
    _serialize_delivery_job,
    _serialize_zone,
)
from tenancy.api import _safe_extension, _can_edit_tenant


# ── helpers ───────────────────────────────────────────────────────────────────

def _user_mock(
    *,
    authenticated=True,
    superuser=False,
    staff=False,
    platform_admin=False,
    role=None,
    tenant_id=1,
    tenant=None,
):
    from accounts.models import User
    u = MagicMock(spec=User)
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.is_staff = staff
    u.is_platform_admin = platform_admin
    u.is_tenant_owner = (role == User.Roles.TENANT_OWNER) if role else True
    u.is_tenant_staff = (role == User.Roles.TENANT_STAFF) if role else False
    u.role = role or User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.tenant = tenant
    u.Roles = User.Roles
    u.id = 1
    u.username = "testuser"
    u.email = "test@example.com"
    return u


def _tenant_ns(tenant_id=1, slug="demo", name="Demo"):
    return SimpleNamespace(id=tenant_id, slug=slug, name=name, is_active=True)


def _request_ns(user=None, tenant=None):
    return SimpleNamespace(user=user or _user_mock(), tenant=tenant)


# ══════════════════════════════════════════════════════════════════════════════
# serialize_user_session
# ══════════════════════════════════════════════════════════════════════════════

class SerializeUserSessionTests(SimpleTestCase):
    def test_basic_fields_present(self):
        u = _user_mock()
        data = serialize_user_session(u)
        for key in ("id", "username", "email", "role", "is_staff",
                    "is_superuser", "is_platform_admin",
                    "can_access_admin_console", "can_edit_tenant_menu"):
            self.assertIn(key, data, f"Missing field: {key!r}")

    def test_tenant_included_when_set(self):
        tenant = SimpleNamespace(id=1, slug="demo", name="Demo", is_active=True, lifecycle_status="active")
        u = _user_mock(tenant=tenant)
        data = serialize_user_session(u)
        self.assertIsNotNone(data["tenant"])
        self.assertEqual(data["tenant"]["slug"], "demo")

    def test_tenant_is_none_when_not_set(self):
        u = _user_mock(tenant=None)
        data = serialize_user_session(u)
        self.assertIsNone(data["tenant"])

    def test_superuser_can_access_admin_console(self):
        u = _user_mock(superuser=True)
        data = serialize_user_session(u)
        self.assertTrue(data["can_access_admin_console"])

    def test_regular_user_cannot_access_admin_console(self):
        u = _user_mock(superuser=False, staff=False, platform_admin=False)
        data = serialize_user_session(u)
        self.assertFalse(data["can_access_admin_console"])

    def test_tenant_lifecycle_status_defaults_to_active(self):
        tenant = SimpleNamespace(id=1, slug="demo", name="Demo", is_active=True)
        # no lifecycle_status attr → defaults to "active"
        u = _user_mock(tenant=tenant)
        data = serialize_user_session(u)
        self.assertEqual(data["tenant"]["lifecycle_status"], "active")


# ══════════════════════════════════════════════════════════════════════════════
# _haversine_km
# ══════════════════════════════════════════════════════════════════════════════

class HaversineKmTests(SimpleTestCase):
    def test_same_point_is_zero(self):
        self.assertAlmostEqual(_haversine_km(48.8566, 2.3522, 48.8566, 2.3522), 0.0, places=3)

    def test_paris_to_london_approx_340km(self):
        # Paris (48.8566, 2.3522) → London (51.5074, -0.1278) ≈ 340 km
        km = _haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
        self.assertGreater(km, 330)
        self.assertLess(km, 350)

    def test_casablanca_to_marrakech_approx_220km(self):
        # Casablanca (33.5731, -7.5898) → Marrakech (31.6295, -8.0083) ≈ 220 km
        km = _haversine_km(33.5731, -7.5898, 31.6295, -8.0083)
        self.assertGreater(km, 210)
        self.assertLess(km, 235)

    def test_result_is_float(self):
        result = _haversine_km(0.0, 0.0, 1.0, 1.0)
        self.assertIsInstance(result, float)

    def test_symmetric(self):
        a = _haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
        b = _haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertAlmostEqual(a, b, places=6)


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_flash_sale
# ══════════════════════════════════════════════════════════════════════════════

class SerializeFlashSaleTests(SimpleTestCase):
    def _fs(self):
        d = date(2025, 6, 1)
        return SimpleNamespace(
            id=1,
            name="Summer Sale",
            description="10% off",
            discount_value=Decimal("10.00"),
            active_from=d,
            active_until=d,
            is_active=True,
            is_live=lambda: True,
            max_redemptions=100,
            redemption_count=5,
            created_at=SimpleNamespace(isoformat=lambda: "2025-01-01T00:00:00"),
        )

    def test_required_keys_present(self):
        result = _serialize_flash_sale(self._fs())
        for key in ("id", "name", "discount_value", "active_from",
                    "active_until", "is_active", "is_live",
                    "max_redemptions", "redemption_count", "opted_in"):
            self.assertIn(key, result)

    def test_discount_value_is_string(self):
        result = _serialize_flash_sale(self._fs())
        self.assertEqual(result["discount_value"], "10.00")

    def test_opted_in_defaults_false(self):
        result = _serialize_flash_sale(self._fs())
        self.assertFalse(result["opted_in"])

    def test_opted_in_true_when_passed(self):
        result = _serialize_flash_sale(self._fs(), opted_in=True)
        self.assertTrue(result["opted_in"])

    def test_is_live_called(self):
        result = _serialize_flash_sale(self._fs())
        self.assertTrue(result["is_live"])


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_delivery_job
# ══════════════════════════════════════════════════════════════════════════════

class SerializeDeliveryJobTests(SimpleTestCase):
    def _job(self, *, driver=None):
        return SimpleNamespace(
            id=10,
            order_number="ORD-ABC123",
            tenant_id=1,
            status="pending",
            pickup_address="123 Main St",
            pickup_lat=33.0,
            pickup_lng=-7.0,
            delivery_address="456 Side St",
            delivery_lat=33.1,
            delivery_lng=-7.1,
            delivery_fee=Decimal("5.00"),
            driver_payout=Decimal("3.00"),
            platform_commission=Decimal("2.00"),
            delivery_commission_rate_applied=Decimal("40.0000"),
            assigned_at=None,
            picked_up_at=None,
            delivered_at=None,
            failed_at=None,
            food_ready_at=None,
            created_at=SimpleNamespace(isoformat=lambda: "2025-06-01T12:00:00"),
            is_terminal=False,
            failure_reason="",
            failure_note="",
            resolution="",
            driver=driver,
            customer_driver_rating=None,
            customer_driver_note="",
            driver_customer_rating=None,
            driver_customer_note="",
            restaurant_driver_rating=None,
            restaurant_driver_note="",
        )

    def _driver(self):
        return SimpleNamespace(
            id=99,
            name="Ali",
            phone="+212600000001",
            driver_vehicle="Motorcycle",
            driver_lat=33.0,
            driver_lng=-7.0,
            is_driver_online=True,
            driver_position_updated_at=None,
        )

    def test_required_keys_present(self):
        result = _serialize_delivery_job(self._job())
        for key in ("id", "order_number", "status", "delivery_fee",
                    "driver_payout", "driver", "ratings", "is_terminal"):
            self.assertIn(key, result)

    def test_driver_is_none_when_absent(self):
        result = _serialize_delivery_job(self._job())
        self.assertIsNone(result["driver"])

    def test_driver_included_when_present(self):
        result = _serialize_delivery_job(self._job(driver=self._driver()))
        self.assertIsNotNone(result["driver"])
        self.assertEqual(result["driver"]["name"], "Ali")

    def test_driver_position_not_included_by_default(self):
        result = _serialize_delivery_job(self._job(driver=self._driver()))
        self.assertNotIn("lat", result["driver"])

    def test_driver_position_included_when_requested(self):
        result = _serialize_delivery_job(
            self._job(driver=self._driver()), include_driver_position=True
        )
        self.assertIn("lat", result["driver"])
        self.assertIn("is_online", result["driver"])

    def test_driver_vehicle_always_included(self):
        result = _serialize_delivery_job(self._job(driver=self._driver()))
        self.assertEqual(result["driver"]["vehicle"], "Motorcycle")

    def test_rating_key_present_when_position_requested(self):
        result = _serialize_delivery_job(
            self._job(driver=self._driver()), include_driver_position=True
        )
        # rating is best-effort (None without a DB) but the key must be exposed.
        self.assertIn("rating", result["driver"])
        self.assertIn("rating_count", result["driver"])

    def test_distance_km_computed_from_coords(self):
        result = _serialize_delivery_job(self._job())
        # pickup (33.0,-7.0) → dropoff (33.1,-7.1) ≈ 14.6 km
        self.assertIsNotNone(result["distance_km"])
        self.assertTrue(10 < result["distance_km"] < 20)

    def test_delivery_fee_is_string(self):
        result = _serialize_delivery_job(self._job())
        self.assertEqual(result["delivery_fee"], "5.00")

    def test_null_timestamps_are_none(self):
        result = _serialize_delivery_job(self._job())
        self.assertIsNone(result["assigned_at"])
        self.assertIsNone(result["delivered_at"])
        self.assertIsNone(result["food_ready_at"])


# ══════════════════════════════════════════════════════════════════════════════
# _serialize_zone
# ══════════════════════════════════════════════════════════════════════════════

class SerializeZoneTests(SimpleTestCase):
    def _zone(self):
        return SimpleNamespace(
            id=1,
            name="Central Zone",
            city="Casablanca",
            polygon=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            center_lat=33.5,
            center_lng=-7.5,
            approx_radius_km=5.0,
            is_active=True,
            fee_tiers=None,
            created_at=SimpleNamespace(isoformat=lambda: "2025-01-01T00:00:00"),
        )

    def test_required_keys_present(self):
        result = _serialize_zone(self._zone())
        for key in ("id", "name", "city", "polygon", "center_lat",
                    "center_lng", "approx_radius_km", "is_active",
                    "fee_tiers", "created_at"):
            self.assertIn(key, result)

    def test_none_fee_tiers_returns_empty_list(self):
        result = _serialize_zone(self._zone())
        self.assertEqual(result["fee_tiers"], [])


# ══════════════════════════════════════════════════════════════════════════════
# tenancy.api._safe_extension
# ══════════════════════════════════════════════════════════════════════════════

class SafeExtensionTests(SimpleTestCase):
    def test_jpg_accepted(self):
        self.assertEqual(_safe_extension("photo.jpg"), "jpg")

    def test_jpeg_accepted(self):
        self.assertEqual(_safe_extension("photo.jpeg"), "jpeg")

    def test_png_accepted(self):
        self.assertEqual(_safe_extension("logo.PNG"), "png")

    def test_webp_accepted(self):
        self.assertEqual(_safe_extension("hero.webp"), "webp")

    def test_unknown_extension_falls_back_to_jpg(self):
        self.assertEqual(_safe_extension("file.txt"), "jpg")

    def test_empty_string_falls_back_to_jpg(self):
        self.assertEqual(_safe_extension(""), "jpg")

    def test_no_extension_falls_back_to_jpg(self):
        self.assertEqual(_safe_extension("noext"), "jpg")

    def test_gif_falls_back_to_jpg(self):
        self.assertEqual(_safe_extension("anim.gif"), "jpg")


# ══════════════════════════════════════════════════════════════════════════════
# tenancy.api._can_edit_tenant
# ══════════════════════════════════════════════════════════════════════════════

class CanEditTenantTests(SimpleTestCase):
    def test_unauthenticated_returns_false(self):
        req = _request_ns(user=_user_mock(authenticated=False))
        self.assertFalse(_can_edit_tenant(req))

    def test_superuser_returns_true(self):
        req = _request_ns(user=_user_mock(superuser=True))
        self.assertTrue(_can_edit_tenant(req))

    def test_staff_only_returns_false(self):
        # OPS-5b priv-esc fix: a Django /admin/ is_staff flag (no tenant
        # affiliation, not superuser/platform-admin) must NOT grant cross-tenant
        # edit access. is_staff was dropped from _can_edit_tenant.
        req = _request_ns(user=_user_mock(staff=True))
        self.assertFalse(_can_edit_tenant(req))

    def test_platform_admin_returns_true(self):
        req = _request_ns(user=_user_mock(platform_admin=True))
        self.assertTrue(_can_edit_tenant(req))

    def test_no_tenant_returns_false(self):
        req = _request_ns(user=_user_mock(tenant_id=1), tenant=None)
        self.assertFalse(_can_edit_tenant(req))

    def test_wrong_tenant_id_returns_false(self):
        req = _request_ns(user=_user_mock(tenant_id=99), tenant=_tenant_ns(1))
        self.assertFalse(_can_edit_tenant(req))

    def test_tenant_owner_matching_tenant_returns_true(self):
        from accounts.models import User
        req = _request_ns(
            user=_user_mock(role=User.Roles.TENANT_OWNER, tenant_id=1),
            tenant=_tenant_ns(1),
        )
        self.assertTrue(_can_edit_tenant(req))

    def test_tenant_staff_matching_tenant_returns_true(self):
        from accounts.models import User
        req = _request_ns(
            user=_user_mock(role=User.Roles.TENANT_STAFF, tenant_id=1),
            tenant=_tenant_ns(1),
        )
        self.assertTrue(_can_edit_tenant(req))
