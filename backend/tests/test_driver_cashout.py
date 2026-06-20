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
