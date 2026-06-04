"""
Regression tests for the security and correctness fixes applied to the API.

All tests are SimpleTestCase (no database).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import CustomerGoogleAuthView
from menu.views import CustomerOrderStatusView, PlaceOrderView


# ── CustomerGoogleAuthView — OAuth client_id guard ─────────────────────────────

class GoogleAuthClientIdGuardTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("accounts.views.settings")
    def test_returns_503_when_client_id_not_configured(self, mock_settings):
        """POST /customer/google-auth/ must refuse all requests when
        GOOGLE_OAUTH_CLIENT_ID is empty — skipping the audience check would
        accept any valid Google ID token issued to any app."""
        mock_settings.GOOGLE_OAUTH_CLIENT_ID = ""

        req = self.factory.post("/api/customer/google-auth/", {"credential": "fake"}, format="json")
        response = CustomerGoogleAuthView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "not_configured")

    @patch("accounts.views.settings")
    def test_returns_503_when_client_id_is_whitespace(self, mock_settings):
        """Whitespace-only client_id must also trigger the 503 guard."""
        mock_settings.GOOGLE_OAUTH_CLIENT_ID = "   "

        req = self.factory.post("/api/customer/google-auth/", {"credential": "fake"}, format="json")
        response = CustomerGoogleAuthView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("accounts.views.settings")
    @patch("accounts.views._verify_google_token")
    def test_proceeds_to_token_verify_when_client_id_is_set(self, mock_verify, mock_settings):
        """When GOOGLE_OAUTH_CLIENT_ID is non-empty the view must NOT return 503
        — it must attempt token verification (and reject bad tokens as 400)."""
        mock_settings.GOOGLE_OAUTH_CLIENT_ID = "123.apps.googleusercontent.com"
        mock_verify.return_value = None  # Simulate invalid token

        req = self.factory.post(
            "/api/customer/google-auth/", {"credential": "bad-token"}, format="json"
        )
        response = CustomerGoogleAuthView.as_view()(req)

        # 400, not 503 — the guard passed, token verification failed instead
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_verify.assert_called_once_with("bad-token", "123.apps.googleusercontent.com")

    def test_returns_400_when_credential_is_empty(self):
        """Empty credential must fail validation before any env-var check."""
        req = self.factory.post("/api/customer/google-auth/", {"credential": ""}, format="json")
        response = CustomerGoogleAuthView.as_view()(req)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ── CustomerOrderStatusView — PII omission ─────────────────────────────────────

class OrderStatusPiiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _make_order(self):
        item = MagicMock()
        item.dish_slug = "burger"
        item.dish_name = "Burger"
        item.qty = 1
        item.unit_price = MagicMock()
        item.unit_price.__str__ = lambda s: "12.00"
        item.subtotal = MagicMock()
        item.subtotal.__str__ = lambda s: "12.00"
        item.options = []
        item.note = ""

        items_qs = MagicMock()
        items_qs.__iter__ = lambda s: iter([item])

        order = MagicMock()
        order.order_number = "ORD-ABCDEF"
        order.status = "pending"
        order.fulfillment_type = "table"
        order.table_label = "5"
        order.customer_name = "Ahmed"
        order.customer_phone = "+212612345678"
        order.delivery_address = "5 Rue de Paris"
        order.delivery_location_url = "https://maps.google.com/..."
        order.total = MagicMock()
        order.total.__str__ = lambda s: "12.00"
        order.delivery_fee = MagicMock()
        order.delivery_fee.__str__ = lambda s: "0.00"
        order.currency = "MAD"
        order.owner_note = ""
        order.estimated_ready_minutes = None
        order.created_at = MagicMock()
        order.created_at.isoformat.return_value = "2026-05-17T10:00:00Z"
        order.status_updated_at = None
        order.items = items_qs
        order.rating = None  # no rating yet; prevents MagicMock auto-attr being truthy
        return order

    @patch("menu.views.Order.objects")
    def test_customer_phone_not_in_status_response(self, mock_objects):
        """customer_phone must never appear in the public order-status endpoint."""
        mock_objects.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = (
            self._make_order()
        )
        req = self.factory.get("/api/order-status/ORD-ABCDEF/")
        req.tenant = SimpleNamespace(id=1)
        response = CustomerOrderStatusView.as_view()(req, order_number="ORD-ABCDEF")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("customer_phone", response.data)

    @patch("menu.views.Order.objects")
    def test_customer_name_still_present(self, mock_objects):
        """customer_name should remain — it confirms the customer placed the order."""
        mock_objects.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = (
            self._make_order()
        )
        req = self.factory.get("/api/order-status/ORD-ABCDEF/")
        req.tenant = SimpleNamespace(id=1)
        response = CustomerOrderStatusView.as_view()(req, order_number="ORD-ABCDEF")

        self.assertIn("customer_name", response.data)
        self.assertEqual(response.data["customer_name"], "Ahmed")

    @patch("menu.views.Order.objects")
    def test_delivery_address_still_present(self, mock_objects):
        """delivery_address should remain so the customer can verify their drop-off."""
        mock_objects.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = (
            self._make_order()
        )
        req = self.factory.get("/api/order-status/ORD-ABCDEF/")
        req.tenant = SimpleNamespace(id=1)
        response = CustomerOrderStatusView.as_view()(req, order_number="ORD-ABCDEF")

        self.assertIn("delivery_address", response.data)

    @patch("menu.views.Order.objects")
    def test_delivery_location_url_not_in_status_response(self, mock_objects):
        """delivery_location_url is never needed by the status page UI."""
        mock_objects.filter.return_value.prefetch_related.return_value.select_related.return_value.first.return_value = (
            self._make_order()
        )
        req = self.factory.get("/api/order-status/ORD-ABCDEF/")
        req.tenant = SimpleNamespace(id=1)
        response = CustomerOrderStatusView.as_view()(req, order_number="ORD-ABCDEF")

        self.assertNotIn("delivery_location_url", response.data)


# ── PlaceOrderView — RuntimeError → 503 ───────────────────────────────────────

class PlaceOrderRuntimeErrorTests(SimpleTestCase):
    """_generate_order_number() can raise RuntimeError after 10 failed attempts.
    The view must catch it and return 503 rather than letting it propagate as 500.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("menu.views.Promotion.objects")
    @patch("menu.views._generate_order_number")
    @patch("menu.views.Profile.objects")
    @patch("menu.views.Dish.objects")
    def test_runtime_error_returns_503(
        self, mock_dish_objects, mock_profile_objects, mock_gen_number, mock_promo_objects
    ):
        mock_gen_number.side_effect = RuntimeError(
            "Could not generate unique order number after 10 attempts."
        )
        mock_promo_objects.filter.return_value = []

        # Minimal profile
        profile = MagicMock()
        profile.is_menu_published = True
        profile.is_menu_temporarily_disabled = False
        profile.delivery_fee = "0"
        profile.whatsapp = ""
        profile.phone = ""
        mock_profile_objects.filter.return_value.first.return_value = profile

        # Single published dish with no stock tracking
        dish = MagicMock()
        dish.id = 1
        dish.slug = "burger"
        dish.is_published = True
        dish.is_available = True
        dish.price = MagicMock()
        dish.price.__float__ = lambda s: 10.0
        dish.price.__str__ = lambda s: "10.00"
        dish.currency = "MAD"
        dish.stock_qty = None
        # Make Dish.objects.filter(...).select_related("category") iterable → [dish]
        filter_mock = MagicMock()
        filter_mock.select_related.return_value = [dish]
        filter_mock.select_for_update.return_value = [dish]
        filter_mock.first.return_value = dish
        mock_dish_objects.filter.return_value = filter_mock

        payload = {
            "customer_name": "Test",
            "customer_phone": "+2120600000000",
            "fulfillment_type": "pickup",
            "items": [{"slug": "burger", "qty": 1, "option_ids": [], "note": ""}],
        }
        req = self.factory.post("/api/place-order/", payload, format="json")
        # Tenant needs a plan that allows ordering
        req.tenant = SimpleNamespace(
            id=1, name="Demo", slug="demo",
            plan=SimpleNamespace(can_whatsapp_order=True, can_checkout=True),
        )
        req.session = {"customer_id": 7}

        # Pickup is pay-now: supply a funded wallet customer so the request reaches
        # the order-number generation (the RuntimeError path this test exercises).
        customer = MagicMock()
        customer.wallet_balance = "1000"
        import accounts.models as _accts
        # Patch the whole transaction.atomic so the DB isn't touched
        with patch.object(_accts.Customer, "objects") as cust_mock, \
             patch("menu.views.transaction") as mock_tx:
            cust_mock.get.return_value = customer
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=None)
            cm.__exit__ = MagicMock(return_value=False)
            mock_tx.atomic.return_value = cm
            # Make _generate_order_number raise inside the mock transaction
            response = PlaceOrderView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data.get("code"), "order_number_exhausted")


