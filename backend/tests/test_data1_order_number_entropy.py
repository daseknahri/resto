"""RISK DATA-1: order-number generator entropy hardening.

`menu.views._generate_order_number` (and the lockstep inline generator in
`accounts.views.MarketplacePlaceOrderView`) now mint 48-bit values (`token_hex(6)`)
instead of 24-bit — huge within-tenant collision headroom and negligible cross-tenant
collisions, without changing the `ORD-<uppercase hex>` shape that the frontend route
regex and the `max_length=20` field depend on. Mock-based (SimpleTestCase, no DB).
"""
import re
from unittest import mock

from django.test import SimpleTestCase

from menu import views

# 48-bit value: "ORD-" + 12 uppercase hex chars.
_FORMAT = re.compile(r"^ORD-[0-9A-F]{12}$")
# The one format assumption in the frontend: router/index.js legacy redirect
# `/order/:n([A-Z]+-[A-Z0-9]+)`. The new value must still match it.
_FRONTEND_ROUTE_REGEX = re.compile(r"^[A-Z]+-[A-Z0-9]+$")
_ORDER_NUMBER_MAX_LENGTH = 20  # menu.models.Order.order_number


class GenerateOrderNumberTests(SimpleTestCase):
    def test_format_length_and_frontend_regex(self):
        with mock.patch("menu.views.Order") as Order:
            Order.objects.filter.return_value.exists.return_value = False
            n = views._generate_order_number()
        self.assertRegex(n, _FORMAT)                 # ORD- + 12 uppercase hex (48-bit)
        self.assertEqual(len(n), 16)
        self.assertLessEqual(len(n), _ORDER_NUMBER_MAX_LENGTH)  # fits the field
        self.assertRegex(n, _FRONTEND_ROUTE_REGEX)   # frontend /order/:n regex still matches

    def test_retries_until_a_free_value(self):
        with mock.patch("menu.views.Order") as Order:
            # first candidate taken, second free
            Order.objects.filter.return_value.exists.side_effect = [True, False]
            n = views._generate_order_number()
        self.assertRegex(n, _FORMAT)
        self.assertEqual(Order.objects.filter.return_value.exists.call_count, 2)

    def test_raises_after_ten_collisions(self):
        with mock.patch("menu.views.Order") as Order:
            Order.objects.filter.return_value.exists.return_value = True
            with self.assertRaises(RuntimeError):
                views._generate_order_number()
        self.assertEqual(Order.objects.filter.return_value.exists.call_count, 10)

    def test_values_are_distinct_across_calls(self):
        with mock.patch("menu.views.Order") as Order:
            Order.objects.filter.return_value.exists.return_value = False
            values = {views._generate_order_number() for _ in range(50)}
        self.assertEqual(len(values), 50)  # 48-bit space → no collision in a tiny sample
