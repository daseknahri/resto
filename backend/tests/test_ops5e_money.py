"""OPS-5e Money-path IDOR / brute-force / idempotency hardening — Contract Tests

Covers the OPS-5e money-path cluster:

  A. Driver cash-out brute-force lockout (accounts/driver_service.py):
       1. After N failed confirms (not_found / expired) the actor is locked out.
       2. A legit first-try confirm never increments the counter and resets it.
       3. Both owner cash-out endpoints wire DriverCashoutConfirmThrottle.

  B. Wallet idempotency replay hardening (accounts/wallet_service.py + menu/views.py):
       4. credit_wallet / debit_wallet refuse a key that resolves to ANOTHER customer.
       5. Same-customer retry still returns the existing tx (backwards compatible).
       6. A partial-debit retry (different stored amount) is still allowed.
       7. credit_tenant_float refuses a key that resolves to ANOTHER tenant.
       8. OwnerWalletChargeView namespaces the external key with the tenant schema.

  C. CustomerOrderRateView ownership gate + throttle (menu/views.py):
       9. A caller whose session customer doesn't own the order gets 403.
      10. throttle_classes wires CustomerOrderRateThrottle (scope customer_order_rate).

  D. TranslateView provider-body leak (tenancy/api.py):
      11. A provider HTTPError returns a generic body with NO upstream 'body' field.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.driver_service import (
    confirm_cashout,
    CashoutError,
    CASHOUT_CONFIRM_MAX_FAILURES,
    _cashout_fail_cache_key,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _pending_request(amount="120.00"):
    from django.utils import timezone
    from datetime import timedelta
    return SimpleNamespace(
        id=7, driver_id=5, amount=Decimal(amount), code="123456",
        status="pending", expires_at=timezone.now() + timedelta(minutes=10),
        currency="MAD", save=MagicMock(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# A. Driver cash-out brute-force lockout
# ═════════════════════════════════════════════════════════════════════════════

class CashoutLockoutTests(SimpleTestCase):
    """confirm_cashout must lock an actor out after repeated failed code attempts."""

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

    def _no_match(self):
        (self.m["dcr"].objects.select_for_update
            .return_value.filter.return_value.first.return_value) = None

    def _match(self, req):
        (self.m["dcr"].objects.select_for_update
            .return_value.filter.return_value.first.return_value) = req

    def test_locks_out_after_max_failures(self):
        """The (N+1)th confirm with wrong codes is rejected with code 'locked'."""
        from django.core.cache import cache
        cache.clear()
        self._no_match()
        # N failures (each not_found) — all raise not_found, none locked yet.
        for _ in range(CASHOUT_CONFIRM_MAX_FAILURES):
            with self.assertRaises(CashoutError) as ctx:
                confirm_cashout("000000", tenant_id=3, actor_user_id=8)
            self.assertEqual(ctx.exception.code, "not_found")
        # The next attempt is locked out before the DB is even consulted.
        with self.assertRaises(CashoutError) as ctx:
            confirm_cashout("000000", tenant_id=3, actor_user_id=8)
        self.assertEqual(ctx.exception.code, "locked")

    def test_legit_first_try_never_increments_and_resets(self):
        """A correct first-try confirm succeeds and clears any (other actor's) counter."""
        from django.core.cache import cache
        cache.clear()
        req = _pending_request()
        self._match(req)
        self.m["debit"].return_value = SimpleNamespace(id=99)
        out = confirm_cashout("123456", tenant_id=3, actor_user_id=8)
        self.assertEqual(out, req)
        # Counter for this actor is absent/zero — a legit confirm cost zero failures.
        self.assertFalse(cache.get(_cashout_fail_cache_key(actor_user_id=8, tenant_id=3)))

    def test_success_resets_counter(self):
        """After some failures, a successful confirm clears the counter."""
        from django.core.cache import cache
        cache.clear()
        key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        cache.set(key, CASHOUT_CONFIRM_MAX_FAILURES - 1, 900)
        req = _pending_request()
        self._match(req)
        self.m["debit"].return_value = SimpleNamespace(id=99)
        confirm_cashout("123456", tenant_id=3, actor_user_id=8)
        self.assertIsNone(cache.get(key))

    def test_fail_key_prefers_user_then_tenant(self):
        """The lockout is keyed per confirming user, falling back to tenant."""
        self.assertEqual(_cashout_fail_cache_key(actor_user_id=8, tenant_id=3),
                         "cashout_confirm_fail:u8")
        self.assertEqual(_cashout_fail_cache_key(actor_user_id=None, tenant_id=3),
                         "cashout_confirm_fail:t3")


class CashoutEndpointThrottleTests(SimpleTestCase):
    """Both owner cash-out endpoints must declare the cash-out throttle."""

    def test_lookup_view_has_throttle(self):
        from menu.views import OwnerDriverCashoutLookupView
        from accounts.throttles import DriverCashoutConfirmThrottle
        self.assertIn(DriverCashoutConfirmThrottle, OwnerDriverCashoutLookupView.throttle_classes)

    def test_confirm_view_has_throttle(self):
        from menu.views import OwnerDriverCashoutConfirmView
        from accounts.throttles import DriverCashoutConfirmThrottle
        self.assertIn(DriverCashoutConfirmThrottle, OwnerDriverCashoutConfirmView.throttle_classes)

    def test_throttle_scope_registered(self):
        from accounts.throttles import DriverCashoutConfirmThrottle
        from config.rest_framework import REST_FRAMEWORK
        self.assertEqual(DriverCashoutConfirmThrottle.scope, "driver_cashout_confirm")
        self.assertIn("driver_cashout_confirm", REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])

    def test_throttle_keyed_per_user(self):
        from accounts.throttles import DriverCashoutConfirmThrottle
        t = DriverCashoutConfirmThrottle()
        req = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, pk=42, id=42), META={})
        key = t.get_cache_key(req, None)
        self.assertIn("cashout:42", key)


