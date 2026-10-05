from datetime import datetime, time, timezone as _tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OrderHandoffView


def _dish(slug, name, price, currency="USD", category_id=10):
    # option_groups: the shared per-line helper (price_line_options) validates group bounds.
    return SimpleNamespace(
        slug=slug, name=name, price=Decimal(price), currency=currency, category_id=category_id,
        option_groups=SimpleNamespace(all=lambda: []),
    )


def _hh_rule(percent_off, days=(0, 1, 2, 3, 4), start=time(17, 0), end=time(19, 0)):
    """An active happy-hour rule covering every category (Mon-Fri 17:00-19:00 by default)."""
    rule = MagicMock()
    rule.percent_off = percent_off
    rule.days = list(days)
    rule.start_time = start
    rule.end_time = end
    rule.categories.all.return_value = []
    return rule


# Tenant-local instants (2026-06-08 is a Monday): inside / outside the default rule window.
_MON_1800 = datetime(2026, 6, 8, 18, 0, tzinfo=_tz.utc)
_MON_1000 = datetime(2026, 6, 8, 10, 0, tzinfo=_tz.utc)


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


class _HandoffViewTestBase(SimpleTestCase):
    """Shared fixtures (no test methods of its own)."""

    def setUp(self):
        cache.clear()  # OrderHandoffThrottle (per-IP) counts in the cache across tests
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
            "burger": _dish("burger", "Burger", "10.00"),
        }
        # No DB: the happy-hour rule source reads HappyHour (no rules unless a test sets them).
        hh_patch = patch("menu.pricing.HappyHour")
        self.mock_hh = hh_patch.start()
        self.addCleanup(hh_patch.stop)
        self.mock_hh.objects.filter.return_value.prefetch_related.return_value = []
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