# ── OwnerOrderListView — total + has_more ─────────────────────────────────────

class OwnerOrderListTotalTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @staticmethod
    def _mock_order():
        """Minimal order mock that survives OwnerOrderListView's dict-builder loop."""
        from decimal import Decimal
        o = MagicMock()
        o.customer = None          # → customer_email = ""
        o.customer_id = None       # prevents MagicMock in ORM customer_id__in query
        o.status_updated_at = None  # → status_updated_at = None
        o.wallet_amount_paid = Decimal("0")
        # items.all() must be iterable (MagicMock supports __iter__ → iter([]))
        return o

    def _user(self):
        u = MagicMock()
        u.is_authenticated = True
        u.is_active = True
        u.pk = 1
        u.is_superuser = False
        u.is_staff = False
        u.is_platform_admin = False
        u.role = "tenant_owner"
        u.tenant_id = 1
        return u

    @patch("menu.views.Order.objects")
    def test_response_includes_total_and_has_more_false(self, mock_objects):
        """When all results fit within 200, has_more must be False."""
        from menu.views import OwnerOrderListView

        mock_qs = MagicMock()
        mock_qs.count.return_value = 3
        # Slice qs[:200] must yield 3 items so len(orders)==3 and has_more==False
        mock_qs.__getitem__ = lambda s, sl: [self._mock_order() for _ in range(3)]
        mock_qs.__iter__ = lambda s: iter([self._mock_order() for _ in range(3)])
        mock_objects.select_related.return_value.prefetch_related.return_value.order_by.return_value = mock_qs

        user = self._user()
        req = self.factory.get("/api/owner/orders/")
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = SimpleNamespace(id=1)

        response = OwnerOrderListView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total", response.data)
        self.assertEqual(response.data["total"], 3)
        self.assertFalse(response.data["has_more"])

    @patch("menu.views.Order.objects")
    def test_has_more_true_when_total_exceeds_display_cap(self, mock_objects):
        """When server total exceeds 200 displayed rows, has_more must be True."""
        from menu.views import OwnerOrderListView

        mock_qs = MagicMock()
        mock_qs.count.return_value = 847
        mock_qs.__getitem__ = lambda s, sl: []
        mock_qs.__iter__ = lambda s: iter([])
        mock_objects.select_related.return_value.prefetch_related.return_value.order_by.return_value = mock_qs

        user = self._user()
        req = self.factory.get("/api/owner/orders/")
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = SimpleNamespace(id=1)

        response = OwnerOrderListView.as_view()(req)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 847)
        self.assertTrue(response.data["has_more"])
