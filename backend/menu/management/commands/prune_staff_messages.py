"""OPS-4 E: Prune StaffMessage rows older than N days (default 90) per tenant.

StaffMessage lives in each tenant schema. This command mirrors the pattern
from prune_analytics_events: iterate tenants, switch schema, delete stale rows.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_tenants.utils import schema_context

from menu.models import StaffMessage
from tenancy.models import Tenant


class Command(BaseCommand):
    help = "Delete StaffMessage rows older than N days (default 90) per tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=90,
            help="Delete messages older than this many days (default: 90).",
        )
        parser.add_argument(
            "--tenant", type=str, default="",
            help="Optional tenant slug to prune a single tenant.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show counts without deleting rows.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        if days < 1:
            raise CommandError("--days must be >= 1")

        tenant_slug = (options.get("tenant") or "").strip()
        dry_run = bool(options.get("dry_run"))
        cutoff = timezone.now() - timedelta(days=days)

        if tenant_slug:
            tenants = list(Tenant.objects.filter(slug=tenant_slug))
        else:
            tenants = list(Tenant.objects.all())
        if not tenants:
            raise CommandError(
                f"No tenant found for slug '{tenant_slug}'." if tenant_slug else "No tenants found."
            )

        mode = "DRY-RUN" if dry_run else "DELETE"
        self.stdout.write(
            f"[{mode}] pruning StaffMessage rows older than {days} days "
            f"(before {cutoff.isoformat()})"
        )

        total = 0
        for tenant in tenants:
            with schema_context(tenant.schema_name):
                stale_qs = StaffMessage.objects.filter(created_at__lt=cutoff)
                count = stale_qs.count()
                if not dry_run and count:
                    stale_qs.delete()
                total += count
                self.stdout.write(f"- {tenant.slug}: {count} stale messages")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {'Would delete' if dry_run else 'Deleted'} {total} StaffMessage rows."
            )
        )
