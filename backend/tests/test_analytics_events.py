from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import AnalyticsEventIngestView, AnalyticsEventInputSerializer


class AnalyticsEventSerializerTests(SimpleTestCase):
    def test_category_view_requires_category_slug(self):
        serializer = AnalyticsEventInputSerializer(data={"event_type": "category_view"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("category_slug", serializer.errors)

    def test_dish_view_requires_dish_slug(self):
        serializer = AnalyticsEventInputSerializer(data={"event_type": "dish_view"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("dish_slug", serializer.errors)

    def test_contact_click_event_is_valid(self):
        serializer = AnalyticsEventInputSerializer(
            data={"event_type": "contact_click", "source": "customer_landing"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class AnalyticsEventIngestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_rejects_when_tenant_missing(self):
        req = self.factory.post("/api/analytics/events/", {"event_type": "menu_view"}, format="json")
        response = AnalyticsEventIngestView.as_view()(req)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "tenant_missing")

    @patch("menu.views.AnalyticsEvent.objects.create")
    def test_records_event_for_resolved_tenant(self, create_mock):
        create_mock.return_value = SimpleNamespace(id=42)
        req = self.factory.post(
            "/api/analytics/events/",
            {
                "event_type": "menu_view",
                "path": "/menu",
                "source": "customer_menu",
                "metadata": {"section": "hero"},
            },
            format="json",
        )
        req.tenant = SimpleNamespace(id=1, slug="demo", name="Demo")

        response = AnalyticsEventIngestView.as_view()(req)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["detail"], "event_recorded")
        self.assertEqual(response.data["id"], 42)
        create_mock.assert_called_once()

    @patch("menu.views.AnalyticsEvent.objects.create")
    def test_ignores_public_schema(self, create_mock):
        req = self.factory.post("/api/analytics/events/", {"event_type": "menu_view"}, format="json")
        req.tenant = SimpleNamespace(id=1, slug="main", name="Main", schema_name="public")

        response = AnalyticsEventIngestView.as_view()(req)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["code"], "public_schema_ignored")
        create_mock.assert_not_called()
