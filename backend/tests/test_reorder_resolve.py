"""Tests for ReorderResolveView — the availability-safe reorder resolver.

Uses the same DB-free SimpleTestCase + Dummy-subclass pattern as
test_checkout_intent.py: the dish/option fetch helpers (inherited from
OrderHandoffView) are stubbed so availability + pricing logic can be exercised
in isolation. Happy-hour resolution is patched to empty so current_price equals
base price + valid option deltas (matching PlaceOrderView's pricing path).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import ReorderResolveView


class DummyReorderResolveView(ReorderResolveView):
    test_profile = None
    test_dishes = {}
    test_options = {}
    test_can_preview = False

    def _profile_for_tenant(self, tenant):
        return self.__class__.test_profile

    def _fetch_dishes(self, slugs, can_preview):
        return {s: self.__class__.test_dishes[s] for s in slugs if s in self.__class__.test_dishes}

    def _fetch_options(self, option_ids, can_preview):
        return {oid: self.__class__.test_options[oid] for oid in option_ids if oid in self.__class__.test_options}

    def _can_preview_unpublished(self, tenant):
        return self.__class__.test_can_preview


class ReorderResolveTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.tenant = SimpleNamespace(id=1, name="Demo Resto")
        self.profile = SimpleNamespace()
        DummyReorderResolveView.test_profile = self.profile
        DummyReorderResolveView.test_dishes = {
            "burger": SimpleNamespace(slug="burger", name="Burger", price=Decimal("10.00"), currency="USD", category_id=1),
            "fries": SimpleNamespace(slug="fries", name="Fries", price=Decimal("4.50"), currency="USD", category_id=1),
        }
        DummyReorderResolveView.test_options = {
            1: SimpleNamespace(id=1, name="Cheese", price_delta=Decimal("2.00"), dish=SimpleNamespace(slug="burger")),
            2: SimpleNamespace(id=2, name="Bacon", price_delta=Decimal("3.00"), dish=SimpleNamespace(slug="burger")),
        }
        DummyReorderResolveView.test_can_preview = False
        # Patch happy-hour resolution to no rules so current_price == base + options.
        self._hh_patch = mock.patch("menu.views.get_all_active_hh_rules", return_value=[])
        self._hh_patch.start()
        self.addCleanup(self._hh_patch.stop)

    def _request(self, payload):
        req = self.factory.post("/api/reorder-resolve/", payload, format="json")
        req.tenant = self.tenant
        return DummyReorderResolveView.as_view()(req)

    # ── happy path ────────────────────────────────────────────────────────────
    def test_available_item_returns_current_price(self):
        resp = self._request({"items": [{"slug": "burger", "option_ids": []}]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        line = resp.data["items"][0]
        self.assertTrue(line["available"])
        self.assertEqual(line["slug"], "burger")
        self.assertEqual(line["name"], "Burger")
        self.assertEqual(Decimal(line["current_price"]), Decimal("10.00"))
        self.assertEqual(line["current_option_ids"], [])
        self.assertTrue(line["current_option_ids_valid"])
        self.assertFalse(resp.data["any_unavailable"])

    def test_valid_options_are_added_to_price(self):
        resp = self._request({"items": [{"slug": "burger", "option_ids": [1, 2]}]})
        line = resp.data["items"][0]
        # 10.00 base + 2.00 cheese + 3.00 bacon
        self.assertEqual(Decimal(line["current_price"]), Decimal("15.00"))
        self.assertEqual(sorted(line["current_option_ids"]), [1, 2])
        self.assertTrue(line["current_option_ids_valid"])

    # ── availability-safety ─────────────────────────────────────────────────────
    def test_unavailable_item_is_flagged_not_errored(self):
        resp = self._request({"items": [{"slug": "gone", "option_ids": []}]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        line = resp.data["items"][0]
        self.assertFalse(line["available"])
        self.assertIsNone(line["current_price"])
        self.assertTrue(resp.data["any_unavailable"])

    def test_mixed_available_and_unavailable(self):
        resp = self._request({"items": [
            {"slug": "burger", "option_ids": []},
            {"slug": "gone", "option_ids": []},
            {"slug": "fries", "option_ids": []},
        ]})
        by_slug = {l["slug"]: l for l in resp.data["items"]}
        self.assertTrue(by_slug["burger"]["available"])
        self.assertTrue(by_slug["fries"]["available"])
        self.assertFalse(by_slug["gone"]["available"])
        self.assertTrue(resp.data["any_unavailable"])

    def test_stale_option_is_dropped_not_errored(self):
        # Option 99 doesn't exist; option 1 valid. Stale one is silently dropped.
        resp = self._request({"items": [{"slug": "burger", "option_ids": [1, 99]}]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        line = resp.data["items"][0]
        self.assertTrue(line["available"])
        self.assertEqual(line["current_option_ids"], [1])
        self.assertFalse(line["current_option_ids_valid"])
        self.assertTrue(resp.data["any_options_dropped"])
        # Price excludes the dropped option: 10.00 + 2.00 cheese.
        self.assertEqual(Decimal(line["current_price"]), Decimal("12.00"))

    def test_option_belonging_to_other_dish_is_dropped(self):
        # Option 1 belongs to burger; requesting it for fries must drop it.
        resp = self._request({"items": [{"slug": "fries", "option_ids": [1]}]})
        line = resp.data["items"][0]
        self.assertTrue(line["available"])
        self.assertEqual(line["current_option_ids"], [])
        self.assertFalse(line["current_option_ids_valid"])
        self.assertEqual(Decimal(line["current_price"]), Decimal("4.50"))

    # ── input shapes ────────────────────────────────────────────────────────────
    def test_slugs_shorthand_shape(self):
        resp = self._request({"slugs": ["burger", "fries"], "option_ids": []})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["items"]), 2)

    def test_empty_input_is_rejected(self):
        resp = self._request({"items": []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_items")

    def test_missing_input_is_rejected(self):
        resp = self._request({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_items")

    def test_tenant_missing_is_rejected(self):
        req = self.factory.post("/api/reorder-resolve/", {"items": [{"slug": "burger"}]}, format="json")
        req.tenant = None
        resp = DummyReorderResolveView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "tenant_missing")

    def test_happy_hour_discount_reflected_in_current_price(self):
        # A 50%-off rule covering all categories should halve the base price.
        rule = SimpleNamespace(percent_off=50, categories=SimpleNamespace(all=lambda: []))
        with mock.patch("menu.views.get_all_active_hh_rules", return_value=[rule]):
            resp = self._request({"items": [{"slug": "burger", "option_ids": [1]}]})
        line = resp.data["items"][0]
        # base 10.00 -> 5.00 after 50% off; option +2.00 (never discounted) = 7.00
        self.assertEqual(Decimal(line["current_price"]), Decimal("7.00"))
