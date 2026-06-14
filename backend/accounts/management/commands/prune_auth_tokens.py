"""OPS-5c item 4: Prune PasswordResetToken + ActivationToken rows that are
both consumed/expired AND older than N days (default 30).

These tables accumulate forever because tokens are never cleaned up after use
or expiry.  A week's-worth of slack (default 30 days) is kept to preserve
forensic evidence of recent auth events.

Both models live in the public schema; no schema iteration is needed.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Delete consumed/expired PasswordResetToken and ActivationToken rows "
        "older than N days (default 30) to prevent unbounded growth."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30,
            help="Delete rows older than this many days (default: 30).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show counts without deleting.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        if days < 1:
            raise CommandError("--days must be >= 1")
        dry_run = bool(options.get("dry_run"))
        cutoff = timezone.now() - timedelta(days=days)
        mode = "DRY-RUN" if dry_run else "DELETE"
        self.stdout.write(
            f"[{mode}] pruning auth tokens older than {days} days "
            f"(before {cutoff.isoformat()})"
        )

        now = timezone.now()
        # Older than cutoff AND (consumed OR expired).  A single Q filter avoids
        # the `qs | qs` UNION (which double-counts a token that is both used and
        # expired) so the reported counts below are accurate.
        stale = Q(used_at__isnull=False) | Q(expires_at__lt=now)

        from accounts.models import PasswordResetToken
        reset_qs = PasswordResetToken.objects.filter(created_at__lt=cutoff).filter(stale)
        reset_count = reset_qs.count()
        if not dry_run and reset_count:
            reset_qs.delete()

        from sales.models import ActivationToken
        activation_qs = ActivationToken.objects.filter(created_at__lt=cutoff).filter(stale)
        activation_count = activation_qs.count()
        if not dry_run and activation_count:
            activation_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {'Would delete' if dry_run else 'Deleted'} "
                f"{reset_count} PasswordResetToken + {activation_count} ActivationToken rows."
            )
        )
