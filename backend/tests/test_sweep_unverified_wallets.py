"""Tests for the sweep_unverified_wallets management command (DB-backed → CI)."""
from decimal import Decimal
from io import StringIO

import pytest

import _dbprobe

from django.core.management import call_command
from django.test import TransactionTestCase

_DB_AVAILABLE = _dbprobe.db_available()


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


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class SweepSkipsCardPaidTests(TransactionTestCase):
    """Wave M M-08: a customer who topped up by card (TOPUP row on the ledger)
    is skipped by default — their balance is real card money, not a pre-rule
    artefact. --include-card-paid opts back in."""

    def setUp(self):
        from accounts.models import Customer, WalletTransaction
        self.card_paid = Customer.objects.create(
            name="CardPaid", wallet_balance=Decimal("30.00"),
            phone="+212600000020", phone_verified=False,
        )
        WalletTransaction.objects.create(
            customer=self.card_paid, type=WalletTransaction.Type.TOPUP,
            amount=Decimal("30.00"), reference="stripe:cs_x",
            balance_after=Decimal("30.00"),
        )
        self.no_topup = Customer.objects.create(
            name="NoTopup", wallet_balance=Decimal("25.00"),
            phone="+212600000021", phone_verified=False,
        )

    def _bal(self, cust):
        from accounts.models import Customer
        return Customer.objects.get(pk=cust.pk).wallet_balance

    def test_dry_run_reports_skipped_card_paid(self):
        out = StringIO()
        call_command("sweep_unverified_wallets", stdout=out)
        self.assertIn("Skipped 1 customer(s) who topped up by card", out.getvalue())
        self.assertEqual(self._bal(self.card_paid), Decimal("30.00"))
        self.assertEqual(self._bal(self.no_topup), Decimal("25.00"))

    def test_apply_skips_card_paid_by_default(self):
        call_command("sweep_unverified_wallets", "--apply", stdout=StringIO())
        self.assertEqual(self._bal(self.card_paid), Decimal("30.00"))  # untouched
        self.assertEqual(self._bal(self.no_topup), Decimal("0.00"))    # swept

    def test_include_card_paid_sweeps_both(self):
        call_command("sweep_unverified_wallets", "--apply", "--include-card-paid", stdout=StringIO())
        self.assertEqual(self._bal(self.card_paid), Decimal("0.00"))
        self.assertEqual(self._bal(self.no_topup), Decimal("0.00"))
