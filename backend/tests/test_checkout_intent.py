from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import CheckoutIntentView


class DummyCheckoutIntentView(CheckoutIntentView):
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


class CheckoutIntentTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.tenant = SimpleNamespace(
            id=1,
            name="Demo Resto",
            plan=SimpleNamespace(can_checkout=True),
        )
        self.profile = SimpleNamespace(
            is_menu_temporarily_disabled=False,
            menu_disabled_note="",
            is_menu_published=True,
            is_open=True,
            whatsapp="+212600000000",
            phone="",
        )
        DummyCheckoutIntentView.test_profile = self.profile
        DummyCheckoutIntentView.test_dishes = {
            "burger": SimpleNamespace(slug="burger", name="Burger", price=Decimal("10.00"), currency="USD"),
        }
        DummyCheckoutIntentView.test_options = {
            1: SimpleNamespace(id=1, name="Cheese", price_delta=Decimal("2.00"), dish=SimpleNamespace(slug="burger"))
        }
        DummyCheckoutIntentView.test_tables = {
            "table-4": SimpleNamespace(slug="table-4", label="Table 4", is_active=True),
        }
        DummyCheckoutIntentView.test_can_preview = False

    def _request(self, payload):
        req = self.factory.post("/api/checkout-intent/", payload, format="json")
        req.tenant = self.tenant
        return DummyCheckoutIntentView.as_view()(req)

    def _non_table_payload(self, **overrides):
        payload = {
            "fulfillment_type": "pickup",
            "customer_name": "John",
            "customer_phone": "+212600000000",
            "items": [{"slug": "burger", "qty": 1}],
        }
        payload.update(overrides)
        return payload

    def test_forbidden_when_plan_disables_checkout(self):
        self.tenant.plan = SimpleNamespace(can_checkout=False)
        response = self._request(self._non_table_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "plan_forbidden_checkout")

    def test_unavailable_item_is_reported(self):
        response = self._request(self._non_table_payload(items=[{"slug": "missing", "qty": 1}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "items_unavailable")

    def test_mixed_currency_cart_is_rejected(self):
        DummyCheckoutIntentView.test_dishes = {
            "burger": SimpleNamespace(slug="burger", name="Burger", price=Decimal("10.00"), currency="USD"),
            "sushi": SimpleNamespace(slug="sushi", name="Sushi", price=Decimal("12.00"), currency="EUR"),
        }
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 1}, {"slug": "sushi", "qty": 1}])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "mixed_currency")

    def test_selected_options_are_included_in_total(self):
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 2, "option_ids": [1]}]))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["total"], "24.00")

    def test_invalid_option_for_dish_is_rejected(self):
        DummyCheckoutIntentView.test_options = {
            9: SimpleNamespace(id=9, name="Wrong", price_delta=Decimal("1.00"), dish=SimpleNamespace(slug="sushi"))
        }
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 1, "option_ids": [9]}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_options")

    def test_accepts_checkout_intent_when_plan_allows(self):
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 2}]))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["code"], "checkout_not_configured")
        self.assertEqual(response.data["total"], "20.00")
        self.assertEqual(response.data["currency"], "USD")

    def test_table_context_checkout_intent_allows_minimal_payload(self):
        response = self._request(
            {
                "table_slug": "table-4",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_invalid_table_slug_is_rejected(self):
        response = self._request(
            {
                "table_slug": "missing-table",
                "items": [{"slug": "burger", "qty": 1}],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "table_unavailable")
