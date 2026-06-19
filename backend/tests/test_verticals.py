"""
Unit tests for the canonical vertical taxonomy (accounts/verticals.py).

See KEPOLI_ACCOUNT_ARCHITECTURE.md §3. No DB needed.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from accounts import verticals as V


class TestBusinessTypeMapping(SimpleTestCase):
    def test_food_types(self):
        self.assertEqual(V.vertical_for_business_type("restaurant"), V.FOOD)
        self.assertEqual(V.vertical_for_business_type("cafe"), V.FOOD)

    def test_shop_types(self):
        for bt in ("bakery", "grocery", "retail"):
            self.assertEqual(V.vertical_for_business_type(bt), V.SHOPS, bt)

    def test_pharmacy_is_its_own_vertical(self):
        # pharmacy is a standalone token, NOT folded into shops.
        self.assertEqual(V.vertical_for_business_type("pharmacy"), V.PHARMACY)

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(V.vertical_for_business_type("  Restaurant "), V.FOOD)
        self.assertEqual(V.vertical_for_business_type("PHARMACY"), V.PHARMACY)

    def test_blank_and_unknown_default_to_food(self):
        self.assertEqual(V.vertical_for_business_type(""), V.FOOD)
        self.assertEqual(V.vertical_for_business_type(None), V.FOOD)
        self.assertEqual(V.vertical_for_business_type("spaceport"), V.FOOD)


class TestRideKindMapping(SimpleTestCase):
    def test_ride_kind(self):
        self.assertEqual(V.vertical_for_ride_kind("ride"), V.RIDES)

    def test_package_kind(self):
        self.assertEqual(V.vertical_for_ride_kind("package"), V.COURIER)

    def test_blank_defaults_to_rides(self):
        self.assertEqual(V.vertical_for_ride_kind(""), V.RIDES)
        self.assertEqual(V.vertical_for_ride_kind(None), V.RIDES)


class TestEnabledVerticals(SimpleTestCase):
    @override_settings(VERTICALS_ENABLED=frozenset({"food", "shops", "driver"}))
    def test_is_vertical_enabled(self):
        self.assertTrue(V.is_vertical_enabled(V.FOOD))
        self.assertTrue(V.is_vertical_enabled(V.DRIVER))
        self.assertFalse(V.is_vertical_enabled(V.RIDES))

    @override_settings(VERTICALS_ENABLED=frozenset({"food"}))
    def test_enabled_verticals_returns_frozenset(self):
        self.assertEqual(V.enabled_verticals(), frozenset({"food"}))


class TestTaxonomyShape(SimpleTestCase):
    def test_all_verticals_complete(self):
        self.assertEqual(
            set(V.ALL_VERTICALS),
            {"food", "shops", "pharmacy", "rides", "courier", "driver"},
        )


class TestVerticalForTenantId(SimpleTestCase):
    def test_none_tenant_returns_none(self):
        self.assertIsNone(V.vertical_for_tenant_id(None))
        self.assertIsNone(V.vertical_for_tenant_id(0))

    @patch("tenancy.models.Profile")
    def test_resolves_business_type(self, mock_profile):
        mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = "pharmacy"
        self.assertEqual(V.vertical_for_tenant_id(7), V.PHARMACY)

    @patch("tenancy.models.Profile")
    def test_missing_profile_returns_none(self, mock_profile):
        # No Profile row for this tenant → None (caller tags the row global), NOT a guess.
        mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = None
        self.assertIsNone(V.vertical_for_tenant_id(7))
