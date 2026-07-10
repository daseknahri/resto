"""Real multi-threaded concurrency tests for the money services (RISK TEST-1, item 4).

Both `test_wallet_service.py` and `test_driver_payout_service.py` note in their own
docstrings that a single-threaded test cannot exercise the `select_for_update` row
lock's actual concurrency guarantee — only the sequential invariant it happens to also
enforce. Mocks are weaker still: patching `transaction.atomic` / `select_for_update`
(as several older money tests do) verifies Python control flow, not the database's
serialization, so it would pass even if the lock were deleted.

These tests close that gap. Each spins up genuinely concurrent workers — each on its
own DB connection, released together by a `threading.Barrier` so they actually contend —
against the real ledger. A regression that drops or weakens the row lock or the
under-lock idempotency re-check is caught here as the exact race the services were
hardened against:

  • concurrent same-key credit  → double-apply + IntegrityError on the unique key
    (wallet idempotency-under-lock, see accounts/wallet_service.py credit_wallet)
  • concurrent debits           → overspend past the balance / negative wallet
  • concurrent credits          → lost update (both read the old balance)
  • concurrent driver payouts   → double-pay past `owed` (RISK MONEY-2)

Each assertion is deterministic on correct code and only fails when the lock is broken,
so the tests are not timing-flaky: every valid lock interleaving yields the same result.

Needs a real DB with row locking. Like the other money DB suites these are
`TransactionTestCase`s (real commits are visible across the worker connections) and they
join the DB-only errors when run without Postgres. SQLite would not serialize these, so
they are meaningful only on the Postgres CI database.
"""
import itertools
import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.driver_service import driver_earnings_summary, record_driver_payout
from accounts.wallet_service import (
    InsufficientFunds,
    WalletError,
    credit_wallet,
    debit_wallet,
)

# Public-schema rows are NOT truncated between TransactionTestCases under django-tenants
# (see the note in test_wallet_service.py), so mint unique phones / keys per use to avoid
# collisions with rows left by earlier tests.
_phone_seq = itertools.count(600800010)
_key_seq = itertools.count(1)
_ordn_seq = itertools.count(1)

_BARRIER_TIMEOUT = 30  # seconds — fail fast instead of hanging CI if a worker stalls


def _uphone():
    return "+212" + str(next(_phone_seq))


def _ukey(prefix):
    return f"{prefix}-{next(_key_seq)}"


def _run_in_parallel(fn, n=2):
    """Run ``fn(i)`` in *n* threads that start together and each use their own DB
    connection. Returns ``(results, errors)`` lists indexed by worker: ``results[i]``
    is the return value (or None if it raised), ``errors[i]`` the exception (or None).

    The barrier makes the workers contend on the same row lock at the same instant,
    which is what turns this into a real race rather than a sequential replay.
    """
    barrier = threading.Barrier(n)
    results = [None] * n
    errors = [None] * n

    def worker(i):
        try:
            barrier.wait(timeout=_BARRIER_TIMEOUT)
            results[i] = fn(i)
        except Exception as exc:  # expected for the "loser" of a contended write
            errors[i] = exc
        finally:
            # Close THIS worker thread's connection so it doesn't leak past the test.
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_BARRIER_TIMEOUT + 10)
    return results, errors


class WalletConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from accounts.models import Customer
        self.customer = Customer.objects.create(
            name="Concurrency", wallet_balance=Decimal("0"),
            phone=_uphone(), phone_verified=True,
        )

    def _balance(self):
        from accounts.models import Customer
        return Customer.objects.get(pk=self.customer.pk).wallet_balance

    def _tx_count(self, **filters):
        from accounts.models import WalletTransaction
        return WalletTransaction.objects.filter(customer=self.customer, **filters).count()

    def test_concurrent_same_key_credit_applies_once(self):
        """Two racing credits with the SAME idempotency key must credit once, reuse the
        one row, and never 500 on the unique-key constraint — the under-lock re-check."""
        key = _ukey("credit-race")
        results, errors = _run_in_parallel(
            lambda i: credit_wallet(self.customer.id, "20", idempotency_key=key)
        )

        self.assertEqual(errors, [None, None], f"unexpected errors: {errors}")
        # Both calls return a transaction, and it is the SAME row (one replayed).
        self.assertIsNotNone(results[0])
        self.assertIsNotNone(results[1])
        self.assertEqual(results[0].id, results[1].id)
        # Credited exactly once, and exactly one ledger row carries the key.
        self.assertEqual(self._balance(), Decimal("20.00"))
        self.assertEqual(self._tx_count(idempotency_key=key), 1)

    def test_concurrent_debits_cannot_overspend(self):
        """Balance 100, two racing debits of 60. The row lock must serialize them so
        exactly one succeeds and the other sees the fresh (insufficient) balance — the
        wallet can never go negative or pay out 120 against 100."""
        credit_wallet(self.customer.id, "100")
        results, errors = _run_in_parallel(
            lambda i: debit_wallet(self.customer.id, "60")
        )

        successes = [r for r in results if r is not None]
        failures = [e for e in errors if e is not None]
        self.assertEqual(len(successes), 1, "exactly one debit should succeed")
        self.assertEqual(len(failures), 1, "the other debit should be refused")
        self.assertIsInstance(failures[0], InsufficientFunds)
        self.assertEqual(successes[0].amount, Decimal("60.00"))
        self.assertEqual(self._balance(), Decimal("40.00"))  # 100 - 60, never negative
        from accounts.models import WalletTransaction
        self.assertEqual(
            self._tx_count(type=WalletTransaction.Type.PAYMENT), 1  # one charge, not two
        )

    def test_concurrent_credits_do_not_lose_an_update(self):
        """Balance 0, two racing credits of 30 with distinct keys. The lock must prevent a
        lost update: both reads-modify-writes serialize, so the balance ends at 60, not 30."""
        results, errors = _run_in_parallel(
            lambda i: credit_wallet(self.customer.id, "30", idempotency_key=_ukey(f"c{i}"))
        )
        self.assertEqual(errors, [None, None], f"unexpected errors: {errors}")
        self.assertEqual(self._balance(), Decimal("60.00"))  # 30 + 30, no lost update
        from accounts.models import WalletTransaction
        self.assertEqual(self._tx_count(type=WalletTransaction.Type.TOPUP), 2)


class DriverPayoutConcurrencyTests(TransactionTestCase):
    """RISK MONEY-2: two settlements racing on the same driver must not double-pay past
    `owed`. The driver-row lock in record_driver_payout makes the owed re-check see the
    other's committed payout instead of both reading the pre-payout total."""

    def _driver(self):
        from accounts.models import Customer
        return Customer.objects.create(
            name="Payout Race", phone=_uphone(), phone_verified=True, is_driver=True,
        )

    def _deliver(self, driver, payout):
        from accounts.models import DeliveryJob
        return DeliveryJob.objects.create(
            tenant_id=1, order_number=f"ORDC-{next(_ordn_seq)}", driver=driver,
            status=DeliveryJob.Status.DELIVERED, driver_payout=Decimal(payout),
            delivered_at=timezone.now(),
        )

    def test_concurrent_payouts_cannot_exceed_owed(self):
        driver = self._driver()
        self._deliver(driver, "100")  # owed = 100
        self.assertEqual(driver_earnings_summary(driver.id)["owed"], Decimal("100.00"))

        results, errors = _run_in_parallel(
            lambda i: record_driver_payout(driver.id, "60")
        )

        successes = [r for r in results if r is not None]
        failures = [e for e in errors if e is not None]
        self.assertEqual(len(successes), 1, "exactly one payout should settle")
        self.assertEqual(len(failures), 1, "the second payout should be refused")
        self.assertIsInstance(failures[0], WalletError)
        # Total settled is 60, NOT 120 — the double-pay race is closed.
        self.assertEqual(driver_earnings_summary(driver.id)["paid"], Decimal("60.00"))
        self.assertEqual(driver_earnings_summary(driver.id)["owed"], Decimal("40.00"))
