"""
Tests for PublicPlanPricingView — GET /api/public/plans/

Unit-level (SimpleTestCase + mocks — no real DB). AllowAny marketing-page
endpoint (Home.vue) showing live plan pricing set by the owner in the admin.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.views import PublicPlanPricingView


class PublicPlanPricingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PublicPlanPricingView.as_view()

    def _get(self):
        req = self.factory.get("/api/public/plans/")
        return self.view(req)

    @patch("sales.views.Plan.objects")
    def test_returns_active_plans(self, mock_plan_objs):
        mock_plan_objs.filter.return_value.order_by.return_value.values.return_value = [
            {
                "code": "starter",
                "price_monthly": Decimal("199.00"),
                "currency": "MAD",
                "billing_period": "monthly",
            },
        ]

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["code"], "starter")
        self.assertEqual(resp.data[0]["price_monthly"], "199.00")
        self.assertEqual(resp.data[0]["currency"], "MAD")
        self.assertEqual(resp.data[0]["billing_period"], "monthly")
        mock_plan_objs.filter.assert_called_once_with(is_active=True)

    @patch("sales.views.Plan.objects")
    def test_null_price_monthly_serializes_to_none_with_defaults(self, mock_plan_objs):
        mock_plan_objs.filter.return_value.order_by.return_value.values.return_value = [
            {"code": "starter", "price_monthly": None, "currency": None, "billing_period": None},
        ]

        resp = self._get()

        row = resp.data[0]
        self.assertIsNone(row["price_monthly"])
        self.assertEqual(row["currency"], "MAD")
        self.assertEqual(row["billing_period"], "monthly")

    @patch("sales.views.Plan.objects")
    def test_cache_control_header_present(self, mock_plan_objs):
        """Small, input-free AllowAny GET — safe to cache publicly for a few minutes
        (pricing only changes when the owner edits it in the Django admin)."""
        mock_plan_objs.filter.return_value.order_by.return_value.values.return_value = []

        resp = self._get()

        self.assertEqual(
            resp["Cache-Control"], "public, max-age=300, stale-while-revalidate=600"
        )
