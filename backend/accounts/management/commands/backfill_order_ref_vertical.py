"""Backfill ``CustomerOrderRef.vertical`` from each row's tenant business_type (P1a).

``CustomerOrderRef`` lives in the public schema, so this is a single-schema scan —
no per-tenant schema switching. Idempotent: only fills rows whose ``vertical`` is
blank, batched per tenant. Safe to re-run. Run this AFTER deploying the migration
and signal change, and BEFORE any read path filters by ``vertical``.

See KEPOLI_ACCOUNT_ARCHITECTURE.md §7 (backfill-then-read).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill CustomerOrderRef.vertical from each tenant's business_type."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context
        from accounts.models import CustomerOrderRef
        from accounts.verticals import vertical_for_business_type
        from tenancy.models import Profile

        dry_run = options["dry_run"]
        total = 0

        with schema_context("public"):
            tenant_ids = list(
                CustomerOrderRef.objects.filter(vertical="")
                .values_list("tenant_id", flat=True)
                .distinct()
            )
            if not tenant_ids:
                self.stdout.write("No order refs need backfilling.")
                return

            # One query for the whole business_type map (Profile is public/shared).
            bt_map = dict(
                Profile.objects.filter(tenant_id__in=tenant_ids).values_list(
                    "tenant_id", "business_type"
                )
            )

            for tid in tenant_ids:
                vertical = vertical_for_business_type(bt_map.get(tid))
                qs = CustomerOrderRef.objects.filter(vertical="", tenant_id=tid)
                n = qs.count()
                if not dry_run:
                    qs.update(vertical=vertical)
                total += n
                self.stdout.write(
                    f"tenant {tid} -> {vertical}: {n} row(s)"
                    f"{' (dry)' if dry_run else ''}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {total} order ref(s) across {len(tenant_ids)} tenant(s)"
                f"{' (dry run, no writes)' if dry_run else ''}."
            )
        )
