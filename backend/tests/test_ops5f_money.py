"""OPS-5f Money-path hardening — Contract Tests

Scouts OPS-5e (test_ops5e_money.py) and closes the two gaps it left:

  A. OwnerWalletChargeView (menu/views.py) — owner-charge cap + throttle:
       1. throttle_classes wires OwnerWalletChargeThrottle (scope owner_wallet_charge).
       2. The instant (sub-threshold, token-only-consent) path caps the COUNT of
          charges per (customer, pay-token): the (N+1)th rapid charge is refused (429)
          and never debits.
       3. The same path caps the CUMULATIVE amount per (customer, pay-token): a charge
          that would push the running total over the ceiling is refused before any debit.
       4. A single legitimate sub-threshold charge still goes through (no regression).

  B. transfer_between_customers (accounts/wallet_service.py) — P2P replay IDENTITY
     assertion (OPS-5e added it to the other ledger helpers but missed this one):
       5. A replay whose existing out-tx belongs to a DIFFERENT sender is refused.
       6. A same-sender retry still returns the existing (out_tx, in_tx) pair.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory


# ═════════════════════════════════════════════════════════════════════════════
# A. OwnerWalletChargeView — instant-charge velocity / amount cap + throttle
# ═════════════════════════════════════════════════════════════════════════════

class OwnerWalletChargeThrottleWiringTests(SimpleTestCase):
    """The view must declare the dedicated owner-charge throttle (scope owner_wallet_charge)."""

    def test_view_has_throttle(self):
        from menu.views import OwnerWalletChargeView
        from accounts.throttles import OwnerWalletChargeThrottle
        self.assertIn(OwnerWalletChargeThrottle, OwnerWalletChargeView.throttle_classes)

    def test_throttle_scope_is_owner_wallet_charge(self):
        from accounts.throttles import OwnerWalletChargeThrottle
        self.assertEqual(OwnerWalletChargeThrottle.scope, "owner_wallet_charge")


class OwnerWalletChargeInstantCapTests(SimpleTestCase):
    """The instant sub-threshold path (consent = pay-token only) must be capped per
    (customer, pay-token) so one scan can't be turned into an unbounded debit stream."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerWalletChargeView
        self.view_cls = OwnerWalletChargeView
        self.view = OwnerWalletChargeView.as_view()

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

    def _token(self, cid=5):
        # Mirror CustomerWalletPayTokenView exactly. Django's signing embeds a 1-second
        # timestamp, so two mints for the same cid in the same second are byte-identical
        # (a single scan). A refreshed QR (≥1 s later) yields a distinct token — see
        # _fresh_token below for a deterministic "later scan".
        from django.core import signing
        from accounts.views import _WALLET_PAY_SALT
        return signing.dumps({"cid": cid}, salt=_WALLET_PAY_SALT)

    def _fresh_token(self, cid=5, at=2_000_000_000):
        """A pay-token minted at a fixed (different) wall-clock second — models the
        customer refreshing their QR, which produces a distinct token string."""
        from django.core import signing
        from accounts.views import _WALLET_PAY_SALT
        with patch("time.time", return_value=at):
            return signing.dumps({"cid": cid}, salt=_WALLET_PAY_SALT)

    def _charge(self, token, amount, *, balance_after="90.00"):
        """Fire one instant charge. Throttling is disabled so we isolate the cap; the
        above-threshold approval branch is avoided by keeping amount under the (mocked)
        threshold. debit_wallet is stubbed so no DB is touched on the success path."""
        tx = SimpleNamespace(balance_after=balance_after)
        req = self.factory.post(
            "/api/owner/wallet/charge/",
            {"token": token, "amount": amount},
            format="json",
        )
        req.user = self._owner()
        req.tenant = SimpleNamespace(id=1, schema_name="acme", name="Acme")
        # High threshold so every amount we use stays on the INSTANT path; PlatformConfig
        # lookup is neutralised to the env fallback path inside the view.
        with patch.object(self.view_cls, "throttle_classes", []), \
                patch("accounts.models.PlatformConfig.get_solo", side_effect=Exception("no DB")), \
                patch("django.conf.settings.WALLET_CHARGE_APPROVAL_THRESHOLD", "10000", create=True), \
                patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit:
            resp = self.view(req)
        return resp, mock_debit

    def test_count_cap_blocks_the_nth_rapid_charge(self):
        """After INSTANT_CHARGE_MAX_COUNT successful instant charges on one pay-token,
        the next one is refused (429) and never reaches debit_wallet."""
        from django.core.cache import cache
        cache.clear()
        token = self._token()
        n = self.view_cls.INSTANT_CHARGE_MAX_COUNT
        # Small amounts so the COUNT ceiling trips before the cumulative-amount ceiling.
        per = (self.view_cls.INSTANT_CHARGE_MAX_TOTAL / (n + 2)).quantize(Decimal("0.01"))
        for i in range(n):
            resp, mock_debit = self._charge(token, str(per))
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"charge {i} should pass")
            mock_debit.assert_called_once()
        # The (N+1)th charge is over the count cap → refused before any debit.
        resp, mock_debit = self._charge(token, str(per))
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "instant_cap")
        mock_debit.assert_not_called()
        cache.clear()

    def test_amount_cap_blocks_charge_over_cumulative_ceiling(self):
        """A charge that would push the running total over INSTANT_CHARGE_MAX_TOTAL is
        refused before any money moves, even when under the count cap."""
        from django.core.cache import cache
        cache.clear()
        token = self._token()
        # First charge: just under the total ceiling. Second: small but tips it over.
        near = (self.view_cls.INSTANT_CHARGE_MAX_TOTAL - Decimal("1.00")).quantize(Decimal("0.01"))
        resp, mock_debit = self._charge(token, str(near))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_debit.assert_called_once()
        resp, mock_debit = self._charge(token, "5.00")  # near + 5 > ceiling
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "instant_cap")
        mock_debit.assert_not_called()
        cache.clear()

    def test_single_legit_charge_still_works(self):
        """The legitimate single-charge flow is unaffected by the cap."""
        from django.core.cache import cache
        cache.clear()
        resp, mock_debit = self._charge(self._token(), "5.00", balance_after="95.00")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "charged")
        self.assertEqual(resp.data["amount"], "5.00")
        mock_debit.assert_called_once()
        cache.clear()

    def test_separate_paytokens_have_independent_buckets(self):
        """The cap is per (customer, pay-token): a fresh QR scan resets the ceiling, so
        the cap can't permanently lock out a present, willing customer."""
        from django.core.cache import cache
        cache.clear()
        n = self.view_cls.INSTANT_CHARGE_MAX_COUNT
        per = (self.view_cls.INSTANT_CHARGE_MAX_TOTAL / (n + 2)).quantize(Decimal("0.01"))
        tok_a = self._token()
        for _ in range(n):
            self._charge(tok_a, str(per))
        # tok_a is now exhausted …
        resp, _ = self._charge(tok_a, str(per))
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # … but a brand-new token (refreshed QR, distinct timestamp) charges fine.
        tok_b = self._fresh_token()
        self.assertNotEqual(tok_a, tok_b)  # a real refresh is a different token string
        resp, mock_debit = self._charge(tok_b, str(per))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_debit.assert_called_once()
        cache.clear()


