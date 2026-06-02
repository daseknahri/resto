"""Tests for the central wallet ledger service (accounts/wallet_service.py).

The money-movement tests need a real DB (row locking + transactions), so they run
as DB-backed TransactionTestCases in CI. The amount-normalization helper is pure
and covered by a SimpleTestCase that runs anywhere.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TransactionTestCase

from accounts.wallet_service import (
    InactiveTenant,
    InsufficientFunds,
    UnverifiedWallet,
    WalletError,
    _money,
    credit_tenant_float,
    credit_wallet,
    debit_wallet,
    transfer_between_customers,
    transfer_to_customer,
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
        self.customer = Customer.objects.create(
            name="Wallet Test", wallet_balance=Decimal("0"), phone="+212600000001", phone_verified=True,
        )

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

    def test_credit_to_unverified_phone_is_refused(self):
        from accounts.models import Customer
        unverified = Customer.objects.create(name="No Phone", wallet_balance=Decimal("0"))
        with self.assertRaises(UnverifiedWallet):
            credit_wallet(unverified.id, "10")
        self.assertEqual(
            Customer.objects.get(pk=unverified.pk).wallet_balance, Decimal("0.00")
        )


class TenantFloatTransferTests(TransactionTestCase):
    """Platform-funds-restaurant → restaurant-funds-customer (needs a DB)."""

    def setUp(self):
        from accounts.models import Customer
        from tenancy.models import Plan, Tenant
        self.customer = Customer.objects.create(
            name="Float Test", wallet_balance=Decimal("0"), phone="+212600000002", phone_verified=True,
        )
        self.plan = Plan.objects.create(name="Test Plan", code="test-float-plan")
        # auto_create_schema=False: we only need the public-schema row (the float lives
        # on it), not a physical tenant schema — keeps the test light.
        self.tenant = Tenant(schema_name="test_float_t", name="Float Resto",
                             slug="float-resto", plan=self.plan, float_balance=Decimal("0"))
        self.tenant.auto_create_schema = False
        self.tenant.save()

    def _float(self):
        from tenancy.models import Tenant
        return Tenant.objects.get(pk=self.tenant.pk).float_balance

    def _wallet(self):
        from accounts.models import Customer
        return Customer.objects.get(pk=self.customer.pk).wallet_balance

    def test_fund_increases_float_and_snapshots(self):
        from accounts.models import TenantFloatTransaction
        tx = credit_tenant_float(self.tenant.id, "500", note="Cash 2026-06-01")
        self.assertEqual(self._float(), Decimal("500.00"))
        self.assertEqual(tx.type, TenantFloatTransaction.Type.FUND)
        self.assertEqual(tx.balance_after, Decimal("500.00"))

    def test_fund_is_idempotent(self):
        a = credit_tenant_float(self.tenant.id, "100", idempotency_key="fund_1")
        b = credit_tenant_float(self.tenant.id, "100", idempotency_key="fund_1")
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._float(), Decimal("100.00"))  # funded once

    def test_transfer_moves_float_to_wallet(self):
        from accounts.models import TenantFloatTransaction, WalletTransaction
        credit_tenant_float(self.tenant.id, "200")
        float_tx, wallet_tx = transfer_to_customer(self.tenant.id, self.customer.id, "30", actor_user_id=7)
        self.assertEqual(self._float(), Decimal("170.00"))   # debited
        self.assertEqual(self._wallet(), Decimal("30.00"))   # credited
        self.assertEqual(float_tx.type, TenantFloatTransaction.Type.DISTRIBUTION)
        self.assertEqual(float_tx.balance_after, Decimal("170.00"))
        self.assertEqual(float_tx.customer_id, self.customer.id)
        self.assertEqual(float_tx.actor_user_id, 7)
        self.assertEqual(wallet_tx.type, WalletTransaction.Type.TOPUP)
        self.assertEqual(wallet_tx.balance_after, Decimal("30.00"))

    def test_transfer_blocked_when_float_insufficient(self):
        credit_tenant_float(self.tenant.id, "5")
        with self.assertRaises(InsufficientFunds):
            transfer_to_customer(self.tenant.id, self.customer.id, "10")
        # Nothing moved on either side.
        self.assertEqual(self._float(), Decimal("5.00"))
        self.assertEqual(self._wallet(), Decimal("0.00"))

    def test_suspended_tenant_cannot_fund_or_distribute(self):
        from tenancy.models import Tenant
        credit_tenant_float(self.tenant.id, "100")  # fund while active
        Tenant.objects.filter(pk=self.tenant.pk).update(lifecycle_status="suspended")
        with self.assertRaises(InactiveTenant):
            credit_tenant_float(self.tenant.id, "50")
        with self.assertRaises(InactiveTenant):
            transfer_to_customer(self.tenant.id, self.customer.id, "10")
        self.assertEqual(self._float(), Decimal("100.00"))  # unchanged
        self.assertEqual(self._wallet(), Decimal("0.00"))

    def test_transfer_is_idempotent(self):
        credit_tenant_float(self.tenant.id, "100")
        a, _ = transfer_to_customer(self.tenant.id, self.customer.id, "20", idempotency_key="xfer_1")
        b, _ = transfer_to_customer(self.tenant.id, self.customer.id, "20", idempotency_key="xfer_1")
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._float(), Decimal("80.00"))   # distributed once
        self.assertEqual(self._wallet(), Decimal("20.00"))


class P2PTransferTests(TransactionTestCase):
    """Customer-to-customer gifting (needs a DB)."""

    def setUp(self):
        from accounts.models import Customer
        self.alice = Customer.objects.create(
            name="Alice", wallet_balance=Decimal("0"), phone="+212600000003", phone_verified=True,
        )
        self.bob = Customer.objects.create(
            name="Bob", wallet_balance=Decimal("0"), phone="+212600000004", phone_verified=True,
        )

    def _bal(self, cust):
        from accounts.models import Customer
        return Customer.objects.get(pk=cust.pk).wallet_balance

    def test_transfer_moves_credit_between_wallets(self):
        from accounts.models import WalletTransaction
        credit_wallet(self.alice.id, "50")
        out_tx, in_tx = transfer_between_customers(self.alice.id, self.bob.id, "20", note="Thanks")
        self.assertEqual(self._bal(self.alice), Decimal("30.00"))
        self.assertEqual(self._bal(self.bob), Decimal("20.00"))
        self.assertEqual(out_tx.type, WalletTransaction.Type.TRANSFER_OUT)
        self.assertEqual(out_tx.balance_after, Decimal("30.00"))
        self.assertEqual(in_tx.type, WalletTransaction.Type.TRANSFER_IN)
        self.assertEqual(in_tx.balance_after, Decimal("20.00"))

    def test_transfer_insufficient_balance_moves_nothing(self):
        credit_wallet(self.alice.id, "5")
        with self.assertRaises(InsufficientFunds):
            transfer_between_customers(self.alice.id, self.bob.id, "10")
        self.assertEqual(self._bal(self.alice), Decimal("5.00"))
        self.assertEqual(self._bal(self.bob), Decimal("0.00"))

    def test_cannot_transfer_to_self(self):
        credit_wallet(self.alice.id, "50")
        with self.assertRaises(WalletError):
            transfer_between_customers(self.alice.id, self.alice.id, "10")
        self.assertEqual(self._bal(self.alice), Decimal("50.00"))

    def test_transfer_is_idempotent(self):
        credit_wallet(self.alice.id, "50")
        a, _ = transfer_between_customers(self.alice.id, self.bob.id, "20", idempotency_key="gift_1")
        b, _ = transfer_between_customers(self.alice.id, self.bob.id, "20", idempotency_key="gift_1")
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._bal(self.alice), Decimal("30.00"))  # sent once
        self.assertEqual(self._bal(self.bob), Decimal("20.00"))

    def test_transfer_to_unverified_recipient_is_refused(self):
        from accounts.models import Customer
        carol = Customer.objects.create(name="Carol", wallet_balance=Decimal("0"))  # unverified
        credit_wallet(self.alice.id, "50")
        with self.assertRaises(UnverifiedWallet):
            transfer_between_customers(self.alice.id, carol.id, "10")
        self.assertEqual(self._bal(self.alice), Decimal("50.00"))  # nothing moved
        self.assertEqual(Customer.objects.get(pk=carol.pk).wallet_balance, Decimal("0.00"))
