"""Regression tests for the driver cash-out status-clobber class of bug.

Two lifecycle writes could blindly overwrite a concurrently-committed PAID row:

  Bug 1 — DriverCashoutCancelView (accounts/views.py): a driver's Cancel read the row
          as PENDING, then blindly saved CANCELLED. A restaurant's confirm committing
          PAID in the gap would be overwritten with CANCELLED (money moved, record wrong,
          dangling wallet_tx_id). Fix: a guarded compare-and-set
          filter(..., status=PENDING).update(status=CANCELLED) that no-ops if the row
          already left PENDING.

  Bug 2 — confirm_cashout (accounts/driver_service.py): a prior fix deferred an UNLOCKED
          blind save(status=EXPIRED) to after the atomic block, opening a clobber window
          where a concurrent confirm could commit PAID in the gap and be overwritten with
          EXPIRED. Fix: write EXPIRED via a guarded update INSIDE the row lock.

Neither bug double-spends (the wallet debit is idempotent on cashout:{id}); both corrupt
the record / break reconciliation.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status

from accounts.driver_service import (
    confirm_cashout,
    CashoutError,
    _cashout_fail_cache_key,
)


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ═════════════════════════════════════════════════════════════════════════════
# Bug 1 — DriverCashoutCancelView guarded compare-and-set
# ═════════════════════════════════════════════════════════════════════════════

class DriverCashoutCancelClobberTests(SimpleTestCase):
    """The Cancel endpoint must transition ONLY a still-PENDING row, and must never
    report a false success when the row already resolved (e.g. a racing PAID confirm)."""

    def setUp(self):
        from accounts.views import DriverCashoutCancelView
        self.view = DriverCashoutCancelView()
        # request.user.id is the only request attribute the handler reads.
        self.request = SimpleNamespace(user=SimpleNamespace(id=5))

    def _call(self, dcr):
        return self.view.post(self.request, request_id=7)

    def test_pending_cancel_succeeds_via_guarded_update(self):
        with patch("accounts.models.DriverCashoutRequest") as DCR:
            DCR.objects.filter.return_value.update.return_value = 1  # one PENDING row hit
            resp = self._call(DCR)

        # Success reports CANCELLED (unchanged response shape).
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIs(resp.data["status"], DCR.Status.CANCELLED)
        # The write is a GUARDED compare-and-set: filter carries the status=PENDING guard,
        # update sets CANCELLED. No blind read-then-save.
        DCR.objects.filter.assert_called_once_with(
            pk=7, driver_id=5, status=DCR.Status.PENDING
        )
        upd = DCR.objects.filter.return_value.update
        upd.assert_called_once()
        self.assertIs(upd.call_args.kwargs["status"], DCR.Status.CANCELLED)
        # Guard succeeded, so we never fell through to the status-reflecting lookup.
        DCR.objects.filter.return_value.first.assert_not_called()

    def test_already_paid_cancel_does_not_report_success_or_overwrite(self):
        """A Cancel that races a confirm to PAID: the guarded update matches 0 rows, so the
        view must NOT report a cancel and must NOT clobber the PAID row."""
        paid = SimpleNamespace(status="paid")
        with patch("accounts.models.DriverCashoutRequest") as DCR:
            DCR.objects.filter.return_value.update.return_value = 0     # nothing PENDING
            DCR.objects.filter.return_value.first.return_value = paid   # already resolved
            resp = self._call(DCR)

        # No false success: it does NOT claim the row was cancelled.
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["status"], "paid")
        self.assertIsNot(resp.data["status"], DCR.Status.CANCELLED)
        # The update was GUARDED on status=PENDING — in a real DB that WHERE matches no
        # row, so the committed PAID row is left untouched (no clobber). The FIRST filter
        # call is the guarded update; the second is the status-reflecting fallback lookup.
        upd = DCR.objects.filter.return_value.update
        upd.assert_called_once()
        self.assertIs(DCR.objects.filter.call_args_list[0].kwargs["status"], DCR.Status.PENDING)
        # The paid row itself was never mutated.
        self.assertEqual(paid.status, "paid")

    def test_missing_request_returns_404(self):
        with patch("accounts.models.DriverCashoutRequest") as DCR:
            DCR.objects.filter.return_value.update.return_value = 0
            DCR.objects.filter.return_value.first.return_value = None
            resp = self._call(DCR)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["detail"], "Not found.")


# ═════════════════════════════════════════════════════════════════════════════
# Bug 2 — confirm_cashout EXPIRED write is a guarded update INSIDE the lock
# ═════════════════════════════════════════════════════════════════════════════

class ConcurrentExpiryClobberTests(SimpleTestCase):
    """At the expiry boundary two confirms can race: A pays and commits PAID; B sees the
    code as expired. B's EXPIRED write must be a guarded update (status=PENDING) executed
    INSIDE the row lock — NOT a deferred, unlocked save() that would overwrite A's PAID."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
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

    def _expired_req(self):
        from django.utils import timezone
        from datetime import timedelta
        return SimpleNamespace(
            id=7, driver_id=5, amount=Decimal("120.00"), code="123456",
            status="pending", expires_at=timezone.now() - timedelta(minutes=5),
            currency="MAD", save=MagicMock(),
        )

    def test_expired_write_is_guarded_update_not_blind_save(self):
        req = self._expired_req()
        (self.m["dcr"].objects.select_for_update
            .return_value.filter.return_value.first.return_value) = req
        # Model the concurrent case: a racing confirm already PAID the row, so the guarded
        # UPDATE matches 0 rows (WHERE status=PENDING no longer holds) and no row is touched.
        self.m["dcr"].objects.filter.return_value.update.return_value = 0

        with self.assertRaises(CashoutError) as ctx:
            confirm_cashout("123456", tenant_id=3, actor_user_id=8)

        # Caller still sees the expired signal.
        self.assertEqual(ctx.exception.code, "expired")
        # The EXPIRED transition was written by a GUARDED update carrying the status=PENDING
        # guard — so a concurrently-committed PAID row is NOT clobbered.
        self.m["dcr"].objects.filter.assert_called_once_with(
            pk=req.id, status=self.m["dcr"].Status.PENDING
        )
        upd = self.m["dcr"].objects.filter.return_value.update
        upd.assert_called_once()
        self.assertIs(upd.call_args.kwargs["status"], self.m["dcr"].Status.EXPIRED)
        # NO deferred, unlocked blind save — that was the clobber window.
        req.save.assert_not_called()
        # No money moved on an expired code.
        self.m["debit"].assert_not_called()
        self.m["credit"].assert_not_called()
        # A well-formed-but-expired code is NOT a wrong-code guess: no brute-force failure.
        from django.core.cache import cache
        self.assertFalse(cache.get(_cashout_fail_cache_key(actor_user_id=8, tenant_id=3)))