# ═════════════════════════════════════════════════════════════════════════════
# B. transfer_between_customers — P2P idempotency-replay IDENTITY assertion
# ═════════════════════════════════════════════════════════════════════════════

class P2PTransferReplayAssertionTests(SimpleTestCase):
    """OPS-5e hardened credit/debit/float/transfer_to_customer against caller-supplied
    idempotency-key collisions but missed this P2P helper. A replay whose existing
    out-tx belongs to a DIFFERENT sender is an attack, not a retry — refuse it. A
    same-sender retry still replays the original (out_tx, in_tx).

    The helper is wrapped in @transaction.atomic; neutralise the atomic context so
    these unit tests never touch a DB (the assertion / early return happens inside the
    atomic block but before any query)."""

    def setUp(self):
        self._atomic = patch("django.db.transaction.Atomic.__enter__", return_value=None)
        self._atomic_exit = patch("django.db.transaction.Atomic.__exit__", return_value=False)
        self._atomic.start()
        self._atomic_exit.start()

    def tearDown(self):
        self._atomic.stop()
        self._atomic_exit.stop()

    def test_replay_rejects_different_sender_key_collision(self):
        from accounts import wallet_service
        from accounts.wallet_service import transfer_between_customers, WalletError
        # Existing out-tx belongs to customer 999, but the caller claims sender 5.
        other = SimpleNamespace(id=1, customer_id=999, amount=Decimal("20.00"))
        with patch.object(wallet_service, "_find_idempotent", return_value=other):
            with self.assertRaises(WalletError):
                transfer_between_customers(5, 8, "20", idempotency_key="attacker-key")

    def test_replay_allows_same_sender_retry(self):
        from accounts import wallet_service
        from accounts.wallet_service import transfer_between_customers
        # Original out-tx for sender 5; the in-tx mirror is looked up by "<key>:in".
        out = SimpleNamespace(id=1, customer_id=5, amount=Decimal("20.00"))
        in_tx = SimpleNamespace(id=2, customer_id=8, amount=Decimal("20.00"))
        wt = MagicMock()
        wt.objects.filter.return_value.first.return_value = in_tx
        with patch.object(wallet_service, "_find_idempotent", return_value=out), \
                patch.object(wallet_service, "WalletTransaction", wt):
            ret_out, ret_in = transfer_between_customers(5, 8, "20", idempotency_key="legit-key")
        self.assertIs(ret_out, out)
        self.assertIs(ret_in, in_tx)

    def test_replay_asserts_identity_only_not_amount(self):
        """A same-sender replay whose stored amount differs from the requested one is
        still accepted — the assertion is IDENTITY only, never amount."""
        from accounts import wallet_service
        from accounts.wallet_service import transfer_between_customers
        # requested 20, but the stored out-tx is 7 (e.g. a different earlier call shape) —
        # same sender, so the replay is honoured without an amount check.
        out = SimpleNamespace(id=3, customer_id=5, amount=Decimal("7.00"))
        wt = MagicMock()
        wt.objects.filter.return_value.first.return_value = None
        with patch.object(wallet_service, "_find_idempotent", return_value=out), \
                patch.object(wallet_service, "WalletTransaction", wt):
            ret_out, _ = transfer_between_customers(5, 8, "20", idempotency_key="legit-key")
        self.assertIs(ret_out, out)
