"""R15b + R16 — money-path hardening contract tests (additive / no-op for MAD today).

Two additive items, neither changes money math or control flow:

  R15b. Three more money-FAILURE paths must emit on the DEDICATED "payments" logger
        (so a payment-failure rate is alertable separately from the ERROR firehose),
        WITHOUT leaking any secret (e.g. the live 6-digit driver cash-out code):
          1. accounts.views.MarketplacePlaceOrderView — the inline wallet-debit step
             (lock + decrement + WalletTransaction PAYMENT) logs to "payments" on a
             money-mutation failure, with attributable ids (schema + order/customer id).
          2. accounts.ride_service._do_settle — logs the settlement failure (ride/rider/
             driver/tenant ids) before re-raising, and a payments.warning on the
             InsufficientFunds → cash fallback.
          3. accounts.driver_service.confirm_cashout — logs a float-credit-leg failure
             (driver/tenant/request id), reusing wallet_service._ref_kind so only the
             "cashout" namespace is recorded, NEVER the raw cash-out code.

  R16 (guard only). The wallet balance is a single MAD scalar and the inline debit writes
        a WalletTransaction at an implicit 1:1 MAD rate. BEFORE debiting, both checkout
        chokepoints (PlaceOrderView in menu/views.py + MarketplacePlaceOrderView in
        accounts/views.py) refuse a non-MAD order with 400 {"code": "currency_unsupported"}.
        Every order is MAD today (currency derives from dish.currency), so the guard is a
        strict NO-OP for the normal case — a MAD order proceeds unchanged.

House style: SimpleTestCase + MagicMock + assertLogs, no real DB (mirrors
test_r15_observability.py, test_place_order_view.py, test_a4_marketplace_cod.py).
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate


# ═════════════════════════════════════════════════════════════════════════════
# R15b.2 — ride settlement failures emit on "payments"
# ═════════════════════════════════════════════════════════════════════════════

class RideSettlePaymentsLoggingTests(SimpleTestCase):
    """accounts.ride_service._do_settle is a money mutation (debit rider → credit driver).

    No DB: the function takes a plain ride object and the wallet seams are module-level
    imports we patch, so the failure / cash-fallback branches are reached deterministically.
    """

    def _ride(self):
        return SimpleNamespace(
            id=77, rider_id=11, driver_id=22, payment_method="wallet",
            fare=Decimal("50.00"), paid_with_wallet=False, cash_fallback=False,
            cash_fallback_note="", kind="ride",
        )

    def test_unexpected_settle_failure_logs_to_payments_and_reraises(self):
        from accounts import ride_service as rs

        ride = self._ride()
        # An unexpected error during the rider debit (NOT InsufficientFunds) must be
        # logged on "payments" with attributable ids, then re-raised so the caller's
        # atomic() rolls the whole completion back (no partial settlement).
        with patch.object(rs, "debit_wallet", side_effect=RuntimeError("db down")):
            with self.assertLogs("payments", level="ERROR") as cm:
                with self.assertRaises(RuntimeError):
                    rs.settle_ride(ride)
        joined = "\n".join(cm.output)
        self.assertIn("ride_id=77", joined)
        self.assertIn("rider_id=11", joined)
        self.assertIn("driver_id=22", joined)
        # Money behaviour unchanged: still a wallet ride (no silent cash flip on a crash).
        self.assertEqual(ride.payment_method, "wallet")

    def test_insufficient_funds_cash_fallback_warns_on_payments(self):
        from accounts import ride_service as rs
        from accounts.wallet_service import InsufficientFunds

        ride = self._ride()
        with patch.object(rs, "debit_wallet", side_effect=InsufficientFunds("short")):
            with self.assertLogs("payments", level="WARNING") as cm:
                rs.settle_ride(ride)  # must NOT raise — explicit cash fallback
        joined = "\n".join(cm.output)
        self.assertIn("ride_id=77", joined)
        self.assertIn("cash", joined.lower())
        # Cash-fallback behaviour is unchanged (the documented OPS-5g markers are set).
        self.assertEqual(ride.payment_method, "cash")
        self.assertTrue(ride.cash_fallback)
        self.assertFalse(ride.paid_with_wallet)

    def test_no_payments_log_on_clean_settle(self):
        """A successful settle must NOT emit a payments failure (no false alert noise)."""
        from accounts import ride_service as rs

        ride = self._ride()
        cfg = SimpleNamespace(ride_commission_pct=Decimal("0"))
        with patch.object(rs, "debit_wallet", return_value=SimpleNamespace(id=1)), \
             patch.object(rs, "credit_wallet", return_value=SimpleNamespace(id=2)), \
             patch.object(rs.PlatformConfig, "get_solo", return_value=cfg):
            logger = __import__("logging").getLogger("payments")
            with patch.object(logger, "handle") as mock_handle:
                rs.settle_ride(ride)
        self.assertFalse(mock_handle.called, "a clean settle must emit nothing on 'payments'")
        self.assertTrue(ride.paid_with_wallet)


# ═════════════════════════════════════════════════════════════════════════════
# R15b.3 — cash-out float-credit-leg failure emits on "payments" (no code leak)
# ═════════════════════════════════════════════════════════════════════════════

def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class ConfirmCashoutFloatLegLoggingTests(SimpleTestCase):
    """confirm_cashout debits the driver wallet then credits the tenant float. The debit
    leg already logs via wallet_service; a failure on the float-credit leg must now also
    emit on 'payments' — reusing _ref_kind so the raw cash-out CODE never reaches a log."""

    def setUp(self):
        self._p = {
            "atomic": patch("django.db.transaction.atomic", return_value=_noop_atomic()),
            "dcr": patch("accounts.models.DriverCashoutRequest"),
            "debit": patch("accounts.wallet_service.debit_wallet"),
            "credit": patch("accounts.wallet_service.credit_tenant_float"),
        }
        self.m = {k: v.start() for k, v in self._p.items()}

    def tearDown(self):
        for v in self._p.values():
            v.stop()

    def _pending(self, amount="120.00"):
        from datetime import timedelta
        from django.utils import timezone
        return SimpleNamespace(
            id=7, driver_id=5, amount=Decimal(amount), code="654321",
            status="pending", expires_at=timezone.now() + timedelta(minutes=10),
            currency="MAD", save=MagicMock(),
        )

    def test_float_credit_failure_logs_to_payments_without_leaking_code(self):
        from accounts.driver_service import confirm_cashout

        req = self._pending()
        self.m["dcr"].objects.select_for_update.return_value.filter.return_value.first.return_value = req
        self.m["debit"].return_value = SimpleNamespace(id=99)  # debit leg succeeds
        # The float-credit leg blows up (e.g. InactiveTenant/WalletError).
        self.m["credit"].side_effect = RuntimeError("float credit failed")

        with self.assertLogs("payments", level="ERROR") as cm:
            with self.assertRaises(RuntimeError):
                confirm_cashout("654321", tenant_id=3, actor_user_id=8)

        joined = "\n".join(cm.output)
        # Attributable by id (driver / tenant / request id), and the safe ref kind.
        self.assertIn("driver_id=5", joined)
        self.assertIn("tenant_id=3", joined)
        self.assertIn("request_id=7", joined)
        self.assertIn("ref_kind=cashout", joined)
        # CRITICAL: the live 6-digit cash-out code must NEVER appear in the log.
        self.assertNotIn("654321", joined)

    def test_uses_ref_kind_from_wallet_service(self):
        """The helper is reused (imported), not re-implemented in driver_service."""
        import accounts.driver_service as ds
        import accounts.wallet_service as ws
        self.assertIs(ds._ref_kind, ws._ref_kind)
        # Sanity: it strips the secret value half of a kind:value reference.
        self.assertEqual(ds._ref_kind("cashout:654321"), "cashout")


# ═════════════════════════════════════════════════════════════════════════════
# R15b.1 + R16 — menu PlaceOrderView wallet-debit chokepoint
# ═════════════════════════════════════════════════════════════════════════════

def _plan(can_checkout=True, can_whatsapp_order=True):
    return SimpleNamespace(can_checkout=can_checkout, can_whatsapp_order=can_whatsapp_order)


def _tenant(plan=None, tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Demo", plan=plan or _plan())


def _profile(delivery_fee="0"):
    return SimpleNamespace(
        is_menu_published=True,
        is_menu_temporarily_disabled=False,
        is_open=True,
        delivery_fee=delivery_fee,
    )


def _menu_dish(currency="MAD"):
    d = MagicMock()
    d.slug = "burger"
    d.name = "Burger"
    d.price = Decimal("10.00")
    d.currency = currency
    d.stock_qty = None
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


class MenuPlaceOrderCurrencyGuardTests(SimpleTestCase):
    """R16: PlaceOrderView refuses a wallet debit on a non-MAD order, and proceeds
    unchanged for MAD (today's every order)."""

    def setUp(self):
        from menu.views import PlaceOrderView
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, data, principal=None):
        req = self.factory.post("/api/place-order/", data, format="json")
        req.tenant = _tenant()
        req.session = {}
        if principal is not None:
            force_authenticate(req, user=principal)
        return req

    def _drive(self, currency, debit_side_effect=None):
        """Drive a funded pickup order to the wallet-debit chokepoint with the dish in the
        given currency. Returns (response, debit_mock)."""
        from accounts.models import Customer
        dish = _menu_dish(currency=currency)
        # RISK IDENTITY-1: the linked customer is request.user (customer_or_none). A real
        # Customer principal carries the verification/phone/wallet the gate reads.
        customer = Customer(id=7, phone_verified=True, phone="+212600000000",
                            name="Alice", wallet_balance=Decimal("1000"))
        customer.save = MagicMock()

        payload = {"items": [{"slug": "burger", "qty": 1}], "fulfillment_type": "pickup"}
        req = self._post(payload, principal=customer)

        # R16b: debit now goes through wallet_service.debit_wallet; mock it so the unit
        # test does not touch a real DB. The returned tx.amount drives _actual.
        fake_wallet_tx = MagicMock()
        fake_wallet_tx.amount = Decimal("10.00")

        with patch("menu.views.Profile.objects") as profile_mock, \
             patch("menu.views.Dish.objects") as dish_mock, \
             patch("menu.views.Promotion.objects") as promo_mock:
            profile_mock.filter.return_value.first.return_value = _profile()
            promo_mock.filter.return_value = []
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = [dish]
            with patch("accounts.wallet_service.debit_wallet",
                       return_value=fake_wallet_tx,
                       side_effect=debit_side_effect) as debit_mock:
                with patch("menu.views.DishOption.objects") as opt_mock, \
                     patch("menu.views.Order.objects") as order_mock, \
                     patch("menu.views.OrderItem.objects"), \
                     patch("menu.views._generate_order_number", return_value="ORD-CUR"), \
                     patch("menu.views.transaction") as tx_mock, \
                     patch("menu.views.LoyaltyConfig.objects") as loy_mock:
                    opt_mock.filter.return_value = []
                    loy_mock.filter.return_value.first.return_value = None
                    mock_order = MagicMock()
                    mock_order.order_number = "ORD-CUR"
                    mock_order.status = "pending"
                    mock_order.total = Decimal("10.00")
                    mock_order.delivery_fee = Decimal("0")
                    mock_order.currency = currency
                    mock_order.wallet_amount_paid = Decimal("0")
                    mock_order.points_earned = 0
                    order_mock.create.return_value = mock_order
                    cm = MagicMock()
                    cm.__enter__ = MagicMock(return_value=None)
                    cm.__exit__ = MagicMock(return_value=False)
                    tx_mock.atomic.return_value = cm
                    resp = self.view(req)
                    return resp, debit_mock

    def test_non_mad_order_refused_at_chokepoint(self):
        resp, debit_mock = self._drive(currency="USD")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "currency_unsupported")
        # No wallet money moved for the refused non-MAD order.
        self.assertFalse(debit_mock.called)

    def test_mad_order_proceeds_unchanged(self):
        """No regression: a MAD order is NOT refused by the guard (the debit runs)."""
        resp, debit_mock = self._drive(currency="MAD")
        self.assertNotEqual(resp.data.get("code"), "currency_unsupported")
        # The MAD path reaches the wallet debit (debit_wallet is called).
        self.assertTrue(debit_mock.called)


