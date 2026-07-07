"""Backfill driver delivery earnings whose wallet credit failed after DELIVERED.

Driver earnings are credited best-effort AFTER the DELIVERED transaction commits, via
``accounts.views._credit_driver_earnings`` — idempotent on
``idempotency_key = "earning:{job.id}"``. If that credit raises transiently the job stays
DELIVERED, so ``driver_earnings_summary()`` still counts the payout into ``owed`` (it sums
delivered-job payouts, independent of ``wallet_balance``), but the driver's actual
``wallet_balance`` was never incremented — and cash-out (which debits ``wallet_balance``)
then fails with InsufficientFunds while the dashboard shows money owed. Today only a
``payments`` log line records that miss; nothing re-applies it.

This sweep finds DELIVERED jobs (driver set, payout > 0, delivered within ``--days``) whose
``earning:{job.id}`` WalletTransaction is missing and re-runs the (idempotent) credit. It
escalates to the payments logger only after a job has failed reconciliation ``--alert-after``
runs, so a genuinely stuck credit surfaces for manual triage without spamming on a single
transient run.

    python manage.py reconcile_driver_earnings [--days 14] [--limit 500] [--alert-after 3] [--dry-run]

Idempotent and safe to re-run. Deliberately a SEPARATE command from sweep_delivery_jobs
(which runs ~every 60s): a full delivered-jobs scan every minute is wasteful, so schedule
this on a lighter cadence (e.g. every 10-15 min / hourly) via Beat or a Coolify task.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

payments_logger = logging.getLogger("payments")

# Keep a job's consecutive-failure streak long enough to escalate across several runs.
FAIL_COUNTER_TTL = 14 * 24 * 3600


class Command(BaseCommand):
    help = "Backfill driver delivery earnings whose wallet credit failed after DELIVERED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=14,
            help="Only reconcile jobs delivered within the last N days (default 14).",
        )
        parser.add_argument(
            "--limit", type=int, default=500,
            help="Max delivered jobs to scan per run (default 500).",
        )
        parser.add_argument(
            "--alert-after", type=int, default=3,
            help="Escalate to the payments log after a job fails this many reconcile runs (default 3).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be credited without crediting.",
        )

    def handle(self, *args, **options):
        from django.core.cache import cache
        from accounts.models import DeliveryJob, WalletTransaction
        from accounts.views import _credit_driver_earnings

        days = options["days"]
        limit = options["limit"]
        alert_after = options["alert_after"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timedelta(days=days)

        # Candidate DELIVERED jobs that SHOULD carry an earning credit: a real driver and a
        # positive payout, delivered within the lookback window. Newest first so a backlog
        # is worked from the most recently-affected drivers down.
        candidates = list(
            DeliveryJob.objects.filter(
                status=DeliveryJob.Status.DELIVERED,
                driver__isnull=False,
                driver_payout__gt=0,
                delivered_at__gte=cutoff,
            ).order_by("-delivered_at")[:limit]
        )
        if not candidates:
            self.stdout.write("reconcile_driver_earnings: no delivered jobs in window")
            return

        keys = {j.id: f"earning:{j.id}" for j in candidates}
        have = set(
            WalletTransaction.objects.filter(
                idempotency_key__in=list(keys.values())
            ).values_list("idempotency_key", flat=True)
        )
        missing = [j for j in candidates if keys[j.id] not in have]

        if not missing:
            self.stdout.write(
                f"reconcile_driver_earnings: scanned={len(candidates)} all credited"
            )
            return

        if dry_run:
            for j in missing:
                self.stdout.write(
                    f"[dry-run] would credit earning:{j.id} "
                    f"driver={j.driver_id} payout={j.driver_payout} order={j.order_number}"
                )
            self.stdout.write(
                f"reconcile_driver_earnings: scanned={len(candidates)} "
                f"missing={len(missing)} (dry-run, nothing credited)"
            )
            return

        # Re-run the idempotent credit for each missing job. _credit_driver_earnings
        # swallows + logs its own errors, so success is detected by re-querying below
        # rather than by catching here.
        for j in missing:
            _credit_driver_earnings(j)

        now_have = set(
            WalletTransaction.objects.filter(
                idempotency_key__in=[keys[j.id] for j in missing]
            ).values_list("idempotency_key", flat=True)
        )

        credited = 0
        still_failing = 0
        for j in missing:
            fail_key = f"earning_reconcile_fail:{j.id}"
            if keys[j.id] in now_have:
                credited += 1
                cache.delete(fail_key)
                continue
            still_failing += 1
            streak = (cache.get(fail_key) or 0) + 1
            cache.set(fail_key, streak, FAIL_COUNTER_TTL)
            if streak >= alert_after:
                # Persistent failure — escalate to the payments channel for manual triage.
                # NEVER log a cash-out code here; delivery earnings carry only the
                # order_number reference, so this is safe.
                payments_logger.error(
                    "driver earning still uncredited after %s reconcile runs "
                    "job_id=%s driver_id=%s payout=%s order=%s",
                    streak, j.id, j.driver_id, j.driver_payout, j.order_number,
                )

        self.stdout.write(self.style.SUCCESS(
            f"reconcile_driver_earnings: scanned={len(candidates)} missing={len(missing)} "
            f"credited={credited} still_failing={still_failing}"
        ))
