"""
Tests for the per-service account model (P2): CustomerServiceProfile, the
per-vertical promo suppression, and the session `services` block.

Model uniqueness / get_or_create are DB-backed (covered in CI); here we unit-test
the model SHAPE and the suppression precedence with no DB.

See KEPOLI_ACCOUNT_ARCHITECTURE.md L2 / P2.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase


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
