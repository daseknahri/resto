"""OPS-5f accounts-app money / IDOR / auth hardening — Contract Tests

Covers the OPS-5f accounts cluster (scouted from OPS-5e):

  A. MarketplacePlaceOrderView DishOption price manipulation (accounts/views.py):
       1. A foreign / cross-dish option id is rejected with 400 {code: stale_options}.
       2. An UNKNOWN option id is rejected the same way.
       3. price_delta is applied ONLY for validated, dish-bound options (the loop
          uses select_related("dish") + opt.dish.slug == dish.slug).

  B. De-approved driver can't bank earnings (accounts/views.py):
       4. A driver whose driver_approved was revoked is 403'd at the DELIVERED
          (earnings-emitting) transition — earnings never credited.
       5. An approved driver clears that gate (reaches the delivery-code check).

  C. DeliveryRatingView customer-branch IDOR + throttle (accounts/views.py):
       6. A session customer who does NOT own the order cannot write the rating (403).
       7. The owning session customer CAN write the rating.
       8. throttle_classes wires DeliveryRatingThrottle (scope delivery_rating).

  D. Voucher redeem funnelled through credit_wallet (accounts/views.py):
       9. CustomerWalletRedeemVoucherView credits via wallet_service.credit_wallet
          with a stable idempotency_key (voucher:<id>) — not a manual balance write.

  E. Password-reset host poisoning + session invalidation:
      10. build_frontend_base_url ignores a spoofed request host for tenant-less users.
      11. PasswordResetConfirmSerializer.save() invalidates the user's other sessions.

  F. Throttle wiring (accounts/throttles.py + config/rest_framework.py):
      12. DeliveryRatingThrottle + OwnerWalletChargeThrottle exist with the exact
          scopes, and both scopes are registered in DEFAULT_THROTTLE_RATES.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

import inspect
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _FakeDNE(Exception):
    """Reusable fake DoesNotExist for mocked managers."""


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _noop_sc():
    """schema_context replacement that is a no-op context manager."""
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


def _dish(slug="burger", name="Burger", price="10.00", currency="USD"):
    d = SimpleNamespace()
    d.slug = slug
    d.name = name
    d.price = Decimal(price)
    d.currency = currency
    # combo_components.all() → [] ; category.course → 0
    d.combo_components = MagicMock()
    d.combo_components.all.return_value = []
    d.category = SimpleNamespace(course=0)
    return d


def _option(oid, dish_slug, price_delta="0.00", name="opt"):
    opt = SimpleNamespace()
    opt.id = oid
    opt.name = name
    opt.price_delta = Decimal(price_delta)
    opt.dish = SimpleNamespace(slug=dish_slug)
    return opt


# ═════════════════════════════════════════════════════════════════════════════
# A. MarketplacePlaceOrderView DishOption price manipulation
# ═════════════════════════════════════════════════════════════════════════════

class MarketplaceOptionBindingTests(SimpleTestCase):
    """A customer must not be able to attach a foreign / negative-delta option to a
    cheap dish and drive the wallet-prepaid total down."""

    def setUp(self):
        from accounts.views import MarketplacePlaceOrderView
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _drive(self, *, dish, options, item):
        """Drive the marketplace order view (pickup) far enough to reach the
        per-item option loop. Returns the DRF Response.

        Everything between tenant resolution and the option loop is mocked so the
        loop's binding check is what decides the outcome. A sentinel is raised right
        AFTER the loop (the promo query) so a request that PASSES the gate surfaces
        as 500 server_error rather than 400 stale_options."""
        import menu.models as mm

        tenant = SimpleNamespace(
            slug="bistro", name="Bistro", schema_name="bistro",
            id=1, lifecycle_status="active",
        )

        # Dish queryset → dishes_map
        dish_qs = MagicMock()
        dish_qs.select_related.return_value.prefetch_related.return_value = [dish]
        # DishOption queryset → options_map (select_related("dish"))
        opt_qs = MagicMock()
        opt_qs.select_related.return_value = options

        profile = MagicMock()
        profile.is_menu_published = True
        profile.platform_delivery_enabled = False
        prof_qs = MagicMock()
        prof_qs.first.return_value = profile

        from tenancy.models import Tenant as _RealTenant

        # The production view imports Profile from tenancy.models (the import bug that
        # used to point at menu.models is fixed). Patch it where the view reads it.
        _ProfileStub = MagicMock()
        _ProfileStub.objects.filter.return_value = prof_qs

        with patch("tenancy.models.Tenant") as MockTenant, \
             patch("django_tenants.utils.schema_context", _noop_sc()), \
             patch("tenancy.models.Profile", _ProfileStub), \
             patch.object(mm.Dish, "objects") as MockDishObjs, \
             patch.object(mm.DishOption, "objects") as MockDOObjs, \
             patch.object(mm.Order, "objects") as MockOrderObjs, \
             patch.object(mm.Promotion, "objects") as MockPromoObjs, \
             patch("accounts.views._compute_is_open_now", return_value=True), \
             patch("menu.pricing.get_active_happy_hours", return_value=[]), \
             patch("menu.pricing.effective_unit_price",
                   side_effect=lambda d, hh: (d.price, None)), \
             patch("menu.views._profile_now", return_value=None):
            MockTenant.LifecycleStatus = _RealTenant.LifecycleStatus
            MockTenant.DoesNotExist = _RealTenant.DoesNotExist
            tenant.lifecycle_status = _RealTenant.LifecycleStatus.ACTIVE
            MockTenant.objects.get.return_value = tenant
            MockDishObjs.filter.return_value = dish_qs
            MockDOObjs.filter.return_value = opt_qs
            # No idempotency key path
            MockOrderObjs.filter.return_value.first.return_value = None
            # Promo query is the first DB hit AFTER the option loop → sentinel proves
            # a request that reached here passed the binding gate.
            MockPromoObjs.filter.side_effect = RuntimeError("reached-promo")

            req = self.factory.post("/api/marketplace/order/", {
                "restaurant": "bistro",
                "fulfillment_type": "pickup",
                "items": [item],
            }, format="json")
            req.user = _anon()
            req.session = {}
            return self.view(req)

    def test_foreign_option_rejected_stale_options(self):
        """An option bound to a DIFFERENT dish is rejected with stale_options."""
        dish = _dish(slug="burger")
        foreign = _option(99, dish_slug="pizza", price_delta="-9.00")
        resp = self._drive(
            dish=dish, options=[foreign],
            item={"slug": "burger", "qty": 1, "option_ids": [99]},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "stale_options")
        self.assertEqual(resp.data["dish_slug"], "burger")
        self.assertIn(99, resp.data["invalid_option_ids"])

    def test_unknown_option_rejected_stale_options(self):
        """An option id with no matching row is rejected too (no silent skip)."""
        dish = _dish(slug="burger")
        resp = self._drive(
            dish=dish, options=[],  # options_map empty → id 5 unknown
            item={"slug": "burger", "qty": 1, "option_ids": [5]},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "stale_options")
        self.assertIn(5, resp.data["invalid_option_ids"])

    def test_bound_option_passes_gate(self):
        """A correctly dish-bound option is NOT rejected — the request proceeds
        past the loop (surfaced here as the post-loop sentinel, i.e. 500)."""
        dish = _dish(slug="burger")
        bound = _option(7, dish_slug="burger", price_delta="1.50")
        resp = self._drive(
            dish=dish, options=[bound],
            item={"slug": "burger", "qty": 1, "option_ids": [7]},
        )
        # Did NOT short-circuit at the binding gate.
        self.assertNotEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_select_related_and_binding_in_source(self):
        """price_delta must only be summed over validated, dish-bound options."""
        from accounts.views import MarketplacePlaceOrderView
        src = inspect.getsource(MarketplacePlaceOrderView.post)
        self.assertIn('.select_related("dish")', src)
        self.assertIn("opt_dish_slug != dish.slug", src)
        self.assertIn("stale_options", src)
        # The delta is applied over the validated set, not the raw option_ids.
        self.assertIn("for opt in _bound_options", src)


# ═════════════════════════════════════════════════════════════════════════════
# B. De-approved driver can't bank earnings
# ═════════════════════════════════════════════════════════════════════════════

class DriverEarningsApprovalGateTests(SimpleTestCase):
    """A driver whose approval was revoked must not advance a job to DELIVERED
    (which credits earnings)."""

    def setUp(self):
        from accounts.views import DriverJobStatusUpdateView
        self.factory = APIRequestFactory()
        self.view = DriverJobStatusUpdateView.as_view()

    def _drive(self, *, still_approved):
        import accounts.models as am

        customer = MagicMock(pk=5, id=5, name="Drv", is_driver_online=True)

        job = MagicMock()
        job.status = "picked_up"  # picked_up → delivered is the credit transition
        job.code_locked_until = None
        job.code_attempts = 0
        job.tenant_id = 1

        # select_for_update().get(...) → job
        sfu = MagicMock()
        sfu.get.return_value = job

        # Customer manager: the initial is_driver lookup and the approval re-check.
        cust_mgr = MagicMock()
        cust_mgr.get.return_value = customer
        cust_mgr.filter.return_value.exists.return_value = still_approved

        @contextmanager
        def _atomic(*a, **k):
            yield

        with patch.object(am.DeliveryJob.objects, "select_for_update", return_value=sfu), \
             patch("accounts.views.Customer", cust_mgr_owner := MagicMock()), \
             patch("django.db.transaction.atomic", _atomic), \
             patch("accounts.views._order_delivery_code", return_value="") as _odc, \
             patch("accounts.views._complete_delivered_order") as _cdo, \
             patch("accounts.views._notify_customer_milestone"), \
             patch("accounts.views._batch_business_types", return_value={1: "restaurant"}), \
             patch("accounts.views._serialize_delivery_job", return_value={}):
            cust_mgr_owner.objects = cust_mgr
            cust_mgr_owner.DoesNotExist = _FakeDNE

            req = self.factory.patch(
                "/api/driver/jobs/1/status/", {"status": "delivered"}, format="json"
            )
            req.session = {"customer_id": 5}
            resp = self.view(req, job_id=1)
            return resp, _cdo, _odc

    def test_revoked_driver_blocked_no_earnings(self):
        """driver_approved revoked → 403 at DELIVERED, earnings never credited."""
        resp, complete_mock, _odc = self._drive(still_approved=False)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "driver_not_approved")
        complete_mock.assert_not_called()  # _complete_delivered_order → _credit_driver_earnings

    def test_approved_driver_clears_gate(self):
        """Still-approved driver passes the approval gate (reaches the code check)."""
        resp, complete_mock, odc_mock = self._drive(still_approved=True)
        # Approval gate passed → delivery-code check ran (no bad-code lockout since
        # _order_delivery_code returned "" → check skipped → completes).
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        odc_mock.assert_called()
        complete_mock.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# C. DeliveryRatingView customer-branch IDOR + throttle
# ═════════════════════════════════════════════════════════════════════════════

class DeliveryRatingOwnershipTests(SimpleTestCase):
    """Only the session customer who owns the order may write the customer→driver
    rating."""

    def setUp(self):
        from accounts.views import DeliveryRatingView
        self.factory = APIRequestFactory()
        self.view = DeliveryRatingView.as_view()

    def _drive(self, *, session_cid, order_customer_id):
        import accounts.models as am
        from accounts.models import DeliveryJob
        import menu.models as mm

        tenant = SimpleNamespace(id=1, slug="bistro", schema_name="bistro")

        job = MagicMock()
        job.status = DeliveryJob.Status.DELIVERED

        order = SimpleNamespace(customer_id=order_customer_id)
        order_qs = MagicMock()
        order_qs.only.return_value.first.return_value = order

        with patch("tenancy.models.Tenant") as MockTenant, \
             patch.object(am.DeliveryJob.objects, "get", return_value=job), \
             patch("django_tenants.utils.schema_context", _noop_sc()), \
             patch.object(mm.Order, "objects") as MockOrderObjs:
            MockTenant.DoesNotExist = _FakeDNE
            MockTenant.objects.get.return_value = tenant
            MockOrderObjs.filter.return_value = order_qs

            req = self.factory.post(
                "/api/marketplace/track/ORD-1/rate/?restaurant=bistro",
                {"role": "customer", "score": 5, "note": "great"}, format="json",
            )
            req.session = {"customer_id": session_cid} if session_cid is not None else {}
            resp = self.view(req, order_number="ORD-1")
            return resp, job

    def test_non_owner_session_rejected(self):
        resp, job = self._drive(session_cid=2, order_customer_id=999)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_order_owner")
        job.save.assert_not_called()

    def test_anon_customer_rejected(self):
        resp, job = self._drive(session_cid=None, order_customer_id=999)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        job.save.assert_not_called()

    def test_owner_session_can_rate(self):
        resp, job = self._drive(session_cid=5, order_customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(job.customer_driver_rating, 5)
        job.save.assert_called_once()

    def test_throttle_wired(self):
        from accounts.views import DeliveryRatingView
        from accounts.throttles import DeliveryRatingThrottle
        self.assertIn(DeliveryRatingThrottle, DeliveryRatingView.throttle_classes)


# ═════════════════════════════════════════════════════════════════════════════
# D. Voucher redeem funnelled through credit_wallet
# ═════════════════════════════════════════════════════════════════════════════

class VoucherRedeemCreditWalletTests(SimpleTestCase):
    """The voucher credit must go through wallet_service.credit_wallet (locks the
    customer row, idempotent) — not a manual read-modify-write of wallet_balance."""

    def setUp(self):
        from accounts.views import CustomerWalletRedeemVoucherView
        self.factory = APIRequestFactory()
        self.view = CustomerWalletRedeemVoucherView.as_view()

    def test_redeem_calls_credit_wallet_with_stable_key(self):
        import accounts.models as am

        customer = SimpleNamespace(id=42, phone_verified=True, wallet_balance=Decimal("0.00"))

        voucher = MagicMock()
        voucher.id = 7
        voucher.code = "ABCD1234"
        voucher.amount = Decimal("25.00")
        voucher.is_used = False
        voucher.used_by_id = None
        voucher.expires_at = None
        voucher.note = "promo"

        voucher_qs = MagicMock()
        voucher_qs.get.return_value = voucher

        tx = SimpleNamespace(balance_after=Decimal("25.00"))

        @contextmanager
        def _atomic(*a, **k):
            yield

        with patch.object(am.WalletVoucher.objects, "select_for_update", return_value=voucher_qs), \
             patch("django.db.transaction.atomic", _atomic), \
             patch("accounts.wallet_service.credit_wallet", return_value=tx) as mock_credit:
            req = self.factory.post(
                "/api/customer/wallet/redeem-voucher/", {"code": "abcd1234"}, format="json"
            )
            req.user = MagicMock(is_authenticated=True)
            req.customer = customer
            req.session = {}
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["new_balance"], "25.00")
        mock_credit.assert_called_once()
        args, kwargs = mock_credit.call_args
        # Positional: (customer_id, amount)
        self.assertEqual(args[0], 42)
        self.assertEqual(args[1], Decimal("25.00"))
        self.assertEqual(kwargs["idempotency_key"], "voucher:7")
        self.assertEqual(kwargs["reference"], "ABCD1234")

    def test_no_manual_balance_write_in_source(self):
        """The manual wallet_balance += amount write must be gone."""
        from accounts.views import CustomerWalletRedeemVoucherView
        src = inspect.getsource(CustomerWalletRedeemVoucherView.post)
        self.assertNotIn("customer.wallet_balance = customer.wallet_balance + voucher.amount", src)
        self.assertIn("credit_wallet", src)
        self.assertIn('idempotency_key=f"voucher:{voucher.id}"', src)


# ═════════════════════════════════════════════════════════════════════════════
# E. Password-reset host poisoning + session invalidation
# ═════════════════════════════════════════════════════════════════════════════

class ResetLinkHostTests(SimpleTestCase):
    """build_frontend_base_url must NOT honour a spoofed request host for a
    tenant-less user (host-header poisoning of the reset link)."""

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
    def test_spoofed_host_ignored_for_tenantless_user(self):
        from accounts.views import build_frontend_base_url
        req = MagicMock()
        req.get_host.return_value = "evil.attacker.com"
        user = MagicMock()
        user.tenant = None
        url = build_frontend_base_url(req, user)
        self.assertEqual(url, "https://app.kepoli.com")
        self.assertNotIn("attacker", url)

    def test_no_get_host_fallback_in_source(self):
        from accounts.views import build_frontend_base_url
        src = inspect.getsource(build_frontend_base_url)
        # The vulnerable get_host() fallback assignment must be gone (it may still be
        # named in an explanatory comment — strip comments before asserting).
        code_lines = [ln.split("#", 1)[0] for ln in src.splitlines()]
        code = "\n".join(code_lines)
        self.assertNotIn("get_host()", code)
        self.assertIn("_canonical_brand_host", code)


class ResetInvalidatesSessionsTests(SimpleTestCase):
    """PasswordResetConfirmSerializer.save() must invalidate the user's other
    sessions on reset so a stolen/active session dies."""

    def _serializer(self, reset):
        from accounts.serializers import PasswordResetConfirmSerializer
        s = PasswordResetConfirmSerializer()
        s._validated_data = {"reset": reset, "password": "newpass999"}
        s._errors = {}
        return s

    def test_save_invalidates_user_sessions(self):
        reset = MagicMock()
        reset.user = MagicMock(pk=11)
        reset.user.set_password = MagicMock()

        # Two sessions in the store: one belongs to the user, one to someone else.
        mine = MagicMock(session_key="aaa")
        mine.get_decoded.return_value = {"_auth_user_id": "11"}
        other = MagicMock(session_key="bbb")
        other.get_decoded.return_value = {"_auth_user_id": "99"}

        with patch("django.contrib.sessions.models.Session") as MockSession:
            MockSession.objects.filter.return_value = [mine, other]
            # Second .filter(...) (the delete path) returns a manager with .delete()
            delete_qs = MagicMock()

            def _filter(*args, **kwargs):
                if "session_key__in" in kwargs:
                    return delete_qs
                return [mine, other]

            MockSession.objects.filter.side_effect = _filter
            self._serializer(reset).save()

            # Only the user's own session key is deleted.
            called = [c for c in MockSession.objects.filter.call_args_list
                      if "session_key__in" in c.kwargs]
            self.assertTrue(called, "delete-by-session_key__in must be issued")
            self.assertEqual(list(called[0].kwargs["session_key__in"]), ["aaa"])
            delete_qs.delete.assert_called_once()

    def test_save_still_resets_password(self):
        reset = MagicMock()
        reset.user = MagicMock(pk=11)
        with patch("django.contrib.sessions.models.Session") as MockSession:
            MockSession.objects.filter.return_value = []
            user = self._serializer(reset).save()
        reset.user.set_password.assert_called_once_with("newpass999")
        reset.mark_used.assert_called_once()
        self.assertIs(user, reset.user)

    def test_invalidation_in_source(self):
        from accounts.serializers import PasswordResetConfirmSerializer
        src = inspect.getsource(PasswordResetConfirmSerializer.save)
        self.assertIn("_invalidate_user_sessions", src)


# ═════════════════════════════════════════════════════════════════════════════
# F. Throttle wiring
# ═════════════════════════════════════════════════════════════════════════════

class ThrottleWiringTests(SimpleTestCase):
    def test_delivery_rating_throttle_scope(self):
        from accounts.throttles import DeliveryRatingThrottle
        self.assertEqual(DeliveryRatingThrottle.scope, "delivery_rating")

    def test_owner_wallet_charge_throttle_scope(self):
        from accounts.throttles import OwnerWalletChargeThrottle
        self.assertEqual(OwnerWalletChargeThrottle.scope, "owner_wallet_charge")

    def test_owner_wallet_charge_keyed_per_actor(self):
        from accounts.throttles import OwnerWalletChargeThrottle
        t = OwnerWalletChargeThrottle()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=True, pk=77)
        key = t.get_cache_key(req, view=None)
        self.assertIn("owner:77", key)

    def test_scopes_registered_in_rates(self):
        from config.rest_framework import REST_FRAMEWORK
        rates = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertEqual(rates["delivery_rating"], "30/hour")
        self.assertEqual(rates["owner_wallet_charge"], "30/min")
