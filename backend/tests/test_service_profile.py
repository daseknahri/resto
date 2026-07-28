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
from rest_framework.test import APIRequestFactory, force_authenticate


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
    """P2c: per-vertical activity summary endpoint.

    RISK IDENTITY-1: this view now authenticates via CustomerSessionAuthentication +
    IsCustomer, so it must be driven through as_view()/dispatch (not a bare instance
    .get() call) for the auth gate to run at all — force_authenticate injects a real
    Customer principal, matching the production auth path.
    """

    def setUp(self):
        from accounts.views import CustomerServicesView

        self.factory = APIRequestFactory()
        self.view = CustomerServicesView.as_view()

    def _req(self, customer_id=1):
        from accounts.models import Customer

        req = self.factory.get("/api/customer/services/")
        req.session = {"customer_id": customer_id} if customer_id else {}
        if customer_id:
            force_authenticate(req, user=Customer(id=customer_id))
        return req

    def test_unauthenticated_returns_401(self):
        resp = self.view(self._req(customer_id=None))
        self.assertEqual(resp.status_code, 401)

    @override_settings(
        VERTICALS_ENABLED=frozenset({"food", "shops", "pharmacy", "courier", "driver"})
    )
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.RideRequest")
    @patch("accounts.models.CustomerOrderRef")
    def test_summary_aggregates_orders_and_rides(self, mock_ref, mock_ride, mock_djob):
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

        resp = self.view(self._req(1))
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
        d = datetime.datetime(2026, 6, 5, tzinfo=datetime.timezone.utc)
        mock_ref.objects.filter.return_value.exclude.return_value.values.return_value.annotate.return_value = []
        mock_ride.objects.filter.return_value.values.return_value.annotate.return_value = []
        mock_djob.objects.filter.return_value.aggregate.return_value = {"count": 5, "last": d}

        resp = self.view(self._req(1))
        svc = resp.data["services"]
        self.assertEqual(svc["driver"]["count"], 5)
        self.assertEqual(svc["driver"]["last_activity"], d.isoformat())


class TestCustomerActiveItemsView(SimpleTestCase):
    """Super-app resume rail: active order / ride / package aggregator.

    RISK IDENTITY-1: driven through as_view()/dispatch (not a bare instance .get()
    call) so the CustomerSessionAuthentication + IsCustomer gate actually runs.
    """

    def setUp(self):
        from accounts.views import CustomerActiveItemsView

        self.factory = APIRequestFactory()
        self.view = CustomerActiveItemsView.as_view()

    def _req(self, customer_id=1):
        from accounts.models import Customer

        req = self.factory.get("/api/customer/active-items/")
        req.session = {"customer_id": customer_id} if customer_id else {}
        if customer_id:
            force_authenticate(req, user=Customer(id=customer_id))
        return req

    def test_unauthenticated_returns_401(self):
        resp = self.view(self._req(customer_id=None))
        self.assertEqual(resp.status_code, 401)

    @patch("accounts.models.RideRequest")
    @patch("accounts.models.CustomerOrderRef")
    def test_aggregates_active_order_ride_package(self, mock_ref, mock_ride):
        created = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)

        order = MagicMock()
        order.order_number = "A123"
        order.restaurant_name = "Pizza Place"
        order.restaurant_slug = "pizza-place"
        order.status = "preparing"
        order.fulfillment_type = "delivery"
        order.total = "85.00"
        order.currency = "MAD"
        order.vertical = "food"
        order.order_created_at = created
        mock_ref.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [order]

        # RideRequest.TERMINAL_STATUSES / Kind are read off the patched class — set them.
        mock_ride.TERMINAL_STATUSES = {"completed", "cancelled"}
        mock_ride.Kind.RIDE = "ride"
        mock_ride.Kind.PACKAGE = "package"

        ride = MagicMock()
        ride.pk = 7
        ride.kind = "ride"
        ride.status = "accepted"
        ride.pickup_address = "Pickup St"
        ride.dropoff_address = "Dropoff Ave"
        ride.fare = "40.00"
        ride.created_at = created
        # filter().exclude().order_by().first() — ride for first call, None for package.
        chain = mock_ride.objects.filter.return_value.exclude.return_value.order_by.return_value
        chain.first.side_effect = [ride, None]

        resp = self.view(self._req(1))
        self.assertEqual(len(resp.data["orders"]), 1)
        self.assertEqual(resp.data["orders"][0]["order_number"], "A123")
        self.assertEqual(resp.data["orders"][0]["status"], "preparing")
        self.assertIsNotNone(resp.data["ride"])
        self.assertEqual(resp.data["ride"]["status"], "accepted")
        self.assertEqual(resp.data["ride"]["dropoff_address"], "Dropoff Ave")
        self.assertIsNone(resp.data["package"])