# ═════════════════════════════════════════════════════════════════════════════
# R15b.1 + R16 — marketplace MarketplacePlaceOrderView wallet-debit chokepoint
# ═════════════════════════════════════════════════════════════════════════════

class _FakeDNE(Exception):
    """Stand-in for Model.DoesNotExist so the view's except clause works."""


def _sc_mock():
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


def _mkt_profile():
    p = MagicMock()
    p.is_menu_published = True
    p.cod_enabled = False
    p.cod_min_paid_orders = 3
    p.lat = None
    p.lng = None
    p.platform_delivery_enabled = False
    return p


def _mkt_dish(currency="MAD"):
    d = MagicMock()
    d.slug = "burger"
    d.name = "Burger"
    d.price = Decimal("10.00")
    d.currency = currency
    d.stock_qty = None
    d.category = MagicMock()
    d.category.course = 0
    d.combo_components.all.return_value = []
    return d


def _mkt_customer(cid=7, wallet="1000"):
    """A real (unsaved) Customer principal (RISK IDENTITY-1: read via customer_or_none).
    The inline debit does `wallet_balance - Decimal(...)`; DecimalField holds a Decimal."""
    from accounts.models import Customer
    c = Customer(id=cid, wallet_balance=Decimal(str(wallet)), name="Repeat Diner",
                 phone="+212600000000", phone_verified=True, loyalty_points=0)
    c.save = MagicMock()
    return c


