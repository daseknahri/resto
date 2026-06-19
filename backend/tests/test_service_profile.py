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
    @patch("accounts.models.RideRequest")
    @patch("accounts.models.CustomerOrderRef")
    def test_summary_aggregates_orders_and_rides(self, mock_ref, mock_ride):
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

        resp = CustomerServicesView().get(self._req(1))
        svc = resp.data["services"]

        self.assertEqual(svc["food"]["count"], 3)
        self.assertEqual(svc["food"]["last_activity"], d2.isoformat())
        self.assertEqual(svc["pharmacy"]["count"], 1)
        self.assertEqual(svc["courier"]["count"], 2)  # package -> courier
        self.assertEqual(svc["rides"]["count"], 0)
        self.assertTrue(svc["food"]["enabled"])
        self.assertFalse(svc["rides"]["enabled"])  # rides not in the enabled set
