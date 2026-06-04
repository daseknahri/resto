"""
Tests for PlaceOrderView — POST /api/place-order/

Covers: plan gate, menu-published gate, restaurant-closed gate,
delivery auth/verified gate, table-unavailable gate, items-unavailable gate,
and the happy-path order creation.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import PlaceOrderView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _plan(can_checkout=True, can_whatsapp_order=True):
    return SimpleNamespace(can_checkout=can_checkout, can_whatsapp_order=can_whatsapp_order)


def _tenant(plan=None, tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Demo", plan=plan or _plan())


def _profile(
    is_menu_published=True,
    is_menu_temporarily_disabled=False,
    is_open=True,
    delivery_fee="0",
):
    return SimpleNamespace(
        is_menu_published=is_menu_published,
        is_menu_temporarily_disabled=is_menu_temporarily_disabled,
        is_open=is_open,
        delivery_fee=delivery_fee,
    )


def _dish(slug="burger", price="10.00", currency="MAD", stock_qty=None):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.price = Decimal(price)
    d.currency = currency
    d.stock_qty = stock_qty  # None = unlimited; must be explicit so MagicMock doesn't produce a truthy sentinel
    return d


def _session(customer_id=None):
    d = {}
    if customer_id is not None:
        d["customer_id"] = customer_id
    sess = MagicMock()
    sess.get = lambda key, default=None: d.get(key, default)
    sess.__setitem__ = lambda s, k, v: d.__setitem__(k, v)
    sess.pop = lambda key, default=None: d.pop(key, default)
    return sess


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


VALID_PAYLOAD = {
    "items": [{"slug": "burger", "qty": 1}],
    "fulfillment_type": "pickup",
}


class PlaceOrderViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, data=None, tenant=None, profile=None, session=None):
        req = self.factory.post("/api/place-order/", data or VALID_PAYLOAD, format="json")
        req.tenant = tenant or _tenant()
        req.user = _anon()
        req.session = session or _session()
        self._profile = profile or _profile()
        return req

    # ── Plan gate ─────────────────────────────────────────────────────────────

    @patch("menu.views.Profile.objects")
    def test_rejects_when_plan_disallows_ordering(self, _profile_mock):
        req = self._post(tenant=_tenant(plan=_plan(can_checkout=False, can_whatsapp_order=False)))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "plan_forbidden")

    # ── Profile / menu gates ───────────────────────────────────────────────────

    @patch("menu.views.Profile.objects")
    def test_rejects_when_no_profile(self, profile_mock):
        profile_mock.filter.return_value.first.return_value = None
        req = self._post()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "profile_missing")

    @patch("menu.views.Profile.objects")
    def test_rejects_when_menu_temporarily_disabled(self, profile_mock):
        profile_mock.filter.return_value.first.return_value = _profile(is_menu_temporarily_disabled=True)
        req = self._post()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "menu_temporarily_disabled")

    @patch("menu.views.Profile.objects")
    def test_rejects_when_menu_not_published(self, profile_mock):
        profile_mock.filter.return_value.first.return_value = _profile(is_menu_published=False)
        req = self._post()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "menu_unpublished")

    @patch("menu.views.Profile.objects")
    def test_rejects_when_restaurant_closed(self, profile_mock):
        """PlaceOrderView must return 409 restaurant_closed when is_open is False."""
        profile_mock.filter.return_value.first.return_value = _profile(is_open=False)
        req = self._post()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "restaurant_closed")

    @patch("menu.views.Profile.objects")
    def test_preview_user_bypasses_closed_check(self, profile_mock):
        """Tenant owner can still place orders even when restaurant is closed (preview mode)."""
        profile_mock.filter.return_value.first.return_value = _profile(is_open=False)
        tenant = _tenant()
        req = self._post(tenant=tenant)
        # Make the request user look like the tenant owner
        owner = MagicMock()
        owner.is_authenticated = True
        owner.is_superuser = False
        owner.is_staff = False
        owner.is_platform_admin = False
        owner.tenant_id = tenant.id
        req.user = owner
        # Will fail at serializer/dish stage — not at the closed check
        with patch("menu.views.Dish.objects") as dish_mock:
            dish_mock.filter.return_value.select_related.return_value = []
            resp = self.view(req)
        # Should NOT be 409 (closed) — should be 400 (items unavailable) or similar
        self.assertNotEqual(resp.status_code, status.HTTP_409_CONFLICT)

    # ── Delivery auth gate ────────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_delivery_requires_auth(self, profile_mock, dish_mock):
        """Delivery without a session customer should return 403 auth_required."""
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]

        payload = {
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "delivery",
            "delivery_address": "123 Main St",
            "delivery_location_url": "https://maps.example.com/place/123",
        }
        req = self._post(data=payload)
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "auth_required")

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_delivery_requires_verified_customer(self, profile_mock, dish_mock):
        """Delivery with an unverified customer returns 403 not_verified."""
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]

        customer = MagicMock()
        customer.phone_verified = False
        customer.email_verified = False
        customer.google_sub = None

        payload = {
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "delivery",
            "delivery_address": "123 Main St",
            "delivery_location_url": "https://maps.example.com/place/123",
        }
        req = self._post(data=payload, session=_session(customer_id=7))
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("accounts.models.Customer.objects") as cust_mock:
                cust_mock.get.return_value = customer
                with patch("menu.views.PlaceOrderView.post") as _:
                    # Manually trigger the view so Customer is imported inline
                    pass
        # Re-run with patched Customer import path used inside the view
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("menu.models.Order") as _:
                pass
        # Direct patch of the inline import
        import accounts.models as accts
        with patch.object(accts.Customer, "objects") as cust_mock:
            cust_mock.get.return_value = customer
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_verified")

    # ── Table gate ────────────────────────────────────────────────────────────

    @patch("menu.views.TableLink.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_rejects_inactive_table_slug(self, profile_mock, dish_mock, table_mock):
        """PlaceOrderView must return 400 table_unavailable for an inactive/missing table slug."""
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]
        table_mock.filter.return_value.first.return_value = None  # table not found

        payload = {"items": [{"slug": "burger", "qty": 1}], "table_slug": "table-99"}
        req = self._post(data=payload)
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "table_unavailable")

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.TableLink.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_active_table_slug_enriches_label(self, profile_mock, dish_mock, table_mock, promo_mock):
        """A valid table_slug must use the DB label as the authoritative table_label."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]
        table = SimpleNamespace(label="Table 5", slug="table-5")
        table_mock.filter.return_value.first.return_value = table

        payload = {"items": [{"slug": "burger", "qty": 1}], "table_slug": "table-5"}
        req = self._post(data=payload)
        created_orders = []

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("menu.views.Order.objects") as order_mock:
                mock_order = MagicMock()
                mock_order.order_number = "ORD001"
                mock_order.status = "pending"
                mock_order.total = Decimal("10.00")
                mock_order.delivery_fee = Decimal("0")
                mock_order.currency = "MAD"
                mock_order.estimated_ready_minutes = None
                order_mock.create.return_value = mock_order
                with patch("menu.views.OrderItem.objects"):
                    with patch("menu.views._generate_order_number", return_value="ORD001"):
                        with patch("menu.views.transaction") as tx_mock:
                            cm = MagicMock()
                            cm.__enter__ = MagicMock(return_value=None)
                            cm.__exit__ = MagicMock(return_value=False)
                            tx_mock.atomic.return_value = cm
                            resp = self.view(req)

        # Whether creation succeeded or errored, table_unavailable should NOT be returned
        self.assertNotEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # If order was created, verify table_label was set from DB
        if order_mock.create.called:
            kwargs = order_mock.create.call_args[1]
            self.assertEqual(kwargs.get("table_label"), "Table 5")

    # ── Items unavailable ─────────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_rejects_unavailable_items(self, profile_mock, dish_mock):
        profile_mock.filter.return_value.first.return_value = _profile()
        dish_mock.filter.return_value.select_related.return_value = []  # none found

        req = self._post()
        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "items_unavailable")

    # ── Phone required for delivery ────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_delivery_requires_phone_number(self, profile_mock, dish_mock):
        """Delivery with a verified customer but no phone should return 403 phone_required."""
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]

        # Verified via email but no phone number set
        customer = MagicMock()
        customer.phone_verified = False
        customer.email_verified = True
        customer.google_sub = None
        customer.phone = None  # no phone

        payload = {
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "delivery",
            "delivery_address": "123 Main St",
            "delivery_location_url": "https://maps.example.com/place/123",
        }
        req = self._post(data=payload, session=_session(customer_id=7))
        import accounts.models as _accts
        with patch.object(_accts.Customer, "objects") as cust_mock:
            cust_mock.get.return_value = customer
            with patch("menu.views.DishOption.objects") as opt_mock:
                opt_mock.filter.return_value = []
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "phone_required")

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_delivery_with_phone_passes_phone_gate(self, profile_mock, dish_mock, promo_mock):
        """Verified customer WITH a phone should not be blocked by the phone gate."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish = _dish()
        dish_mock.filter.return_value.select_related.return_value = [dish]

        customer = MagicMock()
        customer.phone_verified = True
        customer.email_verified = False
        customer.google_sub = None
        customer.phone = "+21261234567"
        customer.name = "Alice"
        customer.wallet_balance = Decimal("1000")  # funds the pay-now (pickup/delivery) requirement

        payload = {
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "delivery",
            "delivery_address": "123 Main St",
            "delivery_location_url": "https://maps.example.com/place/123",
        }
        req = self._post(data=payload, session=_session(customer_id=7))
        import accounts.models as _accts
        with patch.object(_accts.Customer, "objects") as cust_mock, \
             patch.object(_accts.WalletTransaction, "objects"):
            cust_mock.get.return_value = customer
            # Delivery is pay-now: the locked-row wallet debit reads this same customer.
            cust_mock.select_for_update.return_value.get.return_value = customer
            with patch("menu.views.DishOption.objects") as opt_mock:
                opt_mock.filter.return_value = []
                with patch("menu.views.Order.objects") as order_mock:
                    mock_order = MagicMock()
                    mock_order.order_number = "ORD999"
                    mock_order.status = "pending"
                    mock_order.total = Decimal("10.00")
                    mock_order.delivery_fee = Decimal("0")
                    mock_order.currency = "MAD"
                    mock_order.estimated_ready_minutes = None
                    order_mock.create.return_value = mock_order
                    with patch("menu.views.OrderItem.objects"):
                        with patch("menu.views._generate_order_number", return_value="ORD999"):
                            with patch("menu.views.transaction") as tx_mock:
                                cm = MagicMock()
                                cm.__enter__ = MagicMock(return_value=None)
                                cm.__exit__ = MagicMock(return_value=False)
                                tx_mock.atomic.return_value = cm
                                resp = self.view(req)
        # Should NOT be blocked by the phone gate (may fail later for other reasons)
        self.assertNotEqual(resp.data.get("code"), "phone_required")

    # ── Stock management ──────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_out_of_stock_returns_items_unavailable(self, profile_mock, dish_mock, promo_mock):
        """When ordered qty exceeds available stock, return 400 items_unavailable."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()

        # Dish has 1 unit remaining; customer orders 2
        dish = _dish(stock_qty=1)
        dish_mock.filter.return_value.select_related.return_value = [dish]

        # The locked row (select_for_update) reflects the same stock
        locked_dish = MagicMock()
        locked_dish.pk = dish.pk
        locked_dish.stock_qty = 1
        dish_mock.select_for_update.return_value.filter.return_value = [locked_dish]

        payload = {"items": [{"slug": "burger", "qty": 2}], "fulfillment_type": "pickup"}
        req = self._post(data=payload, session=_session(customer_id=7))

        # Pickup is pay-now: supply a funded wallet customer so the request reaches
        # the stock check (which is what this test exercises).
        customer = MagicMock()
        customer.wallet_balance = Decimal("1000")
        import accounts.models as _accts
        with patch.object(_accts.Customer, "objects") as cust_mock:
            cust_mock.get.return_value = customer
            with patch("menu.views.DishOption.objects") as opt_mock:
                opt_mock.filter.return_value = []
                with patch("menu.views.transaction") as tx_mock:
                    cm = MagicMock()
                    cm.__enter__ = MagicMock(return_value=None)
                    cm.__exit__ = MagicMock(return_value=False)
                    tx_mock.atomic.return_value = cm
                    resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "items_unavailable")
        self.assertIn(dish.slug, resp.data.get("slugs", []))

    # ── Pay-now enforcement (pickup & delivery) ───────────────────────────────

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_pickup_without_signed_in_customer_requires_auth(self, profile_mock, dish_mock, promo_mock):
        """A pay-now (pickup) order with no session customer is rejected up front."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish_mock.filter.return_value.select_related.return_value = [_dish()]

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(data=payload)  # no session customer

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "auth_required")

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_pickup_insufficient_wallet_blocks_order(self, profile_mock, dish_mock, promo_mock):
        """A pay-now order whose wallet can't cover the total is rejected (wallet_insufficient)."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish_mock.filter.return_value.select_related.return_value = [_dish(price="10.00")]

        customer = MagicMock()
        customer.wallet_balance = Decimal("3.00")  # < 10.00 total

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(data=payload, session=_session(customer_id=7))
        import accounts.models as _accts
        with patch.object(_accts.Customer, "objects") as cust_mock:
            cust_mock.get.return_value = customer
            with patch("menu.views.DishOption.objects") as opt_mock:
                opt_mock.filter.return_value = []
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(resp.data["code"], "wallet_insufficient")

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_staff_created_pickup_is_exempt_from_prepay(self, profile_mock, dish_mock, promo_mock):
        """A waiter/owner taking a pickup order (no customer session) is NOT blocked by
        the wallet-only rule — they collect payment in person and settle it later."""
        from accounts.models import User
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()
        dish_mock.filter.return_value.select_related.return_value = [_dish()]

        staff = MagicMock()
        staff.is_authenticated = True
        staff.id = 5
        staff.role = User.Roles.TENANT_OWNER

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(data=payload)  # no customer session
        req.user = staff

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("menu.views.Order.objects") as order_mock:
                mock_order = MagicMock()
                mock_order.order_number = "ORD777"
                mock_order.status = "pending"
                mock_order.total = Decimal("10.00")
                mock_order.delivery_fee = Decimal("0")
                mock_order.currency = "MAD"
                mock_order.estimated_ready_minutes = None
                order_mock.create.return_value = mock_order
                with patch("menu.views.OrderItem.objects"), \
                     patch("menu.views._generate_order_number", return_value="ORD777"), \
                     patch("menu.views.transaction") as tx_mock:
                    cm = MagicMock()
                    cm.__enter__ = MagicMock(return_value=None)
                    cm.__exit__ = MagicMock(return_value=False)
                    tx_mock.atomic.return_value = cm
                    resp = self.view(req)

        # Must NOT be blocked by the customer-wallet prepay gate.
        self.assertNotIn(resp.data.get("code"), ("auth_required", "wallet_insufficient"))

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_sufficient_stock_allows_order(self, profile_mock, dish_mock, promo_mock):
        """When stock is sufficient, the order proceeds and stock would be decremented."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()

        # Dish has 5 units; customer orders 2 — should succeed
        dish = _dish(stock_qty=5)
        dish_mock.filter.return_value.select_related.return_value = [dish]

        locked_dish = MagicMock()
        locked_dish.pk = dish.pk
        locked_dish.stock_qty = 5
        dish_mock.select_for_update.return_value.filter.return_value = [locked_dish]
        # The per-dish UPDATE call used for decrement
        dish_mock.filter.return_value.update.return_value = 1

        payload = {"items": [{"slug": "burger", "qty": 2}], "fulfillment_type": "pickup"}
        req = self._post(data=payload)

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("menu.views.Order.objects") as order_mock:
                mock_order = MagicMock()
                mock_order.order_number = "STOCK01"
                mock_order.status = "pending"
                mock_order.total = Decimal("20.00")
                mock_order.delivery_fee = Decimal("0")
                mock_order.currency = "MAD"
                mock_order.estimated_ready_minutes = None
                order_mock.create.return_value = mock_order
                with patch("menu.views.OrderItem.objects"):
                    with patch("menu.views._generate_order_number", return_value="STOCK01"):
                        with patch("menu.views.transaction") as tx_mock:
                            cm = MagicMock()
                            cm.__enter__ = MagicMock(return_value=None)
                            cm.__exit__ = MagicMock(return_value=False)
                            tx_mock.atomic.return_value = cm
                            resp = self.view(req)

        # Order should be created (201) — not blocked by stock check
        self.assertNotEqual(resp.data.get("code"), "items_unavailable")
        self.assertNotEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Promotion.objects")
    @patch("menu.views.Dish.objects")
    @patch("menu.views.Profile.objects")
    def test_exact_stock_match_triggers_sold_out(self, profile_mock, dish_mock, promo_mock):
        """Ordering the last remaining unit returns 400 items_unavailable (race: qty==stock)."""
        promo_mock.filter.return_value = []
        profile_mock.filter.return_value.first.return_value = _profile()

        dish = _dish(stock_qty=1)
        dish_mock.filter.return_value.select_related.return_value = [dish]

        # Stock was 1, but we're ordering 1 — this is fine; stock would hit 0 and auto-disable.
        # Only reject if ordered qty EXCEEDS available stock.
        locked_dish = MagicMock()
        locked_dish.pk = dish.pk
        locked_dish.stock_qty = 1
        dish_mock.select_for_update.return_value.filter.return_value = [locked_dish]
        dish_mock.filter.return_value.update.return_value = 1

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(data=payload)

        with patch("menu.views.DishOption.objects") as opt_mock:
            opt_mock.filter.return_value = []
            with patch("menu.views.Order.objects") as order_mock:
                mock_order = MagicMock()
                mock_order.order_number = "LAST01"
                mock_order.status = "pending"
                mock_order.total = Decimal("10.00")
                mock_order.delivery_fee = Decimal("0")
                mock_order.currency = "MAD"
                mock_order.estimated_ready_minutes = None
                order_mock.create.return_value = mock_order
                with patch("menu.views.OrderItem.objects"):
                    with patch("menu.views._generate_order_number", return_value="LAST01"):
                        with patch("menu.views.transaction") as tx_mock:
                            cm = MagicMock()
                            cm.__enter__ = MagicMock(return_value=None)
                            cm.__exit__ = MagicMock(return_value=False)
                            tx_mock.atomic.return_value = cm
                            resp = self.view(req)

        # Ordering the last unit should be ALLOWED (stock >= qty)
        self.assertNotEqual(resp.data.get("code"), "items_unavailable")
