"""
Hardening sweep — three verified money bugs in accounts/views.py.

  Bug 1  MarketplacePlaceOrderView: when an auto-promo hits its usage cap
         concurrently, the stripped-total recompute must KEEP the still-valid
         loyalty discount (the points were already debited) — dropping it both
         burned the customer's points AND overcharged them.
  Bug 2  AdminWalletBonusView: without a client idempotency_key a retry
         double-credited real money. The endpoint now derives a deterministic
         server-side fingerprint (actor + amount + target set) and dedups on it.
  Bug 3  AdminCreateDeliveryJobView: negative delivery_fee / driver_payout must
         be rejected with a 400.

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema switch).
The marketplace view imports its models at function scope INSIDE schema_context,
so fakes are injected through sys.modules (same technique as test_a4_marketplace_cod).
"""
import sys
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import (
    MarketplacePlaceOrderView,
    AdminWalletBonusView,
    AdminCreateDeliveryJobView,
)
from accounts.models import User


# ── Shared helpers ────────────────────────────────────────────────────────────

class _FakeDNE(Exception):
    """Stand-in for Model.DoesNotExist so the view's except clauses work."""


def _admin(uid=1):
    """Platform admin with a STABLE id — Bug 2's server fingerprint hashes the
    actor id, so both calls of a retry must carry the same principal."""
    u = MagicMock()
    u.__class__ = User
    u.id = uid
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _non_admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


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


def _sc_mock():
    """schema_context replacement that does nothing (no DB switch)."""
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


# ── Bug 1 — marketplace promo-cap recompute must keep the loyalty discount ─────

def _dish(slug="burger", price="10.00", currency="MAD"):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.price = Decimal(price)
    d.currency = currency
    d.stock_qty = None  # unlimited — explicit so MagicMock isn't truthy
    d.category = MagicMock()
    d.category.course = 0
    d.category.station = ""
    d.combo_components.all.return_value = []
    return d


def _customer(cid=7, wallet="100.00", points=20):
    """A real (unsaved) Customer principal — the view reads the linked customer
    via customer_or_none(request.user), which duck-types on the model class name,
    so a MagicMock would not pass."""
    from accounts.models import Customer
    c = Customer(
        id=cid,
        wallet_balance=Decimal(wallet),
        name="Repeat Diner",
        phone="+212600000000",
        loyalty_points=points,
    )
    c.save = MagicMock()
    return c


def _promo():
    """A live percentage promo with a usage cap (so the bounded counter runs)."""
    p = MagicMock()
    p.pk = 1
    p.max_uses = 5
    p.use_count = 0
    p.min_order_amount = "0"
    p.promo_type = "percentage"
    p.discount_value = 50           # 50% of a 10.00 subtotal → 5.00 discount
    p.name = "Half Off"
    return p


def _fake_menu_models(dish, promo, *, promo_update_rows):
    """Fake menu.models module exposing what the order path imports.

    `promo_update_rows` is what the bounded promo counter UPDATE returns — set to
    0 to simulate the usage cap being reached concurrently (the branch under test).
    """
    order_cls = MagicMock()
    order_cls.objects.filter.return_value.first.return_value = None    # no idempotent replay
    order_cls.objects.filter.return_value.exists.return_value = False  # order-number loop

    dish_cls = MagicMock()
    dish_qs = MagicMock()
    dish_qs.select_related.return_value = dish_qs
    dish_qs.prefetch_related.return_value = [dish]
    dish_cls.objects.filter.return_value = dish_qs
    dish_cls.objects.select_for_update.return_value.filter.return_value = []

    promo_cls = MagicMock()
    promo_cls.objects.filter.return_value.order_by.return_value = [promo]  # best-promo scan
    promo_cls.objects.filter.return_value.update.return_value = promo_update_rows

    do_cls = MagicMock()
    do_cls.objects.filter.return_value.select_related.return_value = []

    m = MagicMock()
    m.Dish = dish_cls
    m.DishOption = do_cls
    m.Order = order_cls
    m.OrderItem = MagicMock()
    m.Promotion = promo_cls
    m.LoyaltyConfig = MagicMock()  # truthy config → redemption + earning blocks run
    return m, order_cls