class CashoutLookupLockoutTests(SimpleTestCase):
    """OPS-5e: the GET lookup endpoint is a code-validity oracle, so it must share the
    SAME per-actor brute-force lockout as confirm_cashout — a miss increments the
    counter and once tripped the endpoint refuses before querying."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerDriverCashoutLookupView
        self.view = OwnerDriverCashoutLookupView.as_view()

    def _get(self, code="000000", actor_id=8, tenant_id=3):
        # Superuser actor cleanly satisfies _can_edit_tenant_order without role mocking.
        user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_anonymous=False,
            is_superuser=True, is_platform_admin=False, id=actor_id, pk=actor_id,
        )
        req = self.factory.get("/api/owner/driver-cashout/", {"code": code})
        force_authenticate(req, user=user)
        req.tenant = SimpleNamespace(id=tenant_id)
        # Disable throttling so we isolate the lockout behaviour from the 10/min cap.
        with patch.object(self.view.cls, "throttle_classes", []):
            return self.view(req)

    def test_miss_increments_shared_counter_and_then_locks(self):
        from django.core.cache import cache
        cache.clear()
        key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        with patch("accounts.models.DriverCashoutRequest") as dcr:
            (dcr.objects.filter.return_value.order_by.return_value.first.return_value) = None
            # N misses → 404 each, counter climbs.
            for _ in range(CASHOUT_CONFIRM_MAX_FAILURES):
                resp = self._get(code="111111")
                self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(cache.get(key), CASHOUT_CONFIRM_MAX_FAILURES)
            # Next lookup is locked out (429) before the DB is consulted.
            dcr.objects.filter.reset_mock()
            resp = self._get(code="111111")
            self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertEqual(resp.data["code"], "locked")
            dcr.objects.filter.assert_not_called()

    def test_locked_actor_blocks_lookup_of_valid_code(self):
        """Once the actor is locked, even a valid code is refused (no oracle)."""
        from django.core.cache import cache
        cache.clear()
        key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        cache.set(key, CASHOUT_CONFIRM_MAX_FAILURES, 900)
        with patch("accounts.models.DriverCashoutRequest") as dcr:
            (dcr.objects.filter.return_value.order_by.return_value.first.return_value) = \
                _pending_request()
            resp = self._get(code="123456")
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "locked")

    def test_hit_does_not_increment_counter(self):
        """A valid lookup returns 200 and does NOT add to the failure counter."""
        from django.core.cache import cache
        cache.clear()
        key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        with patch("accounts.models.Customer") as cust, \
                patch("accounts.models.DriverCashoutRequest") as dcr:
            (dcr.objects.filter.return_value.order_by.return_value.first.return_value) = \
                _pending_request()
            cust.objects.filter.return_value.only.return_value.first.return_value = \
                SimpleNamespace(name="Sam", phone="+212600000000")
            resp = self._get(code="123456")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["request_id"], 7)
        self.assertFalse(cache.get(key))


# ═════════════════════════════════════════════════════════════════════════════
# B. Wallet idempotency replay hardening
# ═════════════════════════════════════════════════════════════════════════════

class WalletReplayAssertionTests(SimpleTestCase):
    """An existing idempotent tx that belongs to a different customer/tenant is an
    attack, not a retry — the service must refuse it. Same-owner retries still pass.

    The wallet helpers are wrapped in @transaction.atomic; neutralise the atomic
    context so these unit tests never touch a DB (the replay assertion / early return
    happens inside the atomic block but before any query)."""

    def setUp(self):
        self._atomic = patch("django.db.transaction.Atomic.__enter__", return_value=None)
        self._atomic_exit = patch("django.db.transaction.Atomic.__exit__", return_value=False)
        self._atomic.start()
        self._atomic_exit.start()

    def tearDown(self):
        self._atomic.stop()
        self._atomic_exit.stop()

    def test_credit_rejects_different_customer_key_collision(self):
        from accounts import wallet_service
        from accounts.wallet_service import credit_wallet, WalletError
        other = SimpleNamespace(id=1, customer_id=999)
        with patch.object(wallet_service, "_find_idempotent", return_value=other):
            with self.assertRaises(WalletError):
                credit_wallet(5, "10", idempotency_key="attacker-key")

    def test_credit_allows_same_customer_retry(self):
        from accounts import wallet_service
        from accounts.wallet_service import credit_wallet
        existing = SimpleNamespace(id=1, customer_id=5)
        with patch.object(wallet_service, "_find_idempotent", return_value=existing):
            out = credit_wallet(5, "10", idempotency_key="legit-key")
        self.assertIs(out, existing)

    def test_debit_rejects_different_customer_key_collision(self):
        from accounts import wallet_service
        from accounts.wallet_service import debit_wallet, WalletError
        other = SimpleNamespace(id=2, customer_id=888, amount=Decimal("10.00"))
        with patch.object(wallet_service, "_find_idempotent", return_value=other):
            with self.assertRaises(WalletError):
                debit_wallet(5, "10", idempotency_key="attacker-key")

    def test_debit_allows_same_customer_partial_retry(self):
        """A partial-debit retry stores a DIFFERENT amount than requested — must still
        be accepted (we assert customer only, never amount)."""
        from accounts import wallet_service
        from accounts.wallet_service import debit_wallet
        # requested 10 but the original partial charge stored only 3 — legit retry.
        existing = SimpleNamespace(id=3, customer_id=5, amount=Decimal("3.00"))
        with patch.object(wallet_service, "_find_idempotent", return_value=existing):
            out = debit_wallet(5, "10", idempotency_key="legit-partial", allow_partial=True)
        self.assertIs(out, existing)

    def test_float_rejects_different_tenant_key_collision(self):
        from accounts import wallet_service
        from accounts.wallet_service import credit_tenant_float, WalletError
        other = SimpleNamespace(id=4, tenant_id=777)
        with patch.object(wallet_service, "_find_idempotent_float", return_value=other):
            with self.assertRaises(WalletError):
                credit_tenant_float(3, "10", idempotency_key="attacker-key")

    def test_float_allows_same_tenant_retry(self):
        from accounts import wallet_service
        from accounts.wallet_service import credit_tenant_float
        existing = SimpleNamespace(id=4, tenant_id=3)
        with patch.object(wallet_service, "_find_idempotent_float", return_value=existing):
            out = credit_tenant_float(3, "10", idempotency_key="legit-key")
        self.assertIs(out, existing)


class OwnerWalletChargeKeyNamespaceTests(SimpleTestCase):
    """The externally-supplied idempotency key must be namespaced with the tenant
    schema so one tenant's key can never collide with another's."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = __import__("menu.views", fromlist=["OwnerWalletChargeView"]).OwnerWalletChargeView.as_view()

    def _owner(self, tenant_id=1):
        from accounts.models import User
        u = MagicMock()
        u.is_authenticated = True
        u.is_superuser = False
        u.is_platform_admin = False
        u.tenant_id = tenant_id
        u.role = User.Roles.TENANT_OWNER
        u.Roles = User.Roles
        u.effective_perm_manage_orders.return_value = True
        return u

    def test_external_key_is_tenant_namespaced(self):
        from django.core import signing
        from accounts.views import _WALLET_PAY_SALT
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        req = self.factory.post(
            "/api/owner/wallet/charge/",
            {"token": token, "amount": "10.00", "idempotency_key": "client-supplied-123"},
            format="json",
        )
        req.user = self._owner()
        req.tenant = SimpleNamespace(id=1, schema_name="acme", name="Acme")
        with patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit:
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        passed_key = mock_debit.call_args.kwargs["idempotency_key"]
        self.assertEqual(passed_key, "ownercharge:acme:client-supplied-123")
        # tenant schema is present so a different tenant with the same raw key differs.
        self.assertIn("acme", passed_key)
        self.assertNotEqual(passed_key, "client-supplied-123")


