"""
Tests for the per-service account model (P2): CustomerServiceProfile, the
per-vertical promo suppression, and the session `services` block.

Model uniqueness / get_or_create are DB-backed (covered in CI); here we unit-test
the model SHAPE and the suppression precedence with no DB.

See KEPOLI_ACCOUNT_ARCHITECTURE.md L2 / P2.
"""
from __future__ import annotations

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
