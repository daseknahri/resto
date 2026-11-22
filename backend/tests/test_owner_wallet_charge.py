"""Tests for OwnerWalletChargeView (wallet charge by pay-code). No DB."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.db import IntegrityError
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import _WALLET_PAY_SALT
from menu.models import OrderPayment
from menu.views import OwnerWalletChargeView, _sync_charged_request_bills


class _RecordingAtomic:
    """Stand-in for transaction.atomic() that records whether the block ran and
    whether it exited with an exception (i.e. rolled back)."""
    def __init__(self):
        self.entered = 0
        self.exit_exceptions = []
    def __call__(self, *args, **kwargs):
        return self
    def __enter__(self):
        self.entered += 1
        return self
    def __exit__(self, exc_type, exc, tb):
        self.exit_exceptions.append(exc_type)
        return False


def _owner(tenant_id=1):
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.tenant_id = tenant_id
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    return u


def _outsider():
    u = _owner(tenant_id=99)  # different tenant than the request tenant (id=1)
    return u


class OwnerWalletChargeViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        # The instant-charge velocity cap is per (customer, pay-token) in the shared
        # cache, and every test mints signing.dumps({"cid": 5}) — same-second tokens
        # are identical, so all instant charges share ONE bucket (max 5). Clear it
        # per test or later tests 429 once the bucket fills (Wave B: the new instant
        # fingerprint test pushed the shared bucket over 5).
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = OwnerWalletChargeView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/wallet/charge/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or SimpleNamespace(id=1)
        return self.view(req)

    def test_non_owner_403(self):
        self.assertEqual(self._post({"token": "x", "amount": "10"}, user=_outsider()).status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_token_400(self):
        resp = self._post({"amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_token")

    def test_bad_token_400(self):
        resp = self._post({"token": "not-a-valid-token", "amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid")

    def test_valid_token_but_bad_amount_400(self):
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        resp = self._post({"token": token, "amount": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_above_threshold_creates_pending_request_without_charging(self):
        """Amount over the approval threshold (default 50) → 202 pending, no debit."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        cr = MagicMock(id=7)
        cr.expires_at.isoformat.return_value = "2026-06-03T15:00:00+00:00"
        with patch("accounts.models.WalletChargeRequest.objects") as mock_cr, \
             patch("accounts.wallet_service.debit_wallet") as mock_debit:
            mock_cr.get_or_create.return_value = (cr, True)
            resp = self._post({"token": token, "amount": "100.00"})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["request_id"], 7)
        mock_debit.assert_not_called()

    def test_above_threshold_retry_without_key_reuses_fingerprint_key(self):
        """Gap-hunt 2026-11-22 (W P1-3): two identical above-threshold POSTs with no
        client idempotency_key must map to the SAME server fingerprint key, so the
        second is a replay of the first charge request instead of a second mint.
        """
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        cr = MagicMock(id=7)
        cr.expires_at.isoformat.return_value = "2026-06-03T15:00:00+00:00"
        user = _owner()
        user.id = 3  # fixed actor id so the fingerprint is deterministic
        with patch("accounts.models.WalletChargeRequest.objects") as mock_cr, \
             patch("accounts.wallet_service.debit_wallet") as mock_debit:
            mock_cr.get_or_create.return_value = (cr, True)
            resp1 = self._post({"token": token, "amount": "100.00"}, user=user)
            resp2 = self._post({"token": token, "amount": "100.00"}, user=user)
        self.assertEqual(resp1.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp2.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp1.data["request_id"], resp2.data["request_id"])
        self.assertEqual(mock_cr.get_or_create.call_count, 2)
        keys = [c.kwargs["idempotency_key"] for c in mock_cr.get_or_create.call_args_list]
        self.assertEqual(keys[0], keys[1])  # same fingerprint, not a fresh random key
        self.assertIn(":fp:", keys[0])
        self.assertTrue(keys[0].startswith("ownercharge:"))
        mock_debit.assert_not_called()

    def test_at_or_below_threshold_charges_instantly(self):
        """Amount within the threshold → instant debit, 200 charged."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        with patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit:
            resp = self._post({"token": token, "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "charged")
        mock_debit.assert_called_once()

    def test_order_tied_charge_writes_orderpayment_row(self):
        """S1: when order_number is supplied, the charge must be tied to that
        order as a real OrderPayment (method=wallet) row — not just an update to
        wallet_amount_paid — so OwnerOrderMarkPaidView's reconciliation guard has
        a real ledger figure to check the settle against."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.id = 555
        tx.balance_after = "40.00"
        charged_order = MagicMock(id=77)
        with patch("accounts.wallet_service.debit_wallet", return_value=tx), \
             patch("menu.views.Order.objects") as mock_order_objects, \
             patch("menu.views.OrderPayment.objects") as mock_op_objects, \
             patch("menu.views._settle_order_if_wallet_covers"):
            mock_order_objects.filter.return_value.update.return_value = 1
            mock_order_objects.filter.return_value.only.return_value.first.return_value = charged_order
            resp = self._post({"token": token, "amount": "10.00", "order_number": "ORD-9"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_op_objects.create.assert_called_once()
        _, kwargs = mock_op_objects.create.call_args
        self.assertEqual(kwargs["order"], charged_order)
        self.assertEqual(kwargs["amount"], Decimal("10.00"))
        self.assertEqual(kwargs["method"], OrderPayment.Method.WALLET)
        # The ledger row is anchored on the stable wallet-tx id so a debit replay can't
        # write a duplicate (see the replay test below).
        self.assertEqual(kwargs["idempotency_key"], "ownercharge:555")
        # Fresh charge → the bill counter is incremented.
        mock_order_objects.filter.return_value.update.assert_called_once()

    def test_order_tied_charge_replay_does_not_double_apply(self):
        """Idempotency: a retry (dropped response / double-tap) re-runs the view with the same
        pay-code; debit_wallet returns the SAME tx (no second debit), so the OrderPayment insert
        hits the unique idempotency_key and raises IntegrityError. The bill counter increment
        MUST be skipped on that replay — otherwise wallet_amount_paid double-counts and
        _order_collected() over-reports, silently under-collecting real revenue."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.id = 555
        tx.balance_after = "40.00"
        charged_order = MagicMock(id=77)
        with patch("accounts.wallet_service.debit_wallet", return_value=tx), \
             patch("menu.views.Order.objects") as mock_order_objects, \
             patch("menu.views.OrderPayment.objects") as mock_op_objects, \
             patch("menu.views._settle_order_if_wallet_covers") as mock_settle:
            mock_order_objects.filter.return_value.only.return_value.first.return_value = charged_order
            mock_op_objects.create.side_effect = IntegrityError("duplicate key")
            resp = self._post({"token": token, "amount": "10.00", "order_number": "ORD-9"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_op_objects.create.assert_called_once()
        # Replay: the wallet_amount_paid increment is NOT applied a second time.
        mock_order_objects.filter.return_value.update.assert_not_called()
        # The settle check still runs (it is idempotent).
        mock_settle.assert_called_once()

    def test_instant_retry_without_key_reuses_fingerprint_key(self):
        """Gap-hunt Wave B (W P2-9): two identical instant (sub-threshold) POSTs with no
        client idempotency_key must map to the SAME server fingerprint key, so the
        second is a debit replay (no second debit) instead of a fresh charge. A fresh
        scan (new pay-token) with the same amount is a NEW charge — the token is part
        of the fingerprint because the token IS the consent on the instant path."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        user = _owner()
        user.id = 3  # fixed actor id so the fingerprint is deterministic
        with patch("accounts.wallet_service.debit_wallet", return_value=tx) as mock_debit:
            resp1 = self._post({"token": token, "amount": "10.00"}, user=user)
            resp2 = self._post({"token": token, "amount": "10.00"}, user=user)
            # A new scan (new token, same amount, same customer) is a new charge.
            token2 = signing.dumps({"cid": 5, "n": 1}, salt=_WALLET_PAY_SALT)
            resp3 = self._post({"token": token2, "amount": "10.00"}, user=user)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_debit.call_count, 3)
        keys = [c.kwargs["idempotency_key"] for c in mock_debit.call_args_list]
        self.assertEqual(keys[0], keys[1])  # same scan → same fingerprint key
        self.assertIn(":fp:", keys[0])
        self.assertTrue(keys[0].startswith("ownercharge:"))
        self.assertNotEqual(keys[0], keys[2])  # new scan → new key → new charge

    def test_no_order_number_does_not_write_orderpayment(self):
        """The general (non-settle) wallet charge use — no order_number supplied —
        must be untouched: no OrderPayment row, only the wallet debit."""
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        tx = MagicMock()
        tx.balance_after = "40.00"
        with patch("accounts.wallet_service.debit_wallet", return_value=tx), \
             patch("menu.views.OrderPayment.objects") as mock_op_objects:
            resp = self._post({"token": token, "amount": "10.00"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_op_objects.create.assert_not_called()


# ── _sync_charged_request_bills (W P1-4) ──────────────────────────────────────

class SyncChargedRequestBillsTests(SimpleTestCase):
    """The claim (bill_synced flip) and the bill application must commit together in
    ONE atomic block — a crash between them must not lose the amount."""

    def _run(self, *, claim_rows=1, bill_side_effect=None):
        rec = _RecordingAtomic()
        with patch("accounts.models.WalletChargeRequest") as WCR, \
             patch("menu.views.Order") as O, \
             patch("menu.views.OrderPayment"), \
             patch("menu.views._settle_order_if_wallet_covers") as settle, \
             patch("django.db.transaction.atomic", rec):
            WCR.Status.CHARGED = "charged"
            WCR.objects.filter.return_value.values_list.return_value = [
                (1, "ORD-1", Decimal("25.00"))
            ]
            WCR.objects.filter.return_value.update.return_value = claim_rows
            if bill_side_effect is not None:
                O.objects.filter.return_value.update.side_effect = bill_side_effect
            result = _sync_charged_request_bills(1, ["ORD-1"])
        return result, rec, WCR, O, settle

    def test_happy_path_applies_once_inside_one_atomic_block(self):
        result, rec, WCR, O, settle = self._run()
        self.assertEqual(result, {"ORD-1": Decimal("25.00")})
        self.assertEqual(rec.entered, 1)  # claim + apply shared ONE atomic block
        self.assertEqual(rec.exit_exceptions, [None])  # clean commit
        WCR.objects.filter.return_value.update.assert_called_once()
        O.objects.filter.return_value.update.assert_called_once()
        settle.assert_called_once_with("ORD-1")

    def test_failed_bill_update_rolls_the_claim_back(self):
        """W P1-4: if the bill update fails, the atomic block exits WITH the
        exception — the claim rolls back, the request stays unsynced, and nothing
        is counted as applied. Before the fix there was no atomic block at all, so
        the claim would have committed and the amount been lost."""
        result, rec, WCR, O, settle = self._run(bill_side_effect=Exception("boom"))
        self.assertEqual(result, {})
        self.assertEqual(rec.entered, 1)
        self.assertEqual(len(rec.exit_exceptions), 1)
        self.assertIsNotNone(rec.exit_exceptions[0])  # exited with the exception
        settle.assert_not_called()

    def test_lost_claim_is_not_applied(self):
        """A concurrent caller already flipped bill_synced (claim returns 0): the
        bill is not applied a second time."""
        result, rec, WCR, O, settle = self._run(claim_rows=0)
        self.assertEqual(result, {})
        O.objects.filter.return_value.update.assert_not_called()
        settle.assert_not_called()
