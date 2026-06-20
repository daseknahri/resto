"""Tests for the business_type capability seam (Phase 0 enforcement).

Covers the decision logic that all server-side guards delegate to:
- Profile.capabilities derived per business_type
- tenant_capability_enabled() safe (non-breaking) defaults

Pure unit tests (no DB): Profile is instantiated unsaved; .capabilities only
reads self.business_type. Run with DJANGO_DEBUG=True.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

    def test_pharmacy_disables_all_restaurant_features(self):
        caps = Profile(business_type="pharmacy").capabilities
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


    def test_pharmacy_business_type_value(self):
        # Sanity-check: the choices constant resolves correctly.
        self.assertEqual(Profile.BusinessType.PHARMACY, "pharmacy")

    def test_pharmacy_has_correct_business_type_label(self):
        self.assertEqual(
            Profile.BusinessType.PHARMACY.label, "Pharmacy / Parapharmacie"
        )


class TenantCapabilityHelperTests(SimpleTestCase):
    def test_none_tenant_is_allowed(self):
        # Missing tenant must not block (other guards handle auth/tenant presence).
        self.assertTrue(tenant_capability_enabled(None, "dine_in"))
        self.assertTrue(tenant_capability_enabled(None, "tables"))


class CapabilityGateEnforcementTests(SimpleTestCase):
    """The view-level guards that turn a disabled capability into a 403 / empty
    queryset for a shop tenant. The decision logic is covered above; this locks in
    that the guards actually FIRE (regression cover for the audit's API gates).
    Pure unit tests — tenant_capability_enabled is patched, so no DB."""

    def test_reservation_list_returns_403_for_a_shop(self):
        from sales.views import OwnerReservationListView
        req = SimpleNamespace(tenant=MagicMock(), query_params={})
        with patch("tenancy.capabilities.tenant_capability_enabled", return_value=False):
            resp = OwnerReservationListView().get(req)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data.get("code"), "reservations_unavailable")

    def test_waiter_call_list_returns_403_for_a_shop(self):
        from menu.waiter_views import OwnerWaiterCallListView
        req = SimpleNamespace(tenant=MagicMock())
        with patch("tenancy.capabilities.tenant_capability_enabled", return_value=False):
            resp = OwnerWaiterCallListView().get(req)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data.get("code"), "waiter_unavailable")

    def test_table_queryset_is_empty_for_a_shop(self):
        from menu.views import TableLinkViewSet
        vs = TableLinkViewSet()
        vs.request = SimpleNamespace(tenant=MagicMock())
        with patch("tenancy.capabilities.tenant_capability_enabled", return_value=False):
            qs = vs.get_queryset()
        self.assertTrue(qs.query.is_empty())  # none() — no rows, no DB hit

    def test_table_queryset_passes_through_when_tables_enabled(self):
        from menu.views import TableLinkViewSet
        vs = TableLinkViewSet()
        vs.request = SimpleNamespace(tenant=MagicMock())
        with patch("tenancy.capabilities.tenant_capability_enabled", return_value=True):
            qs = vs.get_queryset()
        self.assertFalse(qs.query.is_empty())  # the real queryset, not the empty marker
