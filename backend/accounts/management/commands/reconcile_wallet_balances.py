"""Assert the money invariant `denormalized balance == ledger head` and alert on drift.

RISK MONEY-1. Both money ledgers keep a *denormalized* running balance that the app spends
against — ``Customer.wallet_balance`` and ``Tenant.float_balance`` — alongside an append-only
journal (``WalletTransaction`` / ``TenantFloatTransaction``) whose every row snapshots the
resulting balance in ``balance_after``. Nothing, until now, checked that the two agree. A single
stray write, or a crash between the ledger insert and the balance update, produces **silent,
permanent balance drift that nothing detects**.

This command reconciles both ledgers and reports/alerts on any mismatch. The check is
**sign-agnostic**: because ``amount`` is only a positive magnitude and direction lives in
``type`` (and ``adjustment`` can go either way), we do NOT sum signed amounts. Instead we compare
the denormalized balance to the ``balance_after`` of the account's most recent ledger row — the
value the ledger itself recorded as the true resulting balance. Legacy rows with a null
``balance_after`` (pre-dating the field) are skipped so they can't cause false positives.

Categories:
  • OK       — balance == latest balance_after (or both zero / no ledger).
  • DRIFT    — has a ledger head, but balance != head. Fixable (the append-only ledger is the
               source of truth, so the safe repair is balance := head).
  • ORPHAN   — non-zero balance but NO ledger row at all. NEVER auto-fixed (could be real money
               from a path that skipped the journal — needs a human).
  • CHAIN    — (``--deep`` only) a row whose |balance_after step| != its amount, i.e. the ledger
               is internally inconsistent. Never auto-fixed — needs forensics.

    python manage.py reconcile_wallet_balances [--limit 0] [--fix] [--deep]
                                               [--alert-after 2] [--dry-run]

Default mode is **read-only detect + alert** — safe to schedule on Beat (it never mutates money).
``--fix`` repairs only the unambiguous DRIFT case, under the same ``select_for_update`` row lock
the wallet service uses, re-checking the mismatch under the lock so it can't clobber a concurrent
legitimate mutation. It never touches ORPHAN or CHAIN accounts.

Money-safety: this never logs a wallet ``reference`` (a driver cash-out reference carries the live
6-digit bearer cash-out code). The ``payments`` channel gets ids + the discrepancy magnitude only;
full figures go to stdout for the operator running the command.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery

payments_logger = logging.getLogger("payments")

_CENT = Decimal("0.01")
# Persist a mismatched account's consecutive-run streak long enough to escalate across
# several detect-only runs (a real drift persists until repaired).
FAIL_COUNTER_TTL = 14 * 24 * 3600


def _money(value) -> Decimal:
    """Coerce to a 2dp Decimal; treat anything unparseable/None as 0 (never raises)."""
    try:
        return Decimal(str(value if value is not None else 0)).quantize(_CENT)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


class Command(BaseCommand):
    help = "Assert denormalized wallet/float balances match their ledger head; alert on drift (MONEY-1)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Max accounts to scan per ledger (0 = all, the default for a full assertion). "
                 "If >0 and there are more accounts, the run warns rather than silently truncating.",
        )
        parser.add_argument(
            "--fix", action="store_true",
            help="Repair the unambiguous DRIFT case (balance := ledger head) under a row lock. "
                 "Never touches ORPHAN/CHAIN accounts. Off by default.",
        )
        parser.add_argument(
            "--deep", action="store_true",
            help="Also run the ledger chain-consistency check (|balance_after step| == amount). "
                 "More expensive; catches an internally inconsistent ledger.",
        )
        parser.add_argument(
            "--alert-after", type=int, default=2,
            help="Escalate a still-mismatched account to the payments error log after this many "
                 "consecutive runs (default 2).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="With --fix, report what would be repaired without writing.",
        )

    # ── entry point ─────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        self.limit = options["limit"]
        self.do_fix = options["fix"]
        self.deep = options["deep"]
        self.alert_after = options["alert_after"]
        self.dry_run = options["dry_run"]

        wallet = self._reconcile_customers()
        floats = self._reconcile_floats()

        summary = (
            f"reconcile_wallet_balances: "
            f"wallets[scanned={wallet['scanned']} ok={wallet['ok']} drift={wallet['drift']} "
            f"orphan={wallet['orphan']} chain={wallet['chain']} fixed={wallet['fixed']}] "
            f"floats[scanned={floats['scanned']} ok={floats['ok']} drift={floats['drift']} "
            f"orphan={floats['orphan']} chain={floats['chain']} fixed={floats['fixed']}]"
        )
        total_bad = (wallet["drift"] + wallet["orphan"] + wallet["chain"]
                     + floats["drift"] + floats["orphan"] + floats["chain"])
        if total_bad and not (self.do_fix and not self.dry_run):
            # A single run-level warning on the money channel so ops always sees "drift exists"
            # even in detect-only mode; per-account escalation happens below at the streak.
            payments_logger.warning(
                "wallet/float reconciliation found %s unreconciled account(s) "
                "(wallets: drift=%s orphan=%s chain=%s; floats: drift=%s orphan=%s chain=%s)",
                total_bad, wallet["drift"], wallet["orphan"], wallet["chain"],
                floats["drift"], floats["orphan"], floats["chain"],
            )
        self.stdout.write(self.style.SUCCESS(summary) if total_bad == 0 else summary)

    # ── customer wallets ────────────────────────────────────────────────────────
    def _reconcile_customers(self):
        from accounts.models import Customer, WalletTransaction

        head_sq = (
            WalletTransaction.objects
            .filter(customer_id=OuterRef("pk"), balance_after__isnull=False)
            .order_by("-created_at", "-id")
            .values("balance_after")[:1]
        )
        rows = (
            Customer.objects
            .annotate(head_ba=Subquery(
                head_sq, output_field=DecimalField(max_digits=12, decimal_places=2)))
            .values("id", "wallet_balance", "head_ba")
            .order_by("-id")
        )
        total = Customer.objects.count()
        return self._reconcile(
            label="wallet",
            rows=rows,
            total=total,
            balance_key="wallet_balance",
            fail_prefix="wallet_reconcile_fail",
            fix_fn=self._fix_customer,
            deep_fn=(self._deep_customer if self.deep else None),
        )

    def _fix_customer(self, account_id, head_ba):
        """Repair a customer's drifted wallet_balance to the ledger head, under a row lock."""
        from accounts.models import Customer, WalletTransaction

        with transaction.atomic():
            cust = Customer.objects.select_for_update().get(pk=account_id)
            head = (
                WalletTransaction.objects
                .filter(customer_id=account_id, balance_after__isnull=False)
                .order_by("-created_at", "-id")
                .values_list("balance_after", flat=True)
                .first()
            )
            if head is None:
                return None  # became an orphan under the lock — do not touch
            if _money(cust.wallet_balance) == _money(head):
                return None  # a concurrent legit mutation already reconciled it
            old = _money(cust.wallet_balance)
            cust.wallet_balance = _money(head)
            cust.save(update_fields=["wallet_balance", "updated_at"])
            return old, _money(head)

    def _deep_customer(self, account_id):
        from accounts.models import WalletTransaction
        # Fetch ALL rows (incl. legacy null-balance_after) so the chain walk can treat a
        # null row as an anchor-reset instead of mis-starting from zero (see _chain_breaks).
        rows = list(
            WalletTransaction.objects
            .filter(customer_id=account_id)
            .order_by("created_at", "id")
            .values_list("id", "amount", "balance_after")
        )
        return self._chain_breaks(rows)

    # ── tenant float ─────────────────────────────────────────────────────────────
    def _reconcile_floats(self):
        from accounts.models import TenantFloatTransaction
        from tenancy.models import Tenant

        head_sq = (
            TenantFloatTransaction.objects
            .filter(tenant_id=OuterRef("pk"), balance_after__isnull=False)
            .order_by("-created_at", "-id")
            .values("balance_after")[:1]
        )
        rows = (
            Tenant.objects
            .annotate(head_ba=Subquery(
                head_sq, output_field=DecimalField(max_digits=12, decimal_places=2)))
            .values("id", "float_balance", "head_ba")
            .order_by("-id")
        )
        total = Tenant.objects.count()
        return self._reconcile(
            label="float",
            rows=rows,
            total=total,
            balance_key="float_balance",
            fail_prefix="float_reconcile_fail",
            fix_fn=self._fix_float,
            deep_fn=(self._deep_float if self.deep else None),
        )

    def _fix_float(self, account_id, head_ba):
        from accounts.models import TenantFloatTransaction
        from tenancy.models import Tenant

        with transaction.atomic():
            tenant = Tenant.objects.select_for_update().get(pk=account_id)
            head = (
                TenantFloatTransaction.objects
                .filter(tenant_id=account_id, balance_after__isnull=False)
                .order_by("-created_at", "-id")
                .values_list("balance_after", flat=True)
                .first()
            )
            if head is None:
                return None
            if _money(tenant.float_balance) == _money(head):
                return None
            old = _money(tenant.float_balance)
            tenant.float_balance = _money(head)
            tenant.save(update_fields=["float_balance"])
            return old, _money(head)

    def _deep_float(self, account_id):
        from accounts.models import TenantFloatTransaction
        rows = list(
            TenantFloatTransaction.objects
            .filter(tenant_id=account_id)
            .order_by("created_at", "id")
            .values_list("id", "amount", "balance_after")
        )
        return self._chain_breaks(rows)

    # ── shared reconciliation core ────────────────────────────────────────────────
    def _chain_breaks(self, rows):
        """Return the tx ids where |balance_after - prev_balance_after| != amount.

        Walks the FULL ordered ledger (oldest first). A legacy row with a null
        balance_after (pre-dating the field) carries no known running balance, so it
        RESETS the anchor: the first known-balance row after such a gap is accepted as the
        new anchor and its own step is not validated — the opening balance it would need
        lives on the skipped legacy rows, so asserting it against zero would be a false
        positive. For an all-known ledger the walk starts from a zero opening balance, so
        the first row must equal its own amount (the ledger can never open with a debit).
        """
        breaks = []
        prev = Decimal("0.00")
        prev_known = True
        for tx_id, amount, ba in rows:
            if ba is None:
                prev_known = False   # legacy gap — can't validate the next step across it
                continue
            ba = _money(ba)
            if prev_known and abs(ba - prev) != _money(amount):
                breaks.append(tx_id)
            prev = ba
            prev_known = True
        return breaks

    def _reconcile(self, *, label, rows, total, balance_key, fail_prefix, fix_fn, deep_fn):
        from django.core.cache import cache

        counts = {"scanned": 0, "ok": 0, "drift": 0, "orphan": 0, "chain": 0, "fixed": 0}

        if self.limit and total > self.limit:
            self.stdout.write(self.style.WARNING(
                f"[{label}] scanning newest {self.limit} of {total} accounts; "
                f"{total - self.limit} older account(s) NOT scanned this run (raise --limit)."
            ))
        iterator = rows[: self.limit] if self.limit else rows.iterator()

        for row in iterator:
            counts["scanned"] += 1
            account_id = row["id"]
            balance = _money(row[balance_key])
            head_ba = row["head_ba"]
            fail_key = f"{fail_prefix}:{account_id}"

            # Classify.
            if head_ba is None:
                if balance == 0:
                    counts["ok"] += 1
                    cache.delete(fail_key)
                    self._maybe_deep(deep_fn, account_id, counts, label)
                    continue
                category = "ORPHAN"
            elif balance == _money(head_ba):
                counts["ok"] += 1
                cache.delete(fail_key)
                self._maybe_deep(deep_fn, account_id, counts, label)
                continue
            else:
                category = "DRIFT"

            delta = balance - (Decimal("0.00") if head_ba is None else _money(head_ba))

            if category == "DRIFT":
                counts["drift"] += 1
                if self.do_fix and not self.dry_run:
                    fixed = fix_fn(account_id, head_ba)
                    if fixed is not None:
                        old, new = fixed
                        counts["fixed"] += 1
                        cache.delete(fail_key)
                        self.stdout.write(
                            f"[{label}] FIXED id={account_id} {old} -> {new}"
                        )
                        payments_logger.warning(
                            "%s balance drift repaired id=%s delta=%s", label, account_id, delta
                        )
                        # Still run the deep check on a fixed account to surface chain issues.
                        self._maybe_deep(deep_fn, account_id, counts, label)
                        continue
                    # Reconciled concurrently or became orphan — re-scan next run.
                    self.stdout.write(f"[{label}] id={account_id} drift resolved under lock")
                    continue
                verb = "would fix" if (self.do_fix and self.dry_run) else "DRIFT"
                self.stdout.write(
                    f"[{label}] {verb} id={account_id} balance={balance} head={_money(head_ba)} delta={delta}"
                )
            else:  # ORPHAN
                counts["orphan"] += 1
                self.stdout.write(self.style.WARNING(
                    f"[{label}] ORPHAN id={account_id} balance={balance} but NO ledger row "
                    f"(never auto-fixed — manual review)"
                ))

            # Escalation streak (both DRIFT-not-fixed and ORPHAN).
            streak = (cache.get(fail_key) or 0) + 1
            cache.set(fail_key, streak, FAIL_COUNTER_TTL)
            if streak >= self.alert_after:
                payments_logger.error(
                    "%s balance %s unreconciled after %s runs id=%s delta=%s",
                    label, category, streak, account_id, delta,
                )
            self._maybe_deep(deep_fn, account_id, counts, label)

        return counts

    def _maybe_deep(self, deep_fn, account_id, counts, label):
        if deep_fn is None:
            return
        breaks = deep_fn(account_id)
        if breaks:
            counts["chain"] += 1
            self.stdout.write(self.style.WARNING(
                f"[{label}] CHAIN id={account_id} inconsistent ledger at tx {breaks} "
                f"(never auto-fixed — forensics)"
            ))
            payments_logger.error(
                "%s ledger chain-inconsistent id=%s tx_count=%s", label, account_id, len(breaks)
            )