class TestSerializeCustomerRoleFlags(SimpleTestCase):
    """Additive read-only role flags on the customer session serializer."""

    def _customer(self, **over):
        c = MagicMock()
        c.pk = 1
        c.email = over.get("email", "")
        c.email_verified = over.get("email_verified", False)
        c.is_driver = over.get("is_driver", False)
        c.driver_approved = over.get("driver_approved", False)
        c.is_driver_online = False
        c.birthday = None
        # Numeric / string fields used by the serializer
        c.wallet_balance = "0"
        c.loyalty_points = 0
        c.lifetime_loyalty_points = 0
        c.locale = "en"
        c.referral_code = ""
        return c

    def test_driver_approved_flag_passthrough(self):
        from accounts.views import _serialize_customer

        data = _serialize_customer(self._customer(is_driver=True, driver_approved=True))
        self.assertTrue(data["is_driver"])
        self.assertTrue(data["driver_approved"])

    @patch("accounts.models.User")
    def test_has_tenant_false_when_email_unverified(self, mock_user):
        from accounts.views import _serialize_customer

        data = _serialize_customer(
            self._customer(email="owner@shop.com", email_verified=False)
        )
        self.assertFalse(data["has_tenant"])
        self.assertFalse(data["is_staff"])
        mock_user.objects.filter.assert_not_called()

    @patch("accounts.models.User")
    def test_has_tenant_true_when_verified_email_matches_tenant_user(self, mock_user):
        from accounts.views import _serialize_customer

        mock_user.objects.filter.return_value.exists.return_value = True
        data = _serialize_customer(
            self._customer(email="owner@shop.com", email_verified=True)
        )
        self.assertTrue(data["has_tenant"])
        self.assertTrue(data["is_staff"])


class TestCustomerServiceProfilesView(SimpleTestCase):
    """P3: read/update per-service notification preferences.

    RISK IDENTITY-1: this view now authenticates via CustomerSessionAuthentication +
    IsCustomer, so it must be driven through as_view()/dispatch (not a bare instance
    .get()/.patch() call) for the auth gate to run at all — force_authenticate
    injects a real Customer principal, matching the production auth path.
    """

    def setUp(self):
        from accounts.views import CustomerServiceProfilesView

        self.factory = APIRequestFactory()
        self.view = CustomerServiceProfilesView.as_view()

    def _get(self, customer=None):
        req = self.factory.get("/api/customer/service-profiles/")
        req.session = {"customer_id": customer.id} if customer is not None else {}
        if customer is not None:
            force_authenticate(req, user=customer)
        return self.view(req)

    def _patch(self, data, customer=None):
        req = self.factory.patch("/api/customer/service-profiles/", data, format="json")
        req.session = {"customer_id": customer.id} if customer is not None else {}
        if customer is not None:
            force_authenticate(req, user=customer)
        return self.view(req)

    def test_get_unauthenticated_401(self):
        resp = self._get(customer=None)
        self.assertEqual(resp.status_code, 401)

    @patch("accounts.models.CustomerServiceProfile")
    def test_get_falls_back_to_global(self, mock_csp):
        from accounts.models import Customer

        customer = Customer(id=1, notify_order_updates=True, notify_promotions=False)
        mock_csp.objects.filter.return_value = []  # no per-service rows yet
        resp = self._get(customer=customer)
        sp = resp.data["service_profiles"]
        self.assertFalse(sp["food"]["customized"])
        self.assertTrue(sp["food"]["notify_updates"])       # global default
        self.assertFalse(sp["food"]["notify_promotions"])   # global default

    def test_patch_invalid_vertical_400(self):
        from accounts.models import Customer

        resp = self._patch({"vertical": "spaceport"}, customer=Customer(id=1))
        self.assertEqual(resp.status_code, 400)

    @patch("accounts.models.CustomerServiceProfile")
    def test_patch_updates_profile(self, mock_csp):
        from accounts.models import Customer

        profile = MagicMock(notify_updates=True, notify_promotions=True)
        mock_csp.get_or_create_for.return_value = profile
        resp = self._patch(
            {"vertical": "food", "notify_promotions": False}, customer=Customer(id=1)
        )
        self.assertFalse(profile.notify_promotions)
        profile.save.assert_called_once()
        self.assertEqual(resp.data["vertical"], "food")

    @patch("accounts.models.SavedAddress")
    @patch("accounts.models.CustomerServiceProfile")
    def test_patch_default_address_validates_ownership(self, mock_csp, mock_addr):
        from accounts.models import Customer

        profile = MagicMock(notify_updates=True, notify_promotions=True, default_address_id=None)
        mock_csp.get_or_create_for.return_value = profile

        # Address NOT owned by this customer → 400, nothing saved.
        mock_addr.objects.filter.return_value.exists.return_value = False
        resp = self._patch(
            {"vertical": "food", "default_address_id": 99}, customer=Customer(id=1)
        )
        self.assertEqual(resp.status_code, 400)
        profile.save.assert_not_called()

        # Address owned → set + persisted.
        mock_addr.objects.filter.return_value.exists.return_value = True
        self._patch(
            {"vertical": "food", "default_address_id": 7}, customer=Customer(id=1)
        )
        self.assertEqual(profile.default_address_id, 7)