class MarketplacePromoCapLoyaltyTests(SimpleTestCase):
    """Bug 1 regression: promo cap hit concurrently must keep the loyalty discount."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _post(self, data, customer):
        req = self.factory.post("/api/marketplace/order/", data, format="json")
        req.session = {}
        force_authenticate(req, user=customer)
        return self.view(req)

    def _run(self, *, promo_update_rows):
        dish = _dish()
        promo = _promo()
        customer = _customer(cid=7, wallet="100.00", points=20)
        fake_menu, order_cls = _fake_menu_models(dish, promo, promo_update_rows=promo_update_rows)

        created = MagicMock()
        created.order_number = "ORD-TEST"
        created.status = "pending"
        created.total = Decimal("8.00")
        created.delivery_fee = Decimal("0")
        created.wallet_amount_paid = Decimal("0")
        created.commission_amount = Decimal("0.30")
        created.promotion_discount = Decimal("0")
        created.applied_promotion_name = ""
        created.loyalty_discount = Decimal("2.00")
        created.redeemed_loyalty_points = 20
        created.points_earned = 0
        created.scheduled_for = None
        created.currency = "MAD"
        order_cls.objects.create.return_value = created

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)

        wallet_tx = MagicMock()
        wallet_tx.amount = Decimal("8.00")  # fully settles the corrected total → PAID

        profile = MagicMock()
        profile.is_menu_published = True
        profile.platform_delivery_enabled = False
        profile.timezone = "UTC"

        optin_m = MagicMock()
        optin_m.objects.filter.return_value.values_list.return_value = []  # no flash sales

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 1}],
            "fulfillment_type": "pickup",
            "redeem_points": 20,
        }

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls, \
                    patch("accounts.views.Customer") as mock_cust_cls, \
                    patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                    patch("django.db.transaction.atomic", return_value=cm), \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("accounts.views._is_promo_active_now", return_value=True), \
                    patch("accounts.wallet_service.debit_wallet", return_value=wallet_tx), \
                    patch("menu.views._orders_paused_now", return_value=False), \
                    patch("menu.views._busy_extra_minutes_now", return_value=0), \
                    patch("menu.views._auto_accept_now", return_value=False), \
                    patch("menu.views._cod_eligible", return_value=False), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.views._size_loyalty_redemption",
                          return_value=(Decimal("2.00"), 20, None)), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.pricing.effective_unit_price",
                          side_effect=lambda d, hh: (d.price, None)):
                mock_profile_cls.objects.filter.return_value.first.return_value = profile
                mock_cust_cls.DoesNotExist = _FakeDNE
                mock_cust_cls.objects.get.return_value = customer
                mock_cust_cls.objects.select_for_update.return_value.get.return_value = customer
                with _inject_module("menu.models", fake_menu):
                    resp = self._post(payload, customer=customer)
        return resp, order_cls

    def test_promo_cap_hit_keeps_loyalty_discount_no_overcharge(self):
        """food 10.00 (pickup, fee 0), 50% promo (5.00), loyalty 2.00 (20 pts).
        Pre-cap total = 10 - 5 - 2 = 3.00. The promo counter UPDATE returns 0
        (cap reached concurrently), so the promo is stripped:
          FIXED  → total = 10 + 0 - 2 = 8.00 (loyalty kept)
          BUGGY  → total = 10 + 0     = 10.00 (loyalty dropped → overcharge)."""
        resp, order_cls = self._run(promo_update_rows=0)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(order_cls.objects.create.called)
        kwargs = order_cls.objects.create.call_args.kwargs

        # The promo is gone, but the loyalty discount (points already spent) stays.
        self.assertEqual(kwargs["total"], Decimal("8.00"))
        self.assertEqual(kwargs["loyalty_discount"], Decimal("2.00"))
        self.assertEqual(kwargs["redeemed_loyalty_points"], 20)
        self.assertEqual(kwargs["promotion_discount"], Decimal("0"))
        # The old bug shipped 10.00 (loyalty burned + overcharge) — guard against it.
        self.assertNotEqual(kwargs["total"], Decimal("10.00"))

    def test_promo_not_capped_applies_both_discounts(self):
        """Control: when the promo counter UPDATE succeeds (rows=1), BOTH the promo
        and the loyalty discount apply → total = 10 - 5 - 2 = 3.00."""
        resp, order_cls = self._run(promo_update_rows=1)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        kwargs = order_cls.objects.create.call_args.kwargs
        self.assertEqual(kwargs["total"], Decimal("3.00"))
        self.assertEqual(kwargs["loyalty_discount"], Decimal("2.00"))
        self.assertEqual(kwargs["promotion_discount"], Decimal("5.00"))


# ── Bug 2 — AdminWalletBonus self-defending idempotency (no client key) ────────

class AdminWalletBonusSelfDefendingIdempotencyTests(SimpleTestCase):
    """Bug 2 regression: a retry with NO client idempotency_key must not
    double-credit — the endpoint dedups on a server-derived fingerprint."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminWalletBonusView.as_view()

    def _post(self, data, user):
        req = self.factory.post("/api/admin/wallet/bonus/", data, format="json")
        req.user = user
        return self.view(req)

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_retry_without_key_deduped_by_cache_mutex(self, mock_cust_objs, mock_tx_objs):
        """Two identical POSTs (same actor+amount+targets, NO idempotency_key):
        the second is deduped and issues NO second credit. Within the mutex TTL the
        cache lock catches it before any wallet mutation."""
        from django.core.cache import cache
        cache.clear()
        try:
            def _vl_se(*args, **kwargs):
                if kwargs.get("flat"):
                    return [1, 2]
                return [(1, "10.00"), (2, "10.00")]
            mock_cust_objs.filter.return_value.values_list.side_effect = _vl_se
            mock_cust_objs.filter.return_value.update.return_value = 2
            mock_tx_objs.filter.return_value.exists.return_value = False
            mock_tx_objs.bulk_create.return_value = []

            user = _admin(uid=42)  # SAME principal for both calls (stable fingerprint)
            body = {"amount": "10.00", "customer_ids": [1, 2], "note": "Thanks"}
            with patch("django.db.transaction.atomic"):
                first = self._post(body, user=user)
                second = self._post(body, user=user)

            self.assertEqual(first.status_code, status.HTTP_200_OK)
            self.assertEqual(first.data["issued_to"], 2)

            # Second identical call, no key → deduped, no second credit.
            self.assertTrue(second.data.get("duplicate"))
            self.assertEqual(second.data["issued_to"], 0)
            self.assertEqual(mock_cust_objs.filter.return_value.update.call_count, 1)
            self.assertEqual(mock_tx_objs.bulk_create.call_count, 1)
        finally:
            cache.clear()

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_retry_without_key_deduped_by_durable_ledger(self, mock_cust_objs, mock_tx_objs):
        """The DURABLE guard is the WalletTransaction dedup query on the fingerprint:
        it must still block a retry after the short cache mutex has expired."""
        from django.core.cache import cache
        cache.clear()
        try:
            def _vl_se(*args, **kwargs):
                if kwargs.get("flat"):
                    return [1, 2]
                return [(1, "10.00"), (2, "10.00")]
            mock_cust_objs.filter.return_value.values_list.side_effect = _vl_se
            mock_cust_objs.filter.return_value.update.return_value = 2
            mock_tx_objs.bulk_create.return_value = []

            user = _admin(uid=42)
            body = {"amount": "10.00", "customer_ids": [1, 2]}

            # First credit succeeds — no prior ledger rows for this fingerprint.
            mock_tx_objs.filter.return_value.exists.return_value = False
            with patch("django.db.transaction.atomic"):
                first = self._post(body, user=user)
            self.assertEqual(first.data["issued_to"], 2)

            # Simulate the cache mutex expiring; the ledger now has rows for this
            # fingerprint → the durable dedup blocks the re-credit.
            cache.clear()
            mock_tx_objs.filter.return_value.exists.return_value = True
            with patch("django.db.transaction.atomic"):
                second = self._post(body, user=user)

            self.assertTrue(second.data.get("duplicate"))
            self.assertEqual(mock_tx_objs.bulk_create.call_count, 1)  # no second credit
        finally:
            cache.clear()

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_distinct_amount_not_falsely_deduped(self, mock_cust_objs, mock_tx_objs):
        """A genuinely different bonus (different amount) has a different fingerprint,
        so it is NOT falsely deduped against the first."""
        from django.core.cache import cache
        cache.clear()
        try:
            def _vl_se(*args, **kwargs):
                if kwargs.get("flat"):
                    return [1, 2]
                return [(1, "0.00"), (2, "0.00")]
            mock_cust_objs.filter.return_value.values_list.side_effect = _vl_se
            mock_cust_objs.filter.return_value.update.return_value = 2
            mock_tx_objs.filter.return_value.exists.return_value = False
            mock_tx_objs.bulk_create.return_value = []

            user = _admin(uid=42)
            with patch("django.db.transaction.atomic"):
                r1 = self._post({"amount": "10.00", "customer_ids": [1, 2]}, user=user)
                r2 = self._post({"amount": "25.00", "customer_ids": [1, 2]}, user=user)

            self.assertEqual(r1.data["issued_to"], 2)
            self.assertEqual(r2.data["issued_to"], 2)  # not deduped
            self.assertEqual(mock_tx_objs.bulk_create.call_count, 2)
        finally:
            cache.clear()


