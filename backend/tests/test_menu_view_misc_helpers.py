"""
Unit tests for two small helper methods in menu/views.py:

  AnalyticsSummaryView._can_view(request, tenant)
    Returns bool: whether the requesting user may see analytics.

  OrderHandoffView._sanitize_phone(value)
    Strips all non-digit characters from a phone string.

Also covers OrderHandoffSerializer.validate (cross-field delivery rules)
which was not included in the previous validator test file.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from menu.views import AnalyticsSummaryView, OrderHandoffSerializer, OrderHandoffView


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(
    *,
    is_authenticated=True,
    is_superuser=False,
    is_staff=False,
    is_platform_admin=False,
    tenant_id=None,
    role=None,
):
    class _Roles:
        TENANT_OWNER = "tenant_owner"
        TENANT_STAFF = "tenant_staff"

    u = MagicMock()
    u.is_authenticated = is_authenticated
    u.is_superuser = is_superuser
    u.is_staff = is_staff
    u.is_platform_admin = is_platform_admin
    u.tenant_id = tenant_id
    u.role = role
    u.Roles = _Roles
    return u


def _req(user):
    r = MagicMock()
    r.user = user
    return r


def _tenant(tid=1):
    return SimpleNamespace(id=tid)


# ══════════════════════════════════════════════════════════════════════════════
# AnalyticsSummaryView._can_view
# ══════════════════════════════════════════════════════════════════════════════

class CanViewTests(SimpleTestCase):
    """_can_view: superusers/staff/platform-admin → True; tenant match + role → True; else False."""

    def _v(self):
        return AnalyticsSummaryView()

    # ── unauthenticated ───────────────────────────────────────────────────────
    def test_unauthenticated_user_returns_false(self):
        self.assertFalse(self._v()._can_view(_req(_user(is_authenticated=False)), _tenant()))

    def test_none_user_returns_false(self):
        req = MagicMock()
        req.user = None
        self.assertFalse(self._v()._can_view(req, _tenant()))

    # ── superuser / staff ─────────────────────────────────────────────────────
    def test_superuser_returns_true(self):
        self.assertTrue(self._v()._can_view(_req(_user(is_superuser=True)), _tenant()))

    def test_django_staff_returns_true(self):
        self.assertTrue(self._v()._can_view(_req(_user(is_staff=True)), _tenant()))

    def test_platform_admin_returns_true(self):
        u = _user(is_platform_admin=True)
        self.assertTrue(self._v()._can_view(_req(u), _tenant()))

    # ── tenant owner / staff ──────────────────────────────────────────────────
    def test_tenant_owner_on_same_tenant_returns_true(self):
        u = _user(tenant_id=1, role="tenant_owner")
        self.assertTrue(self._v()._can_view(_req(u), _tenant(tid=1)))

    def test_tenant_staff_on_same_tenant_returns_true(self):
        u = _user(tenant_id=1, role="tenant_staff")
        self.assertTrue(self._v()._can_view(_req(u), _tenant(tid=1)))

    # ── wrong tenant ──────────────────────────────────────────────────────────
    def test_tenant_owner_on_different_tenant_returns_false(self):
        u = _user(tenant_id=2, role="tenant_owner")
        self.assertFalse(self._v()._can_view(_req(u), _tenant(tid=1)))

    def test_none_tenant_returns_false_for_regular_user(self):
        u = _user(tenant_id=1, role="tenant_owner")
        self.assertFalse(self._v()._can_view(_req(u), tenant=None))

    # ── wrong role ────────────────────────────────────────────────────────────
    def test_unknown_role_on_correct_tenant_returns_false(self):
        u = _user(tenant_id=1, role="unknown_role")
        self.assertFalse(self._v()._can_view(_req(u), _tenant(tid=1)))


# ══════════════════════════════════════════════════════════════════════════════
# OrderHandoffView._sanitize_phone
# ══════════════════════════════════════════════════════════════════════════════

class SanitizePhoneTests(SimpleTestCase):
    """_sanitize_phone: keeps only digit characters."""

    def _v(self):
        return OrderHandoffView()

    def test_digits_only_returned_unchanged(self):
        self.assertEqual(self._v()._sanitize_phone("0661234567"), "0661234567")

    def test_plus_sign_removed(self):
        self.assertEqual(self._v()._sanitize_phone("+212661234567"), "212661234567")

    def test_spaces_removed(self):
        self.assertEqual(self._v()._sanitize_phone("06 61 23 45 67"), "0661234567")

    def test_dashes_removed(self):
        self.assertEqual(self._v()._sanitize_phone("06-61-23-45"), "06612345")

    def test_parentheses_removed(self):
        self.assertEqual(self._v()._sanitize_phone("(0212) 345678"), "0212345678")

    def test_empty_string_returns_empty(self):
        self.assertEqual(self._v()._sanitize_phone(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(self._v()._sanitize_phone(None), "")

    def test_no_digits_returns_empty(self):
        self.assertEqual(self._v()._sanitize_phone("+-()"), "")

    def test_mixed_returns_only_digits(self):
        self.assertEqual(self._v()._sanitize_phone("abc123def456"), "123456")


# ══════════════════════════════════════════════════════════════════════════════
# OrderHandoffSerializer.validate — cross-field delivery rules
# ══════════════════════════════════════════════════════════════════════════════

class OrderHandoffValidateTests(SimpleTestCase):
    """validate: table context bypasses delivery checks; delivery requires address + location."""

    def _s(self):
        return OrderHandoffSerializer()

    def _base_attrs(self, **overrides):
        """Minimal attrs for a table-QR order (always passes)."""
        attrs = {
            "table_slug": "table-1",
            "table_label": "Table 1",
            "fulfillment_type": "",
            "delivery_address": "",
            "delivery_lat": None,
            "delivery_lng": None,
            "delivery_location_url": "",
        }
        attrs.update(overrides)
        return attrs

    # ── table context bypasses all delivery checks ────────────────────────────
    def test_table_slug_bypasses_delivery_checks(self):
        attrs = self._base_attrs(table_slug="table-1", table_label="", fulfillment_type="")
        result = self._s().validate(attrs)
        self.assertIn("table_slug", result)

    def test_table_label_bypasses_delivery_checks(self):
        attrs = self._base_attrs(table_slug="", table_label="Table 1", fulfillment_type="")
        result = self._s().validate(attrs)
        self.assertIn("table_label", result)

    # ── missing fulfillment_type ──────────────────────────────────────────────
    def test_no_table_no_fulfillment_type_raises(self):
        attrs = self._base_attrs(table_slug="", table_label="", fulfillment_type="")
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        self.assertIn("fulfillment_type", str(cm.exception))

    # ── pickup passes without extra fields ───────────────────────────────────
    def test_pickup_without_delivery_fields_passes(self):
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="pickup",
            delivery_address="", delivery_lat=None, delivery_lng=None,
        )
        result = self._s().validate(attrs)
        self.assertEqual(result["fulfillment_type"], "pickup")

    # ── delivery requires address ─────────────────────────────────────────────
    def test_delivery_without_address_raises(self):
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="delivery",
            delivery_address="", delivery_lat=33.5, delivery_lng=-7.6,
        )
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        self.assertIn("delivery_address", str(cm.exception))

    def test_delivery_without_location_raises(self):
        """delivery_address set but no coords and no map URL → raises."""
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="delivery",
            delivery_address="123 Main St",
            delivery_lat=None, delivery_lng=None, delivery_location_url="",
        )
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        self.assertIn("delivery_location_url", str(cm.exception))

    def test_delivery_with_map_url_accepted(self):
        """delivery_address + map URL is valid (no coords needed)."""
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="delivery",
            delivery_address="123 Main St",
            delivery_lat=None, delivery_lng=None,
            delivery_location_url="https://maps.google.com/?q=33.5,-7.6",
        )
        result = self._s().validate(attrs)
        self.assertEqual(result["fulfillment_type"], "delivery")

    def test_delivery_with_coords_accepted(self):
        """delivery_address + coords is valid (no map URL needed)."""
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="delivery",
            delivery_address="123 Main St",
            delivery_lat=33.5, delivery_lng=-7.6, delivery_location_url="",
        )
        result = self._s().validate(attrs)
        self.assertEqual(result["fulfillment_type"], "delivery")

    def test_delivery_lat_without_lng_raises(self):
        """One of lat/lng but not both → partial coords error."""
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="delivery",
            delivery_address="123 Main St",
            delivery_lat=33.5, delivery_lng=None,
            delivery_location_url="",
        )
        with self.assertRaises(ValidationError) as cm:
            self._s().validate(attrs)
        err_str = str(cm.exception)
        self.assertIn("delivery_lat", err_str)

    # ── fulfillment_type normalised to lowercase ──────────────────────────────
    def test_fulfillment_type_lowercased(self):
        attrs = self._base_attrs(
            table_slug="", table_label="", fulfillment_type="PICKUP",
        )
        result = self._s().validate(attrs)
        self.assertEqual(result["fulfillment_type"], "pickup")