# ═════════════════════════════════════════════════════════════════════════════
# C. CustomerOrderRateView ownership gate + throttle
# ═════════════════════════════════════════════════════════════════════════════

class CustomerOrderRateOwnershipTests(SimpleTestCase):
    """Only the session customer who owns an order may rate it."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import CustomerOrderRateView
        self.view = CustomerOrderRateView.as_view()

    def _post(self, *, session_cid, order_customer_id):
        from menu.views import Order
        order = SimpleNamespace(
            order_number="ORD-1", customer_id=order_customer_id,
            status=Order.Status.COMPLETED,
        )
        req = self.factory.post("/api/orders/ORD-1/rate/", {"score": 5}, format="json")
        req.session = {"customer_id": session_cid} if session_cid is not None else {}
        req.tenant = None
        with patch.object(Order.objects, "get", return_value=order):
            return self.view(req, order_number="ORD-1")

    def test_non_owner_session_rejected(self):
        """A session customer that doesn't own the order is 403."""
        resp = self._post(session_cid=2, order_customer_id=999)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_order_owner")

    def test_no_session_customer_rejected(self):
        """An anonymous caller (no session customer) cannot rate."""
        resp = self._post(session_cid=None, order_customer_id=999)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_throttle_wired(self):
        from menu.views import CustomerOrderRateView
        from accounts.throttles import CustomerOrderRateThrottle
        from config.rest_framework import REST_FRAMEWORK
        self.assertIn(CustomerOrderRateThrottle, CustomerOrderRateView.throttle_classes)
        self.assertEqual(CustomerOrderRateThrottle.scope, "customer_order_rate")
        self.assertIn("customer_order_rate", REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])


