"""OPS-5g — voucher-redemption hardening + OG cache-key fix — Contract Tests

Covers three surgical security fixes:

  A. CustomerWalletRedeemVoucherView (accounts/views.py) — a redeemed voucher code
     maps straight to wallet credit, so it's a brute-force-to-money target:
       1. The view declares throttle_classes = [VoucherRedeemThrottle] (scope
          "voucher_redeem").
       2. A per-actor INVALID-code lockout (keyed on the session customer id) trips
          after N consecutive invalid codes → 429, before any voucher lookup.
       3. A legitimate redeem never increments the counter and clears it on success.

  B. WalletVoucher.generate_code (accounts/models.py) — bearer money-token codes must
     come from a CSPRNG (secrets), not random.choices (Mersenne Twister):
       4. The generated code has the right length and uses the expected alphabet.
       5. The source uses `secrets` and no longer references `random.choices`.

  C. OGView cache key (accounts/og_views.py) — the key must NOT contain the spoofable
     inbound Host header; it's keyed on the RESOLVED tenant id + a length-bounded path:
       6. With a resolved tenant the key is namespaced by the tenant id, not the Host.
       7. The path component is sanitised + length-bounded in the key.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

import inspect
import string
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.test import RequestFactory
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory


# ═════════════════════════════════════════════════════════════════════════════
# A. CustomerWalletRedeemVoucherView — throttle + invalid-code lockout
# ═════════════════════════════════════════════════════════════════════════════

def _make_customer(customer_id=1, wallet_balance=Decimal("20.00")):
    c = MagicMock()
    c.id = customer_id
    c.wallet_balance = wallet_balance
    c.phone_verified = True
    return c


def _make_voucher(code="GIFT1234AB", amount=Decimal("15.00"), is_used=False,
                  expires_at=None, note="Gift", vid=7):
    v = MagicMock()
    v.id = vid
    v.code = code
    v.amount = amount
    v.is_used = is_used
    v.expires_at = expires_at
    v.note = note
    return v


class VoucherRedeemThrottleWiringTests(SimpleTestCase):
    """The redeem view must declare the dedicated voucher-redeem throttle."""

    def test_view_has_throttle(self):
        from accounts.views import CustomerWalletRedeemVoucherView, VoucherRedeemThrottle
        self.assertIn(VoucherRedeemThrottle, CustomerWalletRedeemVoucherView.throttle_classes)

    def test_throttle_scope_is_voucher_redeem(self):
        from accounts.views import VoucherRedeemThrottle
        self.assertEqual(VoucherRedeemThrottle.scope, "voucher_redeem")


class VoucherRedeemInvalidCodeLockoutTests(SimpleTestCase):
    """A per-actor lockout must trip after N consecutive INVALID codes, before the
    voucher lookup even has a chance to credit a wallet."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from accounts.views import CustomerWalletRedeemVoucherView
        self.view_cls = CustomerWalletRedeemVoucherView
        self.view = CustomerWalletRedeemVoucherView.as_view()

    def _post(self, code, customer):
        req = self.factory.post(
            "/api/customer/wallet/redeem-voucher/", {"code": code}, format="json"
        )
        req.user = MagicMock(is_authenticated=True)
        req.customer = customer
        # Session customer id is what the lockout key prefers.
        req.session = {"customer_id": customer.id}
        return req

    def _fire_invalid(self, customer):
        """Fire one redeem with a nonexistent code (throttle disabled to isolate the
        lockout). Returns the response."""
        from accounts.models import WalletVoucher
        req = self._post("NOSUCHCODE", customer)
        with patch.object(self.view_cls, "throttle_classes", []), \
                patch("django.db.transaction.atomic"), \
                patch("accounts.models.WalletVoucher.objects") as mock_objs:
            mock_objs.select_for_update.return_value.get.side_effect = WalletVoucher.DoesNotExist
            return self.view(req)

    def test_lockout_trips_after_n_invalid_codes(self):
        from django.core.cache import cache
        from accounts.views import VOUCHER_REDEEM_MAX_FAILURES
        cache.clear()
        customer = _make_customer(customer_id=77)
        n = VOUCHER_REDEEM_MAX_FAILURES
        # The first N invalid attempts each get a plain 400 (invalid code).
        for i in range(n):
            resp = self._fire_invalid(customer)
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, f"attempt {i}")
        # The (N+1)th is refused with 429 BEFORE the voucher lookup runs.
        resp = self._fire_invalid(customer)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "voucher_locked")
        cache.clear()

    def test_locked_actor_cannot_reach_voucher_lookup(self):
        """Once locked, a request returns 429 without touching the WalletVoucher table."""
        from django.core.cache import cache
        from accounts.views import VOUCHER_REDEEM_MAX_FAILURES
        cache.clear()
        customer = _make_customer(customer_id=88)
        for _ in range(VOUCHER_REDEEM_MAX_FAILURES):
            self._fire_invalid(customer)
        # Now locked — even a (hypothetically valid) code must not be looked up.
        req = self._post("GIFT1234AB", customer)
        with patch.object(self.view_cls, "throttle_classes", []), \
                patch("django.db.transaction.atomic"), \
                patch("accounts.models.WalletVoucher.objects") as mock_objs:
            resp = self.view(req)
            mock_objs.select_for_update.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        cache.clear()

    def test_single_legit_redeem_not_penalised_and_clears_counter(self):
        """A legit first-try redeem never increments the counter; a successful redeem
        clears any prior failures so an honest actor is never locked out."""
        from django.core.cache import cache
        from accounts.views import VOUCHER_REDEEM_MAX_FAILURES, _voucher_redeem_fail_cache_key
        cache.clear()
        customer = _make_customer(customer_id=99)
        # Seed a few prior failures (below the cap).
        for _ in range(VOUCHER_REDEEM_MAX_FAILURES - 1):
            self._fire_invalid(customer)

        voucher = _make_voucher(amount=Decimal("15.00"), is_used=False, expires_at=None)
        req = self._post("GIFT1234AB", customer)
        with patch.object(self.view_cls, "throttle_classes", []), \
                patch("django.db.transaction.atomic"), \
                patch("accounts.models.WalletVoucher.objects") as mock_objs, \
                patch("accounts.wallet_service.credit_wallet") as mock_credit:
            mock_objs.select_for_update.return_value.get.return_value = voucher
            mock_credit.return_value = SimpleNamespace(balance_after=Decimal("35.00"))
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The counter was cleared by the successful redeem.
        key = _voucher_redeem_fail_cache_key(req, customer)
        self.assertIn(cache.get(key), (None, 0))
        cache.clear()


