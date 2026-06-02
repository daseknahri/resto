"""Tests for the central wallet ledger service (accounts/wallet_service.py).

The money-movement tests need a real DB (row locking + transactions), so they run
as DB-backed TransactionTestCases in CI. The amount-normalization helper is pure
and covered by a SimpleTestCase that runs anywhere.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TransactionTestCase

from accounts.wallet_service import (
    InsufficientFunds,
    WalletError,
    _money,
    credit_wallet,
    debit_wallet,
)


class MoneyHelperTests(SimpleTestCase):
    def test_normalizes_to_two_decimals(self):
        self.assertEqual(_money("10.5"), Decimal("10.50"))
        self.assertEqual(_money(10), Decimal("10.00"))
        self.assertEqual(_money(None), Decimal("0.00"))

    def test_invalid_amount_raises(self):
        with self.assertRaises(WalletError):
            _money("not-a-number")


class WalletServiceTests(TransactionTestCase):
    """Exercises the real ledger (needs a DB). Skipped automatically where no DB."""

    def setUp(self):
        from accounts.models import Customer
        self.customer = Customer.objects.create(name="Wallet Test", wallet_balance=Decimal("0"))

    def _balance(self):
        from accounts.models import Customer
        return Customer.objects.get(pk=self.customer.pk).wallet_balance

    def test_credit_increases_balance_and_snapshots(self):
        from accounts.models import WalletTransaction
        tx = credit_wallet(self.customer.id, "50", tx_type=WalletTransaction.Type.TOPUP, currency="MAD")
        self.assertEqual(self._balance(), Decimal("50.00"))
        self.assertEqual(tx.amount, Decimal("50.00"))
        self.assertEqual(tx.balance_after, Decimal("50.00"))

    def test_credit_is_idempotent(self):
        a = credit_wallet(self.customer.id, "20", idempotency_key="evt_123")
        b = credit_wallet(self.customer.id, "20", idempotency_key="evt_123")
        self.assertEqual(a.id, b.id)             # same row reused
        self.assertEqual(self._balance(), Decimal("20.00"))  # credited once, not twice

    def test_debit_decreases_balance_positive_magnitude(self):
        from accounts.models import WalletTransaction
        credit_wallet(self.customer.id, "30")
        tx = debit_wallet(self.customer.id, "10", reference="ORD-1", tenant_id=1)
        self.assertEqual(self._balance(), Decimal("20.00"))
        self.assertEqual(tx.amount, Decimal("10.00"))            # stored positive
        self.assertEqual(tx.type, WalletTransaction.Type.PAYMENT)
        self.assertEqual(tx.balance_after, Decimal("20.00"))

    def test_debit_insufficient_raises_and_leaves_balance(self):
        credit_wallet(self.customer.id, "5")
        with self.assertRaises(InsufficientFunds):
            debit_wallet(self.customer.id, "10")
        self.assertEqual(self._balance(), Decimal("5.00"))

    def test_debit_partial_charges_available(self):
        credit_wallet(self.customer.id, "5")
        tx = debit_wallet(self.customer.id, "10", allow_partial=True)
        self.assertEqual(tx.amount, Decimal("5.00"))
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_debit_is_idempotent(self):
        credit_wallet(self.customer.id, "100")
        a = debit_wallet(self.customer.id, "15", idempotency_key="pay_1", reference="ORD-9")
        b = debit_wallet(self.customer.id, "15", idempotency_key="pay_1", reference="ORD-9")
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._balance(), Decimal("85.00"))  # charged once
