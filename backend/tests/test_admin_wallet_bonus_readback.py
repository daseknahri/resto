"""P2-11 — AdminWalletBonusView: bulk-credit read-back + mutex release.

The audit asked whether the bulk-credit read-back could race: the view does a
bulk F() UPDATE of wallet_balance, reads the new balances back, then
bulk_creates BONUS ledger rows with balance_after from that read-back. The
analysis (see RESUME.md) says the read-back is safe under Postgres READ
COMMITTED — the UPDATE holds the row locks until commit, so no concurrent
writer can commit in between. These tests lock that in on a real DB:

  Sequential (plain TestCase — Postgres only, like the MFA B tests:
  the suite's DATABASES points at Postgres localhost:5432, and there is
  no local Postgres, so these skip locally and run in the DB stage):
    * a bonus credits each customer by exactly the amount AND every BONUS
      ledger row's balance_after equals the customer's balance after it;
    * a repeat POST with the same client idempotency_key is a duplicate
      (balances + ledger untouched);
    * a repeat POST with NO client key is a duplicate too (server fingerprint);
    * a FAILED attempt releases the 60s mutex — a retry with the same key
      succeeds instead of being misreported as a duplicate (the P2-11 fix).

  Threaded (TransactionTestCase, Postgres only — skips without it, like the
  MFA B tests): a bonus racing a credit_wallet on the same customer still
  lands both ledger rows with one of the two valid serial-ordering
  balance_after sets ({150, 180} bonus-first, {130, 180} credit-first),
  never a stale one.
"""
import itertools
import threading
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

import _dbprobe
from accounts.models import Customer, User, WalletTransaction
from accounts.wallet_service import credit_wallet

_DB_AVAILABLE = _dbprobe.db_available()

_phone_seq = itertools.count(600900010)


def _uphone():
    return "+212" + str(next(_phone_seq))


def _admin_client():
    admin = User.objects.create_superuser(username="bonus-admin-g", password="x")
    client = APIClient(SERVER_NAME="localhost")
    client.force_authenticate(user=admin)
    return client


def _customer(balance="0"):
    return Customer.objects.create(
        name="Bonus", wallet_balance=Decimal(balance),
        phone=_uphone(), phone_verified=True,
    )


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class BonusReadbackTests(TestCase):
    """Sequential real-DB checks. Postgres-only like the MFA B tests
    (skip gracefully without it — the local suite has no Postgres)."""
    def setUp(self):
        self.client = _admin_client()
        self.c1 = _customer("100")
        self.c2 = _customer("40")

    def _post(self, body):
        return self.client.post("/api/admin/wallet/bonus/", body, format="json")

    def _balance(self, customer):
        return Customer.objects.get(pk=customer.pk).wallet_balance

    def _bonus_rows(self, customer):
        return list(
            WalletTransaction.objects.filter(
                customer=customer, type=WalletTransaction.Type.BONUS
            ).order_by("id")
        )

    def test_bonus_credits_exactly_and_ledger_matches_balance(self):
        resp = self._post({
            "amount": "50", "note": "Wave G check",
            "customer_ids": [self.c1.id, self.c2.id],
            "idempotency_key": f"wg-readback-{uuid.uuid4().hex[:12]}",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["issued_to"], 2)
        self.assertEqual(self._balance(self.c1), Decimal("150.00"))
        self.assertEqual(self._balance(self.c2), Decimal("90.00"))
        for customer, expected in ((self.c1, Decimal("150.00")), (self.c2, Decimal("90.00"))):
            rows = self._bonus_rows(customer)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].amount, Decimal("50.00"))
            self.assertEqual(rows[0].balance_after, expected)

    def test_repeat_with_same_client_key_is_duplicate(self):
        key = f"wg-dup-{uuid.uuid4().hex[:12]}"
        body = {"amount": "25", "note": "dup", "customer_ids": [self.c1.id], "idempotency_key": key}
        first = self._post(body)
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(self._balance(self.c1), Decimal("125.00"))
        second = self._post(body)
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertTrue(second.data.get("duplicate"))
        self.assertEqual(self._balance(self.c1), Decimal("125.00"))
        self.assertEqual(len(self._bonus_rows(self.c1)), 1)

    def test_repeat_without_client_key_is_duplicate_via_fingerprint(self):
        body = {"amount": "25", "note": "fp", "customer_ids": [self.c1.id]}
        first = self._post(body)
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        second = self._post(body)
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertTrue(second.data.get("duplicate"))
        self.assertEqual(self._balance(self.c1), Decimal("125.00"))
        self.assertEqual(len(self._bonus_rows(self.c1)), 1)

    def test_failed_attempt_releases_mutex_so_retry_succeeds(self):
        """P2-11 fix: force bulk_create to raise once (after the lock was
        taken), then retry the same POST — the retry must succeed, not come
        back as a duplicate with issued_to 0."""
        key = f"wg-mutex-{uuid.uuid4().hex[:12]}"
        body = {"amount": "10", "note": "mutex", "customer_ids": [self.c1.id], "idempotency_key": key}
        real_bulk = WalletTransaction.objects.bulk_create
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return real_bulk(*args, **kwargs)

        with patch.object(WalletTransaction.objects, "bulk_create", side_effect=flaky):
            with self.assertRaises(RuntimeError):
                self._post(body)
        # Nothing was issued (the atomic block rolled back) and the lock is gone.
        self.assertEqual(self._balance(self.c1), Decimal("100.00"))
        self.assertEqual(len(self._bonus_rows(self.c1)), 0)
        self.assertIsNone(cache.get(f"walletbonus:{key}"))
        # The retry succeeds and credits exactly once.
        retry = self._post(body)
        self.assertEqual(retry.status_code, status.HTTP_200_OK, retry.data)
        self.assertEqual(retry.data.get("issued_to"), 1)
        self.assertFalse(retry.data.get("duplicate", False))
        self.assertEqual(self._balance(self.c1), Decimal("110.00"))
        self.assertEqual(len(self._bonus_rows(self.c1)), 1)
        self.assertEqual(self._bonus_rows(self.c1)[0].balance_after, Decimal("110.00"))