# ── Bug 3 — AdminCreateDeliveryJob rejects negative money fields ───────────────

class AdminCreateDeliveryJobNegativeMoneyTests(SimpleTestCase):
    """Bug 3 regression: negative delivery_fee / driver_payout → 400."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCreateDeliveryJobView.as_view()

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/delivery-jobs/", data, format="json")
        req.user = user or _admin()
        return self.view(req)

    def test_negative_delivery_fee_returns_400(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = False
            resp = self._post({
                "tenant_id": 1,
                "order_number": "ORD-NEG1",
                "delivery_fee": "-5.00",
            })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # No job may be created on a rejected input.
        self.assertFalse(mock_dj.objects.create.called)

    def test_negative_driver_payout_returns_400(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = False
            resp = self._post({
                "tenant_id": 1,
                "order_number": "ORD-NEG2",
                "driver_payout": "-3.00",
            })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_dj.objects.create.called)

    def test_zero_and_positive_fees_still_accepted(self):
        """Control: 0 / positive values remain valid (a job is created)."""
        job = MagicMock()
        job.id = 1
        job.business_type = "restaurant"
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = False
            mock_dj.objects.create.return_value = job
            with patch("accounts.views._serialize_delivery_job", return_value={"id": 1}):
                resp = self._post({
                    "tenant_id": 1,
                    "order_number": "ORD-OK",
                    "delivery_fee": "0",
                    "driver_payout": "3.00",
                })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_dj.objects.create.called)
