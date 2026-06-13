"""OPS-4 E: Prune NotificationLog rows older than N days (default 180).

NotificationLog lives in the public schema; it is NOT tenant-scoped, so this
command runs a single DELETE against the shared table — no schema iteration.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import NotificationLog


class Command(BaseCommand):
    help = "Delete NotificationLog rows older than N days (default 180) to prevent unbounded growth."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=180,
            help="Delete rows older than this many days (default: 180).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show count without deleting.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        if days < 1:
            raise CommandError("--days must be >= 1")
        dry_run = bool(options.get("dry_run"))
        cutoff = timezone.now() - timedelta(days=days)
        mode = "DRY-RUN" if dry_run else "DELETE"
        self.stdout.write(
            f"[{mode}] pruning NotificationLog rows older than {days} days "
            f"(before {cutoff.isoformat()})"
        )
        stale_qs = NotificationLog.objects.filter(created_at__lt=cutoff)
        count = stale_qs.count()
        if not dry_run and count:
            stale_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {'Would delete' if dry_run else 'Deleted'} {count} NotificationLog rows."
            )
        )