# ═════════════════════════════════════════════════════════════════════════════
# D. TranslateView must not echo the upstream provider's raw error body
# ═════════════════════════════════════════════════════════════════════════════

class TranslateProviderBodyLeakTests(SimpleTestCase):
    """A provider HTTPError must return a generic body, logged server-side only."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from tenancy.api import TranslateView
        self.view = TranslateView.as_view()

    def _owner(self, tenant_id=1):
        from accounts.models import User
        u = MagicMock()
        u.is_authenticated = True
        u.is_superuser = False
        u.is_platform_admin = False
        u.tenant_id = tenant_id
        u.role = User.Roles.TENANT_OWNER
        u.Roles = User.Roles
        return u

    def test_provider_error_body_not_echoed(self):
        import urllib.error
        secret_body = '{"error":"INTERNAL provider key sk-leak quota detail"}'
        http_err = urllib.error.HTTPError(
            url="https://openrouter.ai", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        http_err.read = MagicMock(return_value=secret_body.encode("utf-8"))

        req = self.factory.post(
            "/api/translate/", {"text": "hello", "target_lang": "ar"}, format="json"
        )
        req.user = self._owner()
        req.tenant = SimpleNamespace(id=1, schema_name="acme")

        with (
            patch("django.conf.settings.OPENROUTER_API_KEY", "sk-test", create=True),  # create-true-ok: OPENROUTER_API_KEY is an OPTIONAL Django setting (env-fallback, undefined by default in the test env); create=True is the standard idiom for patching a settings attr that may not exist.
            patch("tenancy.api.TranslateView._call_openrouter", side_effect=http_err),
            patch("tenancy.api.logger") as mock_logger,
        ):
            resp = self.view(req)

        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.data["code"], "provider_error")
        # The raw upstream body must NOT be in the response …
        self.assertNotIn("body", resp.data)
        self.assertNotIn("sk-leak", str(resp.data))
        # … but it IS logged server-side for diagnostics.
        mock_logger.warning.assert_called_once()