def _run_in_parallel(fn, n=2):
    """Run fn(i) in n threads that start together, each on its own DB
    connection (same helper shape as test_money_concurrency)."""
    barrier = threading.Barrier(n)
    results = [None] * n
    errors = [None] * n

    def worker(i):
        try:
            barrier.wait(timeout=30)
            results[i] = fn(i)
        except Exception as exc:
            errors[i] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=40)
    return results, errors


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class BonusRaceTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="bonus-admin-race", password="x")
        self.customer = _customer("100")

    def _bonus_post(self):
        client = APIClient(SERVER_NAME="localhost")
        client.force_authenticate(user=self.admin)
        return client.post("/api/admin/wallet/bonus/", {
            "amount": "50", "note": "race",
            "customer_ids": [self.customer.id],
            "idempotency_key": f"wg-race-{uuid.uuid4().hex[:12]}",
        }, format="json")

    def test_bonus_racing_a_credit_keeps_ledger_consistent(self):
        """Bonus (+50) racing a wallet credit (+30) on the same customer:
        the final balance is 180 and the two ledger rows' balance_after
        values are exactly one of the two valid serial orderings — {150, 180}
        when the bonus commits first, {130, 180} when the credit commits
        first — never a stale pre-race balance (100). Both legs serialize on
        the Customer row lock (bonus: F() UPDATE held to commit; credit:
        select_for_update), so whichever commits second reads the first
        leg's balance. The credit leg usually wins the race (direct call vs
        the bonus's DRF round trip), so {130, 180} is the common outcome."""
        results, errors = _run_in_parallel(
            lambda i: self._bonus_post() if i == 0 else credit_wallet(
                self.customer.id, "30", idempotency_key=f"wg-race-credit-{uuid.uuid4().hex[:12]}"
            )
        )
        self.assertEqual(errors, [None, None], f"unexpected errors: {errors}")
        self.assertEqual(results[0].status_code, status.HTTP_200_OK, results[0].data)
        final = Customer.objects.get(pk=self.customer.pk).wallet_balance
        self.assertEqual(final, Decimal("180.00"))
        bonus_after = WalletTransaction.objects.get(
            customer=self.customer, type=WalletTransaction.Type.BONUS
        ).balance_after
        topup_after = WalletTransaction.objects.get(
            customer=self.customer, type=WalletTransaction.Type.TOPUP
        ).balance_after
        # Either serial ordering is a consistent ledger: exactly one leg
        # commits first (150 for the bonus, 130 for the credit) and the
        # second reads that balance and lands on 180.
        self.assertIn(
            {bonus_after, topup_after},
            [
                {Decimal("150.00"), Decimal("180.00")},
                {Decimal("130.00"), Decimal("180.00")},
            ],
        )
