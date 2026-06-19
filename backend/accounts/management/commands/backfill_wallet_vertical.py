"""Backfill ``WalletTransaction.vertical`` for historical rows (P1b).

``WalletTransaction`` lives in the public schema → single-schema scan, no per-tenant
switching. Mirrors the going-forward tagging logic:
  - CASHOUT rows            → ``driver`` (a driver wallet op).
  - other tenant-attributed → the tenant's vertical (food/shops/pharmacy).
  - rows with no tenant_id  → left NULL (global: top-up, P2P transfer, adjustment).

Reporting metadata only — never touches amounts or balances. Idempotent (only fills
NULL ``vertical``). Run after deploying the migration + service change, before any
read path filters by vertical. See KEPOLI_ACCOUNT_ARCHITECTURE.md §7.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill WalletTransaction.vertical for historical rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context
        from accounts.models import WalletTransaction
        from accounts.verticals import vertical_for_business_type, DRIVER
        from tenancy.models import Profile

        dry_run = options["dry_run"]
        total = 0

        with schema_context("public"):
            # 1. CASHOUT rows → driver (regardless of tenant_id).
            cashout_qs = WalletTransaction.objects.filter(
                vertical__isnull=True, type=WalletTransaction.Type.CASHOUT
            )
            n_cash = cashout_qs.count()
            if not dry_run:
                cashout_qs.update(vertical=DRIVER)
            total += n_cash
            self.stdout.write(
                f"CASHOUT -> {DRIVER}: {n_cash} row(s){' (dry)' if dry_run else ''}"
            )

            # 1b. Delivery EARNING (carries tenant_id) → driver. Ride/courier
            #     EARNING has no tenant_id and stays null here (tagged explicitly
            #     going forward).
            earning_qs = WalletTransaction.objects.filter(
                vertical__isnull=True,
                type=WalletTransaction.Type.EARNING,
                tenant_id__isnull=False,
            )
            n_earn = earning_qs.count()
            if not dry_run:
                earning_qs.update(vertical=DRIVER)
            total += n_earn
            self.stdout.write(
                f"EARNING(delivery) -> {DRIVER}: {n_earn} row(s){' (dry)' if dry_run else ''}"
            )

            # 2. Remaining tenant-attributed rows → the tenant's vertical.
            base = WalletTransaction.objects.filter(
                vertical__isnull=True, tenant_id__isnull=False
            ).exclude(type__in=(WalletTransaction.Type.CASHOUT, WalletTransaction.Type.EARNING))
            tenant_ids = list(base.values_list("tenant_id", flat=True).distinct())
            bt_map = (
                dict(
                    Profile.objects.filter(tenant_id__in=tenant_ids).values_list(
                        "tenant_id", "business_type"
                    )
                )
                if tenant_ids
                else {}
            )
            for tid in tenant_ids:
                bt = bt_map.get(tid)
                if not bt:
                    continue  # unresolved tenant → leave NULL (global)
                vertical = vertical_for_business_type(bt)
                qs = base.filter(tenant_id=tid)
                n = qs.count()
                if not dry_run:
                    qs.update(vertical=vertical)
                total += n
                self.stdout.write(
                    f"tenant {tid} -> {vertical}: {n} row(s){' (dry)' if dry_run else ''}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {total} wallet transaction(s)"
                f"{' (dry run, no writes)' if dry_run else ''}."
            )
        )