# ═════════════════════════════════════════════════════════════════════════════
# B. WalletVoucher.generate_code — CSPRNG (secrets), not random.choices
# ═════════════════════════════════════════════════════════════════════════════

class VoucherGenerateCodeSecretsTests(SimpleTestCase):

    ALPHABET = set(string.ascii_uppercase + string.digits)

    def test_code_has_expected_length_and_alphabet(self):
        from accounts.models import WalletVoucher
        # The uniqueness check queries the DB; stub it so no DB is touched.
        with patch.object(WalletVoucher, "objects") as mock_objs:
            mock_objs.filter.return_value.exists.return_value = False
            code = WalletVoucher.generate_code()
        self.assertEqual(len(code), 10)
        self.assertTrue(set(code).issubset(self.ALPHABET),
                        f"code {code!r} contains chars outside the alphabet")

    def test_respects_custom_length(self):
        from accounts.models import WalletVoucher
        with patch.object(WalletVoucher, "objects") as mock_objs:
            mock_objs.filter.return_value.exists.return_value = False
            code = WalletVoucher.generate_code(length=16)
        self.assertEqual(len(code), 16)
        self.assertTrue(set(code).issubset(self.ALPHABET))

    def test_source_uses_secrets_not_mersenne_twister(self):
        from accounts.models import WalletVoucher
        src = inspect.getsource(WalletVoucher.generate_code)
        self.assertIn("secrets", src, "generate_code must use the secrets module")
        self.assertNotIn("random.choices", src,
                         "generate_code must not use random.choices (non-CSPRNG)")

    def test_uses_secrets_choice_at_runtime(self):
        """Patch secrets.choice and confirm the generator routes through it (proves the
        CSPRNG is the source of randomness, not random.choices)."""
        from accounts.models import WalletVoucher
        with patch.object(WalletVoucher, "objects") as mock_objs, \
                patch("secrets.choice", return_value="A") as mock_choice:
            mock_objs.filter.return_value.exists.return_value = False
            code = WalletVoucher.generate_code(length=10)
        self.assertEqual(code, "A" * 10)
        self.assertEqual(mock_choice.call_count, 10)


