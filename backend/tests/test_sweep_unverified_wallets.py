"""Tests for the sweep_unverified_wallets management command (DB-backed → CI)."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TransactionTestCase


class SweepUnverifiedWalletsTests(TransactionTestCase):
    def setUp(self):
        from accounts.models import Customer
        self.unverified = Customer.objects.create(
            name="Unverified", wallet_balance=Decimal("25.00"), phone="+212600000010", phone_verified=False,
        )
        self.verified = Customer.objects.create(
            name="Verified", wallet_balance=Decimal("40.00"), phone="+212600000011", phone_verified=True,
        )

    def _bal(self, cust):
        from accounts.models import Customer
        return Customer.objects.get(pk=cust.pk).wallet_balance

    def test_dry_run_changes_nothing(self):
        out = StringIO()
        call_command("sweep_unverified_wallets", stdout=out)
        self.assertIn("dry-run", out.getvalue())
        self.assertEqual(self._bal(self.unverified), Decimal("25.00"))  # untouched
        self.assertEqual(self._bal(self.verified), Decimal("40.00"))

    def test_apply_zeroes_only_unverified_and_records_adjustment(self):
        from accounts.models import WalletTransaction
        call_command("sweep_unverified_wallets", "--apply", stdout=StringIO())
        self.assertEqual(self._bal(self.unverified), Decimal("0.00"))   # swept
        self.assertEqual(self._bal(self.verified), Decimal("40.00"))    # left alone
        adj = WalletTransaction.objects.filter(
            customer=self.unverified, type=WalletTransaction.Type.ADJUSTMENT
        ).first()
        self.assertIsNotNone(adj)
        self.assertEqual(adj.amount, Decimal("25.00"))
        self.assertEqual(adj.balance_after, Decimal("0.00"))
