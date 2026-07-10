"""Tests for record_driver_payout — owed-cap + idempotency + driver-row lock (MONEY-2).

Needs a real DB (aggregates + select_for_update), so these run as DB-backed
TransactionTestCases in CI and join the DB-only errors when run without Postgres. The
row lock's concurrency guarantee can't be exercised in a single-threaded test, but the
sequential invariant it enforces (a later payout sees every committed prior payout in
`paid`, so totals can never exceed `earned`) is covered here.
"""
from decimal import Decimal
import itertools

from django.test import TransactionTestCase
from django.utils import timezone

from accounts.driver_service import driver_earnings_summary, record_driver_payout
from accounts.wallet_service import WalletError

_phone_seq = itertools.count(600700010)
_ordn_seq = itertools.count(1)


def _uphone():
    return "+212" + str(next(_phone_seq))


class RecordDriverPayoutTests(TransactionTestCase):
    def _driver(self):
        from accounts.models import Customer
        return Customer.objects.create(
            name="Payout Driver", phone=_uphone(), phone_verified=True, is_driver=True,
        )

    def _deliver(self, driver, payout):
        """A DELIVERED job with a driver_payout — this is what `earned` sums over."""
        from accounts.models import DeliveryJob
        return DeliveryJob.objects.create(
            tenant_id=1, order_number=f"ORD-{next(_ordn_seq)}", driver=driver,
            status=DeliveryJob.Status.DELIVERED, driver_payout=Decimal(payout),
            delivered_at=timezone.now(),
        )

    def test_payout_up_to_owed_succeeds_and_reduces_owed(self):
        d = self._driver()
        self._deliver(d, "100")
        self.assertEqual(driver_earnings_summary(d.id)["owed"], Decimal("100.00"))
        p = record_driver_payout(d.id, "60")
        self.assertEqual(p.amount, Decimal("60.00"))
        self.assertEqual(driver_earnings_summary(d.id)["owed"], Decimal("40.00"))

    def test_payout_exceeding_owed_is_rejected(self):
        d = self._driver()
        self._deliver(d, "50")
        with self.assertRaises(WalletError):
            record_driver_payout(d.id, "60")
        self.assertEqual(driver_earnings_summary(d.id)["paid"], Decimal("0.00"))

    def test_sequential_payouts_cannot_exceed_owed(self):
        # The essence of MONEY-2: a later payout sees the earlier committed one in `paid`,
        # so total settlements can never exceed `earned`. The driver-row lock makes this
        # hold under concurrency, not merely sequentially.
        d = self._driver()
        self._deliver(d, "100")
        record_driver_payout(d.id, "70")
        with self.assertRaises(WalletError):
            record_driver_payout(d.id, "40")    # 70 + 40 > 100 → rejected
        record_driver_payout(d.id, "30")        # 70 + 30 == 100 exactly → OK
        self.assertEqual(driver_earnings_summary(d.id)["owed"], Decimal("0.00"))

    def test_idempotent_replay_does_not_double_pay(self):
        d = self._driver()
        self._deliver(d, "100")
        a = record_driver_payout(d.id, "40", idempotency_key="payout-1")
        b = record_driver_payout(d.id, "40", idempotency_key="payout-1")
        self.assertEqual(a.id, b.id)                                       # same row
        self.assertEqual(driver_earnings_summary(d.id)["paid"], Decimal("40.00"))  # once

    def test_idempotency_key_collision_across_drivers_is_rejected(self):
        # A caller-supplied key that already belongs to ANOTHER driver's payout must be
        # refused, not silently handed back (which would falsely acknowledge a payout to a
        # driver who received nothing). Mirrors the wallet_service collision guards.
        x = self._driver(); self._deliver(x, "100")
        y = self._driver(); self._deliver(y, "100")
        record_driver_payout(x.id, "40", idempotency_key="shared-key")
        with self.assertRaises(WalletError):
            record_driver_payout(y.id, "40", idempotency_key="shared-key")
        self.assertEqual(driver_earnings_summary(y.id)["paid"], Decimal("0.00"))  # Y unpaid

    def test_missing_driver_is_rejected(self):
        # Fail closed if the driver row is absent — the lock (and thus the mutex) would
        # otherwise be a silent no-op for a future caller that skips the view's pre-check.
        from django.db.models import Max
        from accounts.models import Customer
        free_id = (Customer.objects.aggregate(m=Max("id"))["m"] or 0) + 100000
        with self.assertRaises(WalletError):
            record_driver_payout(free_id, "10")
