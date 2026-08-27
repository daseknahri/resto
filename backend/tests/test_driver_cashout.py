"""
Tests for driver cash-out (DV3): create-request validation + the atomic confirm
(debit driver wallet → credit restaurant float). Unit-level (SimpleTestCase + mocks).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.driver_service import (
    create_cashout_request, confirm_cashout, CashoutError, CASHOUT_MIN,
    _cashout_fail_cache_key,
)


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class CreateCashoutTests(SimpleTestCase):
    def setUp(self):
        # create_cashout_request now locks the driver row inside transaction.atomic()
        # (TOCTOU fix). Make atomic a no-op so these no-DB unit tests don't hit the DB.
        self._atomic = patch("django.db.transaction.atomic", return_value=_noop_atomic())
        self._atomic.start()
        self.addCleanup(self._atomic.stop)

    @patch("accounts.models.Customer")
    def test_below_min_rejected(self, Cust):
        Cust.objects.select_for_update.return_value.filter.return_value.first.return_value = SimpleNamespace(
            wallet_balance=Decimal("50"), driver_approved=True)
        with self.assertRaises(CashoutError) as ctx:
            create_cashout_request(1, "50")
        self.assertEqual(ctx.exception.code, "below_min")

    @patch("accounts.models.Customer")
    def test_not_approved_rejected(self, Cust):
        Cust.objects.select_for_update.return_value.filter.return_value.first.return_value = SimpleNamespace(
            wallet_balance=Decimal("150"), driver_approved=False)
        with self.assertRaises(CashoutError) as ctx:
            create_cashout_request(1, "120")
        self.assertEqual(ctx.exception.code, "not_approved")

    @patch("accounts.models.Customer")
    def test_amount_over_balance_rejected(self, Cust):
        Cust.objects.select_for_update.return_value.filter.return_value.first.return_value = SimpleNamespace(
            wallet_balance=Decimal("120"), driver_approved=True)
        with self.assertRaises(CashoutError) as ctx:
            create_cashout_request(1, "200")
        self.assertEqual(ctx.exception.code, "bad_amount")

    @patch("accounts.models.DriverCashoutRequest")
    @patch("accounts.models.Customer")
    def test_happy_path_creates_request(self, Cust, DCR):
        Cust.objects.select_for_update.return_value.filter.return_value.first.return_value = SimpleNamespace(
            wallet_balance=Decimal("150"), driver_approved=True)
        DCR.objects.filter.return_value.exists.return_value = False  # code is unique + no pending
        DCR.objects.create.return_value = SimpleNamespace(id=1, amount=Decimal("120.00"), code="123456")
        create_cashout_request(1, "120")
        DCR.objects.create.assert_called_once()
        kw = DCR.objects.create.call_args.kwargs
        self.assertEqual(kw["driver_id"], 1)
        self.assertEqual(kw["amount"], Decimal("120.00"))
        self.assertTrue(kw["code"].isdigit())

    def test_min_is_100(self):
        self.assertEqual(CASHOUT_MIN, Decimal("100"))


class ConfirmCashoutTests(SimpleTestCase):
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
        from django.utils import timezone
        from datetime import timedelta
        return SimpleNamespace(
            id=7, driver_id=5, amount=Decimal(amount), code="123456",
            status="pending", expires_at=timezone.now() + timedelta(minutes=10),
            currency="MAD", save=MagicMock(),
        )

    def test_not_found(self):
        self.m["dcr"].objects.select_for_update.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(CashoutError) as ctx:
            confirm_cashout("000000", tenant_id=3)
        self.assertEqual(ctx.exception.code, "not_found")

    def test_confirm_debits_driver_and_credits_float(self):
        req = self._pending()
        self.m["dcr"].objects.select_for_update.return_value.filter.return_value.first.return_value = req
        self.m["debit"].return_value = SimpleNamespace(id=99)
        out = confirm_cashout("123456", tenant_id=3, actor_user_id=8)
        # driver wallet debited for the amount...
        self.m["debit"].assert_called_once()
        dkw = self.m["debit"].call_args
        self.assertEqual(dkw.args[0], 5)              # driver_id
        self.assertEqual(dkw.args[1], Decimal("120.00"))
        # ...and the restaurant float credited the same
        self.m["credit"].assert_called_once()
        ckw = self.m["credit"].call_args
        self.assertEqual(ckw.args[0], 3)              # tenant_id
        self.assertEqual(ckw.args[1], Decimal("120.00"))
        self.assertEqual(req.status, self.m["dcr"].Status.PAID)  # marked paid
        self.assertEqual(req.tenant_id, 3)
        req.save.assert_called_once()


class _RollbackAtomic:
    """A ``transaction.atomic()`` test double that models rollback-on-exception.

    ``db`` is a mutable dict the ``req.save()`` side-effect writes into. On enter we
    snapshot it; if the block exits via an exception we RESTORE the snapshot (rollback),
    and if it exits cleanly we KEEP the writes (commit). This lets a no-DB unit test
    observe whether the EXPIRED status write actually survives (the fix) or is discarded
    by a raise-inside-atomic (the bug)."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self._snapshot = dict(self.db)
        return None

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.db.clear()
            self.db.update(self._snapshot)
        return False  # never suppress the exception


