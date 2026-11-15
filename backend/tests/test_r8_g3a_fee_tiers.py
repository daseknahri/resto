"""Run 8 G3a — A2-11: fee tiers validated client + server.

Server: _validate_fee_tiers (shared by zone POST + PATCH) — each tier needs a
fee >= 0 (missing fee used to silently become a 0.00 charge) and an optional
km_up_to > 0 or null; non-numeric values are 400 (they used to 500 in
compute_fee). compute_fee skips malformed legacy tiers instead of raising.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import DeliveryZone, User
from accounts.views import (
    AdminDeliveryZoneDetailView,
    AdminDeliveryZoneListCreateView,
    _validate_fee_tiers,
)


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _sc_mock():
    ctx = MagicMock()
    ctx.__enter__ = lambda s: None
    ctx.__exit__ = lambda s, *a: None
    return ctx


class ValidateFeeTiersTests(SimpleTestCase):
    def test_valid_tiers_pass_and_coerce(self):
        tiers, err = _validate_fee_tiers([
            {"km_up_to": 3, "fee": 2.5},
            {"km_up_to": None, "fee": "6"},
            {"fee": "10", "min_km": 0},  # legacy shape: absent km_up_to = catch-all
        ])
        self.assertIsNone(err)
        self.assertEqual(tiers, [
            {"km_up_to": 3.0, "fee": 2.5},
            {"km_up_to": None, "fee": 6.0},
            {"km_up_to": None, "fee": 10.0},
        ])

    def test_empty_list_is_valid(self):
        tiers, err = _validate_fee_tiers([])
        self.assertIsNone(err)
        self.assertEqual(tiers, [])

    def test_missing_fee_rejected(self):
        _, err = _validate_fee_tiers([{"km_up_to": 3}])
        self.assertIn("fee", err)

    def test_non_numeric_fee_rejected(self):
        _, err = _validate_fee_tiers([{"km_up_to": 3, "fee": "abc"}])
        self.assertIn("fee", err)

    def test_negative_fee_rejected(self):
        _, err = _validate_fee_tiers([{"fee": -1}])
        self.assertIn("fee", err)

    def test_zero_km_up_to_rejected(self):
        _, err = _validate_fee_tiers([{"km_up_to": 0, "fee": 5}])
        self.assertIn("km_up_to", err)

    def test_non_numeric_km_up_to_rejected(self):
        _, err = _validate_fee_tiers([{"km_up_to": "far", "fee": 5}])
        self.assertIn("km_up_to", err)

    def test_non_list_rejected(self):
        _, err = _validate_fee_tiers({"fee": 5})
        self.assertIsNotNone(err)

    def test_non_dict_tier_rejected(self):
        _, err = _validate_fee_tiers(["not-a-tier"])
        self.assertIsNotNone(err)

    def test_bool_fee_rejected(self):
        _, err = _validate_fee_tiers([{"fee": True}])
        self.assertIn("fee", err)


class ComputeFeeHardeningTests(SimpleTestCase):
    def test_valid_tiers_still_price(self):
        z = DeliveryZone(fee_tiers=[{"km_up_to": 3, "fee": 2.5}, {"km_up_to": None, "fee": 6.0}])
        self.assertEqual(z.compute_fee(2), 2.5)
        self.assertEqual(z.compute_fee(10), 6.0)

    def test_malformed_tiers_skipped_not_raised(self):
        z = DeliveryZone(fee_tiers=[
            {"km_up_to": 3},                    # missing fee
            {"km_up_to": 7, "fee": "abc"},      # non-numeric fee
            {"km_up_to": None, "fee": 6.0},     # the good one
        ])
        self.assertEqual(z.compute_fee(2), 6.0)

    def test_all_bad_tiers_return_zero(self):
        z = DeliveryZone(fee_tiers=[{"km_up_to": 3}, {"fee": "abc"}])
        self.assertEqual(z.compute_fee(2), 0.0)


class FeeTiersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.list_view = AdminDeliveryZoneListCreateView.as_view()
        self.detail_view = AdminDeliveryZoneDetailView.as_view()

    def _polygon(self):
        return [{"lat": 33.5, "lng": -7.6}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}]

    def test_post_missing_fee_returns_400_without_creating(self):
        req = self.factory.post("/api/admin/delivery-zones/", {
            "name": "Downtown", "city": "Casablanca", "polygon": self._polygon(),
            "fee_tiers": [{"km_up_to": 3}],
        }, format="json")
        req.user = _admin()
        with patch("accounts.models.DeliveryZone") as mock_dz, \
             patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.list_view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_dz.objects.create.assert_not_called()

    def test_patch_non_numeric_fee_returns_400_without_saving(self):
        zone = MagicMock()
        zone.id = 1
        zone.name = "Downtown"
        zone.city = "Casablanca"
        zone.fee_tiers = []
        zone.is_active = True
        req = self.factory.patch("/api/admin/delivery-zones/1/", {
            "fee_tiers": [{"km_up_to": 3, "fee": "abc"}],
        }, format="json")
        req.user = _admin()
        with patch("accounts.models.DeliveryZone") as mock_dz, \
             patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            mock_dz.objects.get.return_value = zone
            resp = self.detail_view(req, zone_id=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        zone.save.assert_not_called()
