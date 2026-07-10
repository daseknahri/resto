"""Tests for the reconcile_wallet_balances command (MONEY-1).

Asserts the money invariant `denormalized balance == ledger head` is detected/repaired:
  - a matching account is left untouched,
  - a drifted balance is detected and (only with --fix) repaired to the ledger head,
  - an ORPHAN (non-zero balance, no ledger) is detected but NEVER auto-fixed,
  - tenant float drift is reconciled the same way,
  - --deep catches an internally inconsistent ledger even when the head matches.

These need a real DB (subquery reconciliation + row-locked --fix), so they run as
DB-backed TransactionTestCases in CI and join the ~DB-only errors when run without
Postgres. Assertions are account-specific: django-tenants + TransactionTestCase does NOT
truncate public-schema tables between tests, so global summary counts aren't reliable.
"""
from decimal import Decimal
from io import StringIO
import itertools
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase

from accounts.wallet_service import credit_tenant_float, credit_wallet

_phone_seq = itertools.count(600500010)
_suffix_seq = itertools.count(1)


def _uphone():
    return "+212" + str(next(_phone_seq))


def _usuffix():
    return next(_suffix_seq)


def _run(*args):
    out = StringIO()
    call_command("reconcile_wallet_balances", *args, stdout=out, stderr=out)
    return out.getvalue()


class ReconcileWalletTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def _mk_customer(self, balance="0"):
        from accounts.models import Customer
        return Customer.objects.create(
            name="Recon Test", wallet_balance=Decimal(balance),
            phone=_uphone(), phone_verified=True,
        )

    def _balance(self, cid):
        from accounts.models import Customer
        return Customer.objects.get(pk=cid).wallet_balance

    # ── customer wallet ──────────────────────────────────────────────────────────
    def test_matching_wallet_is_left_untouched(self):
        c = self._mk_customer()
        credit_wallet(c.id, "50")                       # balance == head == 50
        _run("--fix")                                   # scans + would fix drift
        self.assertEqual(self._balance(c.id), Decimal("50.00"))

    def test_drift_is_detected_but_not_mutated_in_detect_mode(self):
        from accounts.models import Customer
        c = self._mk_customer()
        credit_wallet(c.id, "100")                      # head == 100
        Customer.objects.filter(pk=c.id).update(wallet_balance=Decimal("80"))  # drift the cache
        out = _run()                                    # detect-only
        self.assertIn("DRIFT", out)
        self.assertIn(f"id={c.id}", out)
        self.assertEqual(self._balance(c.id), Decimal("80.00"))  # NOT changed by detect-only

    def test_drift_is_repaired_by_fix(self):
        from accounts.models import Customer
        c = self._mk_customer()
        credit_wallet(c.id, "100")                      # head == 100
        Customer.objects.filter(pk=c.id).update(wallet_balance=Decimal("80"))
        out = _run("--fix")
        self.assertIn("FIXED", out)
        self.assertEqual(self._balance(c.id), Decimal("100.00"))  # cache := ledger head

    def test_orphan_balance_is_detected_and_never_fixed(self):
        # Non-zero balance with NO ledger row — must NOT be auto-fixed (could be real money).
        c = self._mk_customer(balance="50")
        out = _run("--fix")
        self.assertIn("ORPHAN", out)
        self.assertIn(f"id={c.id}", out)
        self.assertEqual(self._balance(c.id), Decimal("50.00"))   # untouched

    def test_zero_balance_no_ledger_is_ok(self):
        c = self._mk_customer(balance="0")
        out = _run("--fix")
        self.assertNotIn(f"ORPHAN id={c.id}", out)
        self.assertEqual(self._balance(c.id), Decimal("0.00"))

    # ── ledger chain consistency (--deep) ─────────────────────────────────────────
    def test_deep_detects_chain_break_when_head_still_matches(self):
        from accounts.models import WalletTransaction
        c = self._mk_customer()
        credit_wallet(c.id, "100")                      # tx1: amount 100, balance_after 100
        credit_wallet(c.id, "50")                       # tx2: amount 50,  balance_after 150 (head)
        # Tamper the OLDER row's snapshot so the head still equals the cache (150) but the
        # per-row step no longer matches its amount → an internally inconsistent ledger.
        oldest = (WalletTransaction.objects.filter(customer_id=c.id)
                  .order_by("created_at", "id").first())
        WalletTransaction.objects.filter(pk=oldest.pk).update(balance_after=Decimal("90"))
        out = _run("--deep", "--fix")
        self.assertIn("CHAIN", out)
        self.assertIn(f"id={c.id}", out)
        # Head still matches the cache, so no drift repair happened.
        self.assertEqual(self._balance(c.id), Decimal("150.00"))

    def test_deep_ignores_legacy_null_balance_after_prefix(self):
        # An account whose earliest row predates the balance_after field (null) must NOT be
        # falsely flagged CHAIN: the null row resets the anchor, so the first known row after
        # it isn't validated against a zero opening balance. Regression for the --deep review.
        from accounts.models import WalletTransaction
        c = self._mk_customer()
        credit_wallet(c.id, "100")                      # tx1: balance_after 100
        credit_wallet(c.id, "50")                       # tx2: balance_after 150 (head), healthy
        oldest = (WalletTransaction.objects.filter(customer_id=c.id)
                  .order_by("created_at", "id").first())
        WalletTransaction.objects.filter(pk=oldest.pk).update(balance_after=None)  # legacy row
        out = _run("--deep")
        self.assertNotIn(f"CHAIN id={c.id}", out)
        # Head-check still clean (latest non-null balance_after == wallet_balance).
        self.assertNotIn(f"DRIFT id={c.id}", out)


class ReconcileFloatTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        from tenancy.models import Plan, Tenant
        # Stub schema creation (see test_wallet_service.TenantFloatTransferTests): these tests
        # only exercise the public-schema float ledger.
        _p = patch.object(Tenant, "create_schema", lambda self, **kw: None)
        _p.start()
        self.addCleanup(_p.stop)
        suffix = _usuffix()
        self.plan = Plan.objects.create(name="Recon Plan", code=f"recon-float-plan-{suffix}")
        self.tenant = Tenant(schema_name=f"recon_float_{suffix}", name="Recon Resto",
                             slug=f"recon-resto-{suffix}", plan=self.plan,
                             float_balance=Decimal("0"))
        self.tenant.auto_create_schema = False
        self.tenant.save()

    def _float(self):
        from tenancy.models import Tenant
        return Tenant.objects.get(pk=self.tenant.pk).float_balance

    def test_float_drift_is_repaired_by_fix(self):
        from tenancy.models import Tenant
        credit_tenant_float(self.tenant.id, "200")      # head == 200
        Tenant.objects.filter(pk=self.tenant.pk).update(float_balance=Decimal("150"))
        out = _run("--fix")
        self.assertIn("FIXED", out)
        self.assertEqual(self._float(), Decimal("200.00"))
