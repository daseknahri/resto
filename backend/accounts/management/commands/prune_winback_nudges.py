"""OPS-4 E: Prune WinbackNudge rows older than N days (default 120).

120 days = 90-day dedupe window + 30-day margin.  Older rows can never affect
the deduplication logic but accumulate forever without this cron.

WinbackNudge lives in the public schema — single DELETE, no tenant iteration.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import WinbackNudge


class Command(BaseCommand):
    help = "Delete WinbackNudge rows older than N days (default 120) to prevent unbounded growth."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=120,
            help="Delete rows older than this many days (default: 120).",
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
            f"[{mode}] pruning WinbackNudge rows older than {days} days "
            f"(before {cutoff.isoformat()})"
        )
        stale_qs = WinbackNudge.objects.filter(sent_at__lt=cutoff)
        count = stale_qs.count()
        if not dry_run and count:
            stale_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {'Would delete' if dry_run else 'Deleted'} {count} WinbackNudge rows."
            )
        )
