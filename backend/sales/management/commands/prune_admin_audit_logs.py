import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sales.models import AdminAuditLog


def _default_days() -> int:
    raw = (os.getenv("ADMIN_AUDIT_RETENTION_DAYS", "180") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 180
    return value if value > 0 else 180


class Command(BaseCommand):
    help = "Delete admin audit log entries older than retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=_default_days(),
            help="Retention window in days (default from ADMIN_AUDIT_RETENTION_DAYS or 180).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        dry_run = bool(options["dry_run"])
        if days <= 0:
            raise CommandError("--days must be greater than 0")

        cutoff = timezone.now() - timezone.timedelta(days=days)
        scope = AdminAuditLog.objects.filter(created_at__lt=cutoff)
        count = scope.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] admin_audit_logs older than {days} days: {count} (cutoff={cutoff.isoformat()})"
                )
            )
            return

        deleted, _ = scope.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} admin audit log row(s) older than {days} days (cutoff={cutoff.isoformat()})."
            )
        )