class OrderHandoffTests(_HandoffViewTestBase):
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
        self.assertEqual(response.data["code"], "stale_options")
        self.assertEqual(response.data["invalid_option_ids"], [9])

    def test_mixed_currency_cart_is_rejected(self):
        DummyOrderHandoffView.test_dishes = {
            "burger": _dish("burger", "Burger", "10.00"),
            "sushi": _dish("sushi", "Sushi", "12.00", currency="EUR"),
        }
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 1}, {"slug": "sushi", "qty": 1}])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "mixed_currency")

    def test_non_table_order_requires_fulfillment(self):
        # customer_name / customer_phone are optional (identity comes from
        # the customer session), so only fulfillment_type is required here.
        response = self._request({"items": [{"slug": "burger", "qty": 1}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fulfillment_type", response.data)

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


class OrderHandoffQuoteMatchesCheckoutTests(_HandoffViewTestBase):
    """M11 regressions: the WhatsApp quote must price lines and the delivery fee the way direct
    checkout (PlaceOrderView) does."""

    # ── Happy hour (same windowed rule source + effective_unit_price as checkout) ──

    def _at(self, now_local):
        p = patch("menu.views._profile_now", return_value=now_local)
        p.start()
        self.addCleanup(p.stop)

    def test_happy_hour_price_is_quoted_inside_the_window(self):
        self.mock_hh.objects.filter.return_value.prefetch_related.return_value = [_hh_rule(20)]
        self._at(_MON_1800)
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 2}]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 20% off 10.00 = 8.00 per unit, exactly what the menu/cart and checkout charge.
        self.assertIn("- 2 x Burger (8.00 USD)", response.data["message"])
        self.assertIn("Total: 16.00 USD", response.data["message"])
        self.assertEqual(response.data["total"], "16.00")

    def test_happy_hour_discounts_the_dish_but_not_option_deltas(self):
        self.mock_hh.objects.filter.return_value.prefetch_related.return_value = [_hh_rule(20)]
        self._at(_MON_1800)
        response = self._request(
            self._non_table_payload(items=[{"slug": "burger", "qty": 2, "option_ids": [1]}])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # (10.00 - 20%) + 2.00 cheese = 10.00 per unit — option price_delta is never discounted.
        self.assertEqual(response.data["total"], "20.00")
        self.assertIn("options: Cheese", response.data["message"])

    def test_full_price_outside_the_happy_hour_window(self):
        # Guard: an active rule outside its day/time window must not discount the quote.
        self.mock_hh.objects.filter.return_value.prefetch_related.return_value = [_hh_rule(20)]
        self._at(_MON_1000)
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 2}]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], "20.00")

    def test_option_group_bounds_are_enforced_like_checkout(self):
        # The shared per-line helper also enforces option-group min/max (as checkout does), so a
        # cart checkout would reject can't be quoted on WhatsApp either.
        cheese = DummyOrderHandoffView.test_options[1]
        required = SimpleNamespace(
            id=7, name="Sauce", min_select=1, max_select=1,
            options=SimpleNamespace(all=lambda: [cheese]),
        )
        DummyOrderHandoffView.test_dishes["burger"].option_groups = SimpleNamespace(all=lambda: [required])
        response = self._request(self._non_table_payload(items=[{"slug": "burger", "qty": 1}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "option_selection_invalid")

    # ── Delivery fee (same shared delivery-pricing helper as checkout) ──

    def _delivery_profile(self, *, per_km="0", base="0", flat="10.00", free_over="0", radius=None):
        self.profile.delivery_per_km = Decimal(per_km)
        self.profile.delivery_base_fee = Decimal(base)
        self.profile.delivery_fee = Decimal(flat)
        self.profile.delivery_free_over = Decimal(free_over)
        self.profile.delivery_radius_km = radius
        self.profile.lat = 33.6
        self.profile.lng = -7.6
        # Production parity: tenant.profile IS the tenant's Profile.
        self.tenant.profile = self.profile

    def _delivery_payload(self, with_coords=True):
        extra = {"fulfillment_type": "delivery", "delivery_address": "Main street 1"}
        if with_coords:
            extra.update(delivery_lat=33.5731, delivery_lng=-7.5898)
        else:
            extra["delivery_location_url"] = "https://maps.example.com/?q=33.57,-7.58"
        return self._non_table_payload(**extra)

    def _road_km(self, km):
        p = patch("tenancy.routing.road_distance_km", return_value=km)
        p.start()
        self.addCleanup(p.stop)

    def test_distance_priced_fee_is_computed_from_the_coordinates(self):
        self._delivery_profile(per_km="2.00", base="5.00", flat="10.00")
        self._road_km(3.0)
        response = self._request(self._delivery_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # base 5.00 + 2.00/km x 3 km = 11.00 (what checkout charges), not the flat 10.00.
        self.assertIn("Subtotal: 10.00 USD", response.data["message"])
        self.assertIn("Delivery fee: 11.00 USD", response.data["message"])
        self.assertIn("Total: 21.00 USD", response.data["message"])
        self.assertEqual(response.data["delivery_fee"], "11.00")
        self.assertEqual(response.data["total"], "21.00")
        self.assertFalse(response.data["delivery_fee_pending"])

    def test_distance_priced_without_coordinates_fee_is_confirmed_by_restaurant(self):
        self._delivery_profile(per_km="2.00", base="5.00", flat="10.00")
        response = self._request(self._delivery_payload(with_coords=False))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        message = response.data["message"]
        self.assertIn("Subtotal: 10.00 USD", message)
        self.assertIn("Delivery fee: to be confirmed by the restaurant", message)
        self.assertNotIn("Total:", message)  # no misleading total without the real fee
        self.assertIsNone(response.data["delivery_fee"])
        self.assertIsNone(response.data["total"])
        self.assertTrue(response.data["delivery_fee_pending"])

    def test_address_outside_delivery_area_fee_is_confirmed_by_restaurant(self):
        self._delivery_profile(per_km="2.00", base="5.00", flat="10.00", radius=5)
        self._road_km(8.0)  # beyond the 5 km radius — checkout would refuse this address
        response = self._request(self._delivery_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Delivery fee: to be confirmed by the restaurant", response.data["message"])
        self.assertTrue(response.data["delivery_fee_pending"])

    def test_flat_fee_restaurant_quotes_its_flat_fee_as_before(self):
        # Guard: flat-fee restaurants keep a numeric fee + total, with or without coordinates.
        self._delivery_profile(flat="10.00")
        self._road_km(3.0)
        for with_coords in (True, False):
            with self.subTest(with_coords=with_coords):
                response = self._request(self._delivery_payload(with_coords=with_coords))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("Delivery fee: 10.00 USD", response.data["message"])
                self.assertIn("Total: 20.00 USD", response.data["message"])
                self.assertEqual(response.data["total"], "20.00")

    def test_flat_fee_free_over_threshold_matches_checkout(self):
        # Checkout charges no fee once the food subtotal reaches delivery_free_over.
        self._delivery_profile(flat="10.00", free_over="15.00")
        response = self._request(
            self._delivery_payload() | {"items": [{"slug": "burger", "qty": 2}]}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Delivery fee", response.data["message"])
        self.assertIn("Total: 20.00 USD", response.data["message"])
        self.assertEqual(response.data["delivery_fee"], "0.00")
