"""Send pre-dispatch push reminders to riders whose SCHEDULED trip is ~30 min away.

Runs every 15 min via Celery Beat (same cadence as the food-order equivalent).

Window: `scheduled_for` between now+WINDOW_MIN_MINUTES and now+WINDOW_MAX_MINUTES,
with `predispatch_reminder_sent_at IS NULL` as the idempotency guard.

    python manage.py send_ride_predispatch_reminders
    python manage.py send_ride_predispatch_reminders --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now as _now


WINDOW_MIN_MINUTES = 20
WINDOW_MAX_MINUTES = 40


class Command(BaseCommand):
    help = "Push ~30-min pre-dispatch reminders to riders with upcoming SCHEDULED trips."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending or stamping.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context
        from accounts.models import RideRequest
        from accounts.push import send_ride_predispatch_reminder_sync

        dry_run = options["dry_run"]
        now = _now()
        window_start = now + timedelta(minutes=WINDOW_MIN_MINUTES)
        window_end = now + timedelta(minutes=WINDOW_MAX_MINUTES)
        sent_count = 0

        with schema_context("public"):
            qs = RideRequest.objects.filter(
                status=RideRequest.Status.SCHEDULED,
                scheduled_for__range=(window_start, window_end),
                predispatch_reminder_sent_at__isnull=True,
            ).select_related("rider")

            for ride in qs:
                minutes = int((ride.scheduled_for - now).total_seconds() / 60)
                kind = ride.kind if ride.kind in ("ride", "package") else "ride"

                self.stdout.write(
                    f"[send_ride_predispatch_reminders] "
                    f"{'(dry) ' if dry_run else ''}"
                    f"ride {ride.id} rider {ride.rider_id} kind={kind} in ~{minutes}min"
                )

                if not dry_run:
                    try:
                        send_ride_predispatch_reminder_sync(ride.rider_id, kind, minutes)
                    except Exception:
                        pass
                    # Stamp even on push failure to prevent retrying a broken sub loop.
                    ride.predispatch_reminder_sent_at = now
                    ride.save(update_fields=["predispatch_reminder_sent_at"])
                    sent_count += 1

        self.stdout.write(
            f"[send_ride_predispatch_reminders] done: sent={sent_count} dry_run={dry_run}"
        )