# ═════════════════════════════════════════════════════════════════════════════
# C. OGView cache key — tenant id (not spoofed Host) + bounded path
# ═════════════════════════════════════════════════════════════════════════════

class OGCacheKeyTests(SimpleTestCase):

    def _make_request(self, path_param="/", host="evil.example.com"):
        return RequestFactory().get("/api/og/", {"path": path_param}, HTTP_HOST=host)

    def test_key_uses_tenant_id_not_spoofed_host(self):
        """When a tenant resolves, the cache key is namespaced by the tenant id; the
        (spoofable) inbound Host must not appear in the key."""
        from accounts.og_views import OGView
        tenant = MagicMock()
        tenant.id = 4242
        tenant.name = "Tacos House"
        tenant.is_active = True
        domain_obj = MagicMock()
        domain_obj.tenant = tenant
        profile = MagicMock()
        profile.tagline = "Good tacos"
        profile.hero_url = "https://cdn.example.com/h.jpg"
        profile.logo_url = ""

        with patch("accounts.og_views.cache") as mock_cache, \
                patch("accounts.og_views.Domain") as MockDomain, \
                patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile

            req = self._make_request(path_param="/menu", host="spoofed.attacker.test")
            OGView.as_view()(req)

        # The key the body was stored under.
        set_key = mock_cache.set.call_args[0][0]
        get_key = mock_cache.get.call_args[0][0]
        self.assertEqual(set_key, get_key)  # look-up and store use the same key
        self.assertIn("t4242", set_key)
        self.assertNotIn("spoofed.attacker.test", set_key)
        self.assertTrue(set_key.startswith("ogpage:"))

    def test_no_tenant_uses_platform_namespace_not_host(self):
        from accounts.og_views import OGView
        with patch("accounts.og_views.cache") as mock_cache, \
                patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            req = self._make_request(path_param="/about", host="spoofed.attacker.test")
            OGView.as_view()(req)

        set_key = mock_cache.set.call_args[0][0]
        self.assertEqual(set_key, "ogpage:platform:/about")
        self.assertNotIn("spoofed.attacker.test", set_key)

    @override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="")
    def test_no_tenant_body_uses_brand_host_not_spoofed_host(self):
        """OPS-5g close-out: the no-tenant platform fallback must build og:image/canonical
        from the server-authoritative BRAND_DOMAIN, not the spoofable inbound Host —
        otherwise the shared 'ogpage:platform' cache row serves a poisoned host to everyone."""
        from accounts.og_views import OGView
        with patch("accounts.og_views.cache") as mock_cache, \
                patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            req = self._make_request(path_param="/about", host="spoofed.attacker.test")
            OGView.as_view()(req)

        body = mock_cache.set.call_args[0][1]
        self.assertNotIn("spoofed.attacker.test", body)
        self.assertIn("app.kepoli.com", body)

    def test_cache_key_path_is_length_bounded(self):
        """A very long ?path can't fan out unbounded distinct cache rows — the path
        component in the KEY is truncated."""
        from accounts.og_views import OGView, _OG_CACHE_PATH_MAX
        long_path = "/" + ("a" * 5000)
        with patch("accounts.og_views.cache") as mock_cache, \
                patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            req = self._make_request(path_param=long_path, host="kepoli.app")
            OGView.as_view()(req)

        set_key = mock_cache.set.call_args[0][0]
        # Key = "ogpage:platform:" + bounded path. The path part is capped.
        prefix = "ogpage:platform:"
        self.assertTrue(set_key.startswith(prefix))
        path_part = set_key[len(prefix):]
        self.assertLessEqual(len(path_part), _OG_CACHE_PATH_MAX)

    def test_cache_key_helper_sanitises_and_bounds(self):
        """Direct unit test of the key helper: tenant id namespace + sanitised path."""
        from accounts.og_views import _og_cache_key, _OG_CACHE_PATH_MAX
        tenant = SimpleNamespace(id=7)
        key = _og_cache_key(tenant, "/order/x" + ("y" * 5000))
        self.assertTrue(key.startswith("ogpage:t7:"))
        path_part = key[len("ogpage:t7:"):]
        self.assertLessEqual(len(path_part), _OG_CACHE_PATH_MAX)
        # None tenant → platform namespace.
        self.assertTrue(_og_cache_key(None, "/x").startswith("ogpage:platform:"))