def _fake_menu_models(dish):
    order_cls = MagicMock()
    order_cls.objects.filter.return_value.first.return_value = None
    order_cls.objects.filter.return_value.exists.return_value = False

    dish_cls = MagicMock()
    dish_qs = MagicMock()
    dish_qs.select_related.return_value = dish_qs
    dish_qs.prefetch_related.return_value = [dish]
    dish_cls.objects.filter.return_value = dish_qs
    dish_cls.objects.select_for_update.return_value.filter.return_value = []

    promo_cls = MagicMock()
    promo_cls.objects.filter.return_value.order_by.return_value = []

    do_cls = MagicMock()
    do_cls.objects.filter.return_value.select_related.return_value = []

    m = MagicMock()
    m.Dish = dish_cls
    m.DishOption = do_cls
    m.Order = order_cls
    m.OrderItem = MagicMock()
    m.Promotion = promo_cls
    return m, order_cls


@contextmanager
def _inject_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield
    finally:
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


class MarketplacePlaceOrderCurrencyGuardTests(SimpleTestCase):
    """R16 + R15b.1 on the marketplace path."""

    def setUp(self):
        from accounts.views import MarketplacePlaceOrderView
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _post(self, data, customer=None):
        req = self.factory.post("/api/marketplace/order/", data, format="json")
        req.session = {}
        if customer is not None:
            force_authenticate(req, user=customer)
        return self.view(req)

    def _run_order(self, *, currency, customer, created_order=None, debit_side_effect=None):
        dish = _mkt_dish(currency=currency)
        fake_menu, order_cls = _fake_menu_models(dish)
        if created_order is not None:
            order_cls.objects.create.return_value = created_order

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        # R16b: debit now goes through wallet_service.debit_wallet; mock it so the
        # unit test does not need a real DB. The returned tx.amount drives _actual.
        fake_wallet_tx = MagicMock()
        fake_wallet_tx.amount = Decimal("10.00")

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "pickup",
        }

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls, \
                    patch("accounts.views.Customer") as mock_cust_cls, \
                    patch("accounts.wallet_service.debit_wallet",
                          return_value=fake_wallet_tx,
                          side_effect=debit_side_effect) as debit_mock, \
                    patch("django.db.transaction.atomic", return_value=cm), \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("menu.views._cod_eligible", return_value=False), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.pricing.effective_unit_price",
                          side_effect=lambda d, hh: (d.price, None)):
                mock_profile_cls.objects.filter.return_value.first.return_value = _mkt_profile()
                mock_cust_cls.DoesNotExist = _FakeDNE
                mock_cust_cls.objects.get.return_value = customer
                with _inject_module("menu.models", fake_menu):
                    resp = self._post(payload, customer=customer)
        return resp, order_cls, debit_mock

    def _created_order(self, currency="MAD"):
        o = MagicMock()
        o.order_number = "ORD-MKT"
        o.status = "pending"
        o.total = Decimal("10.00")
        o.delivery_fee = Decimal("0")
        o.currency = currency
        o.wallet_amount_paid = Decimal("0")
        o.scheduled_for = None
        o.commission_amount = Decimal("0")
        o.promotion_discount = Decimal("0")
        o.applied_promotion_name = ""
        o.loyalty_discount = Decimal("0")
        o.redeemed_loyalty_points = None
        o.points_earned = 0
        return o

    def test_non_mad_order_refused_with_currency_unsupported(self):
        customer = _mkt_customer(wallet="1000")  # funded, so the debit step is reached
        created = self._created_order(currency="USD")
        resp, _order_cls, debit_mock = self._run_order(
            currency="USD", customer=customer, created_order=created,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "currency_unsupported")
        # No wallet money moved for the refused non-MAD order.
        self.assertFalse(debit_mock.called)

    def test_mad_order_proceeds_and_debits(self):
        """No regression: a MAD order is not refused and calls debit_wallet."""
        customer = _mkt_customer(wallet="1000")
        created = self._created_order(currency="MAD")
        resp, _order_cls, debit_mock = self._run_order(
            currency="MAD", customer=customer, created_order=created,
        )
        self.assertNotEqual(resp.data.get("code"), "currency_unsupported")
        # The MAD path reaches the wallet debit (debit_wallet is called).
        self.assertTrue(debit_mock.called)

    def test_wallet_debit_failure_logs_to_payments(self):
        """R15b.1: a money-mutation failure in debit_wallet emits on 'payments' with
        attributable ids (no PII/secrets), and the existing 500 path is unchanged."""
        customer = _mkt_customer(wallet="1000")
        created = self._created_order(currency="MAD")
        with self.assertLogs("payments", level="ERROR") as cm:
            resp, _order_cls, _debit = self._run_order(
                currency="MAD", customer=customer, created_order=created,
                debit_side_effect=RuntimeError("ledger write failed"),
            )
        joined = "\n".join(cm.output)
        self.assertIn("order_number=ORD-MKT", joined)
        self.assertIn("customer_id=7", joined)
        # Failure bubbles to the existing app.customer handler → unchanged 500 response.
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(resp.data.get("code"), "server_error")
