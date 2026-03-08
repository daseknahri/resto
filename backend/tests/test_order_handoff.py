from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OrderHandoffView


class DummyOrderHandoffView(OrderHandoffView):
    test_profile = None
    test_dishes = {}
    test_options = {}
    test_tables = {}
    test_can_preview = False

    def _profile_for_tenant(self, tenant):
        return self.__class__.test_profile

    def _fetch_dishes(self, slugs, can_preview):
        return self.__class__.test_dishes

    def _fetch_options(self, option_ids, can_preview):
        return {opt_id: self.__class__.test_options[opt_id] for opt_id in option_ids if opt_id in self.__class__.test_options}

    def _fetch_active_table_by_slug(self, slug):
        return self.__class__.test_tables.get((slug or "").strip().lower())

    def _can_preview_unpublished(self, tenant):
        return self.__class__.test_can_preview


class OrderHandoffTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.tenant = SimpleNamespace(
            id=1,
            name="Demo Resto",
            plan=SimpleNamespace(can_whatsapp_order=True),
        )
        self.profile = SimpleNamespace(
            is_menu_temporarily_disabled=False,
            menu_disabled_note="",
            is_menu_published=True,
            is_open=True,
            whatsapp="+212600000000",
            phone="",
        )
        DummyOrderHandoffView.test_profile = self.profile
        DummyOrderHandoffView.test_dishes = {
            "burger": SimpleNamespace(slug="burger", name="Burger", price=Decimal("10.00"), currency="USD"),
        }
        DummyOrderHandoffView.test_options = {
            1: SimpleNamespace(id=1, name="Cheese", price_delta=Decimal("2.00"), dish=SimpleNamespace(slug="burger")),
            2: SimpleNamespace(id=2, name="Chili", price_delta=Decimal("1.00"), dish=SimpleNamespace(slug="burger")),
        }
        DummyOrderHandoffView.test_tables = {
            "table-4": SimpleNamespace(slug="table-4", label="Table 4", is_active=True),
        }
        DummyOrderHandoffView.test_can_preview = False

    def _request(self, payload):
        req = self.factory.post("/api/order-handoff/", payload, format="json")
        req.tenant = self.tenant
        return DummyOrderHandoffView.as_view()(req)

    def _non_table_payload(self, **overrides):
        payload = {
            "fulfillment_type": "pickup",
            "customer_name": "John",
            "customer_phone": "+212600000000",
            "items": [{"slug": "burger", "qty": 1}],
        }
        payload.update(overrides)
        return payload

    def test_forbidden_when_plan_disables_whatsapp(self):
        self.tenant.plan = SimpleNamespace(can_whatsapp_order=False)
        response = self._request(self._non_table_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "plan_forbidden")

    def test_unpublished_menu_is_blocked(self):
        self.profile.is_menu_published = False
        response = self._request(self._non_table_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "menu_unpublished")

    def test_temporarily_disabled_menu_is_blocked(self):
        self.profile.is_menu_temporarily_disabled = True
        self.profile.menu_disabled_note = "Maintenance"
        response = self._request(self._non_table_payload())
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "menu_temporarily_disabled")

    def test_closed_restaurant_is_blocked(self):
        self.profile.is_open = False
        response = self._request(self._non_table_payload())
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "restaurant_closed")

    def test_unavailable_item_is_reported(self):
        response = self._request(self._non_table_payload(items=[{"slug": "missing", "qty": 1}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "items_unavailable")
        self.assertEqual(response.data["unavailable_slugs"], ["missing"])

    def test_success_returns_whatsapp_url(self):
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 2}]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("https://wa.me/212600000000?text=", response.data["url"])
        self.assertEqual(response.data["total"], "20.00")
        self.assertEqual(response.data["currency"], "USD")

    def test_table_label_is_included_in_whatsapp_message(self):
        response = self._request(
            {
                "table_label": "4",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["table_label"], "4")
        self.assertIn("Table: 4", response.data["message"])

    def test_invalid_table_label_is_rejected(self):
        response = self._request(
            {
                "table_label": "<script>",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("table_label", response.data)

    def test_table_slug_resolves_active_table_label(self):
        response = self._request(
            {
                "table_slug": "table-4",
                "table_label": "Wrong label",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["table_slug"], "table-4")
        self.assertEqual(response.data["table_label"], "Table 4")
        self.assertIn("Table: Table 4", response.data["message"])

    def test_invalid_table_slug_is_rejected(self):
        response = self._request(
            {
                "table_slug": "missing-table",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "table_unavailable")

    def test_customer_identity_is_included_in_whatsapp_message(self):
        response = self._request(
            {
                "fulfillment_type": "pickup",
                "customer_name": "John",
                "customer_phone": "+212600000000",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["customer_name"], "John")
        self.assertEqual(response.data["customer_phone"], "+212600000000")
        self.assertIn("Customer: John", response.data["message"])
        self.assertIn("Phone: +212600000000", response.data["message"])

    def test_invalid_customer_phone_is_rejected(self):
        response = self._request(
            {
                "fulfillment_type": "pickup",
                "customer_name": "John",
                "customer_phone": "ABC#@@",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("customer_phone", response.data)

    def test_selected_options_are_included_in_total_and_message(self):
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 2, "option_ids": [1, 2]}])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], "26.00")
        self.assertIn("options: Cheese, Chili", response.data["message"])

    def test_invalid_option_for_dish_is_rejected(self):
        DummyOrderHandoffView.test_options = {
            9: SimpleNamespace(id=9, name="Wrong", price_delta=Decimal("1.00"), dish=SimpleNamespace(slug="sushi"))
        }
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 1, "option_ids": [9]}])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_options")
        self.assertEqual(response.data["invalid_option_ids"], [9])

    def test_mixed_currency_cart_is_rejected(self):
        DummyOrderHandoffView.test_dishes = {
            "burger": SimpleNamespace(slug="burger", name="Burger", price=Decimal("10.00"), currency="USD"),
            "sushi": SimpleNamespace(slug="sushi", name="Sushi", price=Decimal("12.00"), currency="EUR"),
        }
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 1}, {"slug": "sushi", "qty": 1}])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "mixed_currency")

    def test_non_table_order_requires_fulfillment_and_customer_identity(self):
        response = self._request({"items": [{"slug": "burger", "qty": 1}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fulfillment_type", response.data)
        self.assertIn("customer_name", response.data)
        self.assertIn("customer_phone", response.data)

    def test_delivery_order_requires_address_and_location(self):
        response = self._request(
            self._non_table_payload(
                fulfillment_type="delivery",
                delivery_address="",
                delivery_location_url="",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_address", response.data)
        self.assertIn("delivery_location_url", response.data)

    def test_delivery_order_accepts_lat_lng_location(self):
        response = self._request(
            self._non_table_payload(
                fulfillment_type="delivery",
                delivery_address="Main street 1",
                delivery_lat=33.5731,
                delivery_lng=-7.5898,
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["fulfillment_type"], "delivery")
        self.assertIn("Delivery address: Main street 1", response.data["message"])
