"""
Tests for the per-service account model (P2): CustomerServiceProfile, the
per-vertical promo suppression, and the session `services` block.

Model uniqueness / get_or_create are DB-backed (covered in CI); here we unit-test
the model SHAPE and the suppression precedence with no DB.

See KEPOLI_ACCOUNT_ARCHITECTURE.md L2 / P2.
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


class TestCustomerServiceProfileModel(SimpleTestCase):
    def test_fields_and_defaults(self):
        from accounts.models import CustomerServiceProfile

        names = {f.name for f in CustomerServiceProfile._meta.get_fields()}
        for expected in ("customer", "vertical", "notify_updates", "notify_promotions", "default_address"):
            self.assertIn(expected, names)
        self.assertTrue(CustomerServiceProfile._meta.get_field("notify_promotions").default)
        self.assertTrue(CustomerServiceProfile._meta.get_field("notify_updates").default)

    def test_unique_customer_vertical_constraint(self):
        from accounts.models import CustomerServiceProfile

        constraint_names = {c.name for c in CustomerServiceProfile._meta.constraints}
        self.assertIn("customerserviceprofile_customer_vertical_uniq", constraint_names)


class TestVerticalMutedCustomerIds(SimpleTestCase):
    """P2b: per-vertical promo suppression at the audience level."""

    def test_none_tenant_returns_empty(self):
        from accounts.push import vertical_muted_customer_ids

        self.assertEqual(vertical_muted_customer_ids(None), set())

    @patch("accounts.models.CustomerServiceProfile")
    @patch("accounts.verticals.vertical_for_tenant_id")
    def test_unresolvable_vertical_returns_empty(self, mock_vert, mock_csp):
        from accounts.push import vertical_muted_customer_ids

        mock_vert.return_value = None
        self.assertEqual(vertical_muted_customer_ids(5), set())
        mock_csp.objects.filter.assert_not_called()

    @patch("accounts.models.CustomerServiceProfile")
    @patch("accounts.verticals.vertical_for_tenant_id")
    def test_returns_muted_ids_for_vertical(self, mock_vert, mock_csp):
        from accounts.push import vertical_muted_customer_ids

        mock_vert.return_value = "food"
        mock_csp.objects.filter.return_value.values_list.return_value = [3, 7]
        self.assertEqual(vertical_muted_customer_ids(5), {3, 7})
        mock_csp.objects.filter.assert_called_once_with(
            vertical="food", notify_promotions=False
        )


class TestCustomerServicesView(SimpleTestCase):
    """P2c: per-vertical activity summary endpoint."""

    def _req(self, customer_id=1):
        req = MagicMock()
        req.session = {"customer_id": customer_id} if customer_id else {}
        return req

    def test_unauthenticated_returns_401(self):
        from accounts.views import CustomerServicesView

        resp = CustomerServicesView().get(self._req(customer_id=None))
        self.assertEqual(resp.status_code, 401)

    @override_settings(
        VERTICALS_ENABLED=frozenset({"food", "shops", "pharmacy", "courier", "driver"})
    )
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.RideRequest")
    @patch("accounts.models.CustomerOrderRef")
    def test_summary_aggregates_orders_and_rides(self, mock_ref, mock_ride, mock_djob):
        from accounts.views import CustomerServicesView

        d1 = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
        d2 = datetime.datetime(2026, 6, 10, tzinfo=datetime.timezone.utc)
        mock_ref.objects.filter.return_value.exclude.return_value.values.return_value.annotate.return_value = [
            {"vertical": "food", "count": 3, "last": d2},
            {"vertical": "pharmacy", "count": 1, "last": d1},
        ]
        mock_ride.objects.filter.return_value.values.return_value.annotate.return_value = [
            {"kind": "package", "count": 2, "last": d2},
        ]
        mock_djob.objects.filter.return_value.aggregate.return_value = {"count": 0, "last": None}

        resp = CustomerServicesView().get(self._req(1))
        svc = resp.data["services"]

        self.assertEqual(svc["food"]["count"], 3)
        self.assertEqual(svc["food"]["last_activity"], d2.isoformat())
        self.assertEqual(svc["pharmacy"]["count"], 1)
        self.assertEqual(svc["courier"]["count"], 2)  # package -> courier
        self.assertEqual(svc["rides"]["count"], 0)
        self.assertTrue(svc["food"]["enabled"])
        self.assertFalse(svc["rides"]["enabled"])  # rides not in the enabled set

    @override_settings(VERTICALS_ENABLED=frozenset({"food", "driver"}))
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.RideRequest")
    @patch("accounts.models.CustomerOrderRef")
    def test_driver_count_from_delivered_jobs(self, mock_ref, mock_ride, mock_djob):
        from accounts.views import CustomerServicesView

        d = datetime.datetime(2026, 6, 5, tzinfo=datetime.timezone.utc)
        mock_ref.objects.filter.return_value.exclude.return_value.values.return_value.annotate.return_value = []
        mock_ride.objects.filter.return_value.values.return_value.annotate.return_value = []
        mock_djob.objects.filter.return_value.aggregate.return_value = {"count": 5, "last": d}

        resp = CustomerServicesView().get(self._req(1))
        svc = resp.data["services"]
        self.assertEqual(svc["driver"]["count"], 5)
        self.assertEqual(svc["driver"]["last_activity"], d.isoformat())


class TestCustomerServiceProfilesView(SimpleTestCase):
    """P3: read/update per-service notification preferences."""

    def _req(self, customer_id=1, data=None):
        req = MagicMock()
        req.session = {"customer_id": customer_id} if customer_id else {}
        req.data = data or {}
        return req

    def test_get_unauthenticated_401(self):
        from accounts.views import CustomerServiceProfilesView

        resp = CustomerServiceProfilesView().get(self._req(customer_id=None))
        self.assertEqual(resp.status_code, 401)

    @patch("accounts.models.CustomerServiceProfile")
    @patch("accounts.models.Customer")
    def test_get_falls_back_to_global(self, mock_cust, mock_csp):
        from accounts.views import CustomerServiceProfilesView

        mock_cust.objects.get.return_value = MagicMock(
            notify_order_updates=True, notify_promotions=False
        )
        mock_csp.objects.filter.return_value = []  # no per-service rows yet
        resp = CustomerServiceProfilesView().get(self._req(1))
        sp = resp.data["service_profiles"]
        self.assertFalse(sp["food"]["customized"])
        self.assertTrue(sp["food"]["notify_updates"])       # global default
        self.assertFalse(sp["food"]["notify_promotions"])   # global default

    def test_patch_invalid_vertical_400(self):
        from accounts.views import CustomerServiceProfilesView

        resp = CustomerServiceProfilesView().patch(self._req(1, {"vertical": "spaceport"}))
        self.assertEqual(resp.status_code, 400)

    @patch("accounts.models.CustomerServiceProfile")
    def test_patch_updates_profile(self, mock_csp):
        from accounts.views import CustomerServiceProfilesView

        profile = MagicMock(notify_updates=True, notify_promotions=True)
        mock_csp.get_or_create_for.return_value = profile
        resp = CustomerServiceProfilesView().patch(
            self._req(1, {"vertical": "food", "notify_promotions": False})
        )
        self.assertFalse(profile.notify_promotions)
        profile.save.assert_called_once()
        self.assertEqual(resp.data["vertical"], "food")

    @patch("accounts.models.SavedAddress")
    @patch("accounts.models.CustomerServiceProfile")
    def test_patch_default_address_validates_ownership(self, mock_csp, mock_addr):
        from accounts.views import CustomerServiceProfilesView

        profile = MagicMock(notify_updates=True, notify_promotions=True, default_address_id=None)
        mock_csp.get_or_create_for.return_value = profile

        # Address NOT owned by this customer → 400, nothing saved.
        mock_addr.objects.filter.return_value.exists.return_value = False
        resp = CustomerServiceProfilesView().patch(
            self._req(1, {"vertical": "food", "default_address_id": 99})
        )
        self.assertEqual(resp.status_code, 400)
        profile.save.assert_not_called()

        # Address owned → set + persisted.
        mock_addr.objects.filter.return_value.exists.return_value = True
        CustomerServiceProfilesView().patch(
            self._req(1, {"vertical": "food", "default_address_id": 7})
        )
        self.assertEqual(profile.default_address_id, 7)