class ConfirmCashoutExpiryTests(SimpleTestCase):
    """Bug: an EXPIRED cash-out code marked its status inside the atomic block that then
    raised, so the EXPIRED write was ROLLED BACK (row stayed PENDING), and it was counted
    as a brute-force failure — which can lock out an honest driver/restaurant whose valid
    code merely lapsed. Fix: persist EXPIRED durably (own transaction, after the block) and
    do NOT record a failure for a well-formed-but-expired code."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        # `db` is the simulated persisted row state; req.save() writes req.status into it.
        self.db = {"status": "pending"}
        self._p = {
            "dcr": patch("accounts.models.DriverCashoutRequest"),
            "debit": patch("accounts.wallet_service.debit_wallet"),
            "credit": patch("accounts.wallet_service.credit_tenant_float"),
            # atomic returns a fresh rollback-modelling CM per call, all sharing self.db.
            "atomic": patch(
                "django.db.transaction.atomic",
                side_effect=lambda *a, **k: _RollbackAtomic(self.db),
            ),
        }
        self.m = {k: v.start() for k, v in self._p.items()}

    def tearDown(self):
        for v in self._p.values():
            v.stop()

    def _expired_req(self):
        from django.utils import timezone
        from datetime import timedelta
        req = SimpleNamespace(
            id=7, driver_id=5, amount=Decimal("120.00"), code="123456",
            status="pending", expires_at=timezone.now() - timedelta(minutes=5),
            currency="MAD",
        )

        def _save(update_fields=None):
            # Model a real save: commit the current in-memory status to the "row".
            self.db["status"] = req.status

        req.save = MagicMock(side_effect=_save)
        return req

    def test_expired_code_persists_expired_and_does_not_record_failure(self):
        req = self._expired_req()
        (self.m["dcr"].objects.select_for_update
            .return_value.filter.return_value.first.return_value) = req

        with self.assertRaises(CashoutError) as ctx:
            confirm_cashout("123456", tenant_id=3, actor_user_id=8)

        # Caller still sees the expired signal.
        self.assertEqual(ctx.exception.code, "expired")
        # The EXPIRED transition is DURABLE — it survived the block instead of rolling back.
        self.assertIs(self.db["status"], self.m["dcr"].Status.EXPIRED)
        self.assertIs(req.status, self.m["dcr"].Status.EXPIRED)
        req.save.assert_called_once()
        # No money moved on an expired code.
        self.m["debit"].assert_not_called()
        self.m["credit"].assert_not_called()
        # A well-formed-but-expired code is NOT a wrong-code guess: no brute-force failure.
        fail_key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        from django.core.cache import cache
        self.assertFalse(cache.get(fail_key))

    def test_wrong_code_still_records_failure(self):
        """Control: a genuinely wrong code (no pending match) DOES count as a failure."""
        (self.m["dcr"].objects.select_for_update
            .return_value.filter.return_value.first.return_value) = None

        with self.assertRaises(CashoutError) as ctx:
            confirm_cashout("000000", tenant_id=3, actor_user_id=8)

        self.assertEqual(ctx.exception.code, "not_found")
        fail_key = _cashout_fail_cache_key(actor_user_id=8, tenant_id=3)
        from django.core.cache import cache
        self.assertEqual(cache.get(fail_key), 1)
