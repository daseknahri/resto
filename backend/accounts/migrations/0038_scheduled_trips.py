# Migration 0038 — Scheduled trips for RideRequest.
#
# Adds:
#   scheduled_for  — rider-requested departure time (null for immediate trips)
#   dispatched_at  — when the trip actually entered the SEARCHING pool
#                    (set at create for immediate; set at release for scheduled;
#                     null on pre-0038 rows — handled by sweep_ride_requests Coalesce fallback)
#   Status.SCHEDULED ("scheduled") — new status before searching in the choices list
#
# Depends on 0037_courier_kind.  No data backfill needed.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0037_courier_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="riderequest",
            name="scheduled_for",
            field=models.DateTimeField(null=True, blank=True, db_index=True),
        ),
        migrations.AddField(
            model_name="riderequest",
            name="dispatched_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="riderequest",
            name="status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("scheduled", "Scheduled"),
                    ("searching", "Searching for driver"),
                    ("accepted", "Driver accepted"),
                    ("arrived", "Driver arrived"),
                    ("in_progress", "In progress"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                default="searching",
                db_index=True,
            ),
        ),
    ]
