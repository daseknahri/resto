"""De-approve drivers whose car documents have expired; warn those expiring soon.

Runs daily via Celery Beat.  Both sweeps operate on the public schema only
because driver records live on the shared Customer model.

Expire sweep:  driver_car_approved=True + (licence_expiry < today OR
               insurance_expiry < today) → set car_approved=False + push.
               Natural idempotency: de-approved drivers leave the filter set.

Warning sweep: driver_car_approved=True + expiry in [today+12, today+14] →
               push warning (no DB state change; 3-day window absorbs a missed
               daily run without resending more than twice).

    python manage.py check_car_doc_expiry
    python manage.py check_car_doc_expiry --dry-run
"""
import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.timezone import now as _now

WARN_WINDOW_MIN = 12  # days before expiry: start of warning window
WARN_WINDOW_MAX = 14  # days before expiry: end of warning window


class Command(BaseCommand):
    help = "De-approve drivers with expired car docs; warn those expiring soon."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without making any changes.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context
        from accounts.models import Customer
        from accounts.push import send_driver_doc_expiry_push_sync

        dry_run = options["dry_run"]
        today = _now().date()
        warn_start = today + datetime.timedelta(days=WARN_WINDOW_MIN)
        warn_end = today + datetime.timedelta(days=WARN_WINDOW_MAX)

        de_approved = 0
        warned = 0

        with schema_context("public"):
            # ── Expire sweep ─────────────────────────────────────────────────
            expired_q = Q(
                driver_licence_expiry__isnull=False,
                driver_licence_expiry__lt=today,
            ) | Q(
                driver_insurance_expiry__isnull=False,
                driver_insurance_expiry__lt=today,
            )
            for driver in Customer.objects.filter(
                is_driver=True, driver_car_approved=True,
            ).filter(expired_q):
                if not dry_run:
                    driver.driver_car_approved = False
                    driver.save(update_fields=["driver_car_approved", "updated_at"])
                    if (
                        driver.driver_licence_expiry
                        and driver.driver_licence_expiry < today
                    ):
                        try:
                            send_driver_doc_expiry_push_sync(driver.id, "licence", -1)
                        except Exception:
                            pass
                    if (
                        driver.driver_insurance_expiry
                        and driver.driver_insurance_expiry < today
                    ):
                        try:
                            send_driver_doc_expiry_push_sync(driver.id, "insurance", -1)
                        except Exception:
                            pass
                de_approved += 1
                self.stdout.write(
                    f"[check_car_doc_expiry] {'(dry) ' if dry_run else ''}de-approved driver {driver.id}"
                )

            # ── Warning sweep ─────────────────────────────────────────────────
            warn_q = Q(
                driver_licence_expiry__isnull=False,
                driver_licence_expiry__range=(warn_start, warn_end),
            ) | Q(
                driver_insurance_expiry__isnull=False,
                driver_insurance_expiry__range=(warn_start, warn_end),
            )
            for driver in Customer.objects.filter(
                is_driver=True, driver_car_approved=True,
            ).filter(warn_q):
                if not dry_run:
                    if (
                        driver.driver_licence_expiry
                        and warn_start <= driver.driver_licence_expiry <= warn_end
                    ):
                        days = (driver.driver_licence_expiry - today).days
                        try:
                            send_driver_doc_expiry_push_sync(driver.id, "licence", days)
                        except Exception:
                            pass
                    if (
                        driver.driver_insurance_expiry
                        and warn_start <= driver.driver_insurance_expiry <= warn_end
                    ):
                        days = (driver.driver_insurance_expiry - today).days
                        try:
                            send_driver_doc_expiry_push_sync(driver.id, "insurance", days)
                        except Exception:
                            pass
                warned += 1
                self.stdout.write(
                    f"[check_car_doc_expiry] {'(dry) ' if dry_run else ''}warned driver {driver.id}"
                )

        self.stdout.write(
            f"[check_car_doc_expiry] done: de_approved={de_approved} warned={warned} dry_run={dry_run}"
        )
