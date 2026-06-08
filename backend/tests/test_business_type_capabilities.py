"""Tests for the business_type capability seam (Phase 0 enforcement).

Covers the decision logic that all server-side guards delegate to:
- Profile.capabilities derived per business_type
- tenant_capability_enabled() safe (non-breaking) defaults

Pure unit tests (no DB): Profile is instantiated unsaved; .capabilities only
reads self.business_type. Run with DJANGO_DEBUG=True.
"""

from django.test import SimpleTestCase

from tenancy.models import Profile
from tenancy.capabilities import tenant_capability_enabled

CAP_KEYS = ("tables", "dine_in", "waiter", "kitchen", "reservations")


class ProfileCapabilitiesTests(SimpleTestCase):
    def test_restaurant_has_all_capabilities(self):
        caps = Profile(business_type="restaurant").capabilities
        self.assertTrue(all(caps[k] for k in CAP_KEYS))

    def test_cafe_has_all_capabilities(self):
        caps = Profile(business_type="cafe").capabilities
        self.assertTrue(all(caps[k] for k in CAP_KEYS))

    def test_retail_disables_all_restaurant_features(self):
        caps = Profile(business_type="retail").capabilities
        self.assertFalse(any(caps[k] for k in CAP_KEYS))

    def test_grocery_disables_all_restaurant_features(self):
        caps = Profile(business_type="grocery").capabilities
        self.assertFalse(any(caps[k] for k in CAP_KEYS))

    def test_bakery_keeps_only_kitchen(self):
        caps = Profile(business_type="bakery").capabilities
        self.assertTrue(caps["kitchen"])
        self.assertFalse(caps["tables"])
        self.assertFalse(caps["dine_in"])
        self.assertFalse(caps["waiter"])
        self.assertFalse(caps["reservations"])

    def test_default_business_type_is_restaurant(self):
        # An unsaved Profile uses the field default — a fresh tenant is a restaurant.
        self.assertEqual(Profile().business_type, "restaurant")
        self.assertTrue(all(Profile().capabilities[k] for k in CAP_KEYS))

    def test_unknown_business_type_falls_back_to_full_set(self):
        # Never silently downgrade an existing tenant on an unrecognised value.
        caps = Profile(business_type="something_new").capabilities
        self.assertTrue(all(caps[k] for k in CAP_KEYS))

    def test_capabilities_returns_independent_copy(self):
        # Mutating one profile's dict must not poison the shared class map.
        caps = Profile(business_type="restaurant").capabilities
        caps["tables"] = False
        self.assertTrue(Profile(business_type="restaurant").capabilities["tables"])


class TenantCapabilityHelperTests(SimpleTestCase):
    def test_none_tenant_is_allowed(self):
        # Missing tenant must not block (other guards handle auth/tenant presence).
        self.assertTrue(tenant_capability_enabled(None, "dine_in"))
        self.assertTrue(tenant_capability_enabled(None, "tables"))
