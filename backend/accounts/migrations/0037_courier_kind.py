# Hand-written migration — Courier MVP: add kind + package-recipient fields to RideRequest.
# Depends on 0036_car_vetting_time_fare.
#
# Non-breaking: every column has a database-level default so all existing rows
# are left as-is (kind='ride').  The choices= change on kind requires no migration
# by itself, but we capture it here to keep the migration graph complete.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0036_car_vetting_time_fare"),
    ]

    operations = [
        # 1. kind — 'ride' | 'package', default 'ride' (backward-compatible)
        migrations.AddField(
            model_name="riderequest",
            name="kind",
            field=models.CharField(
                max_length=10,
                choices=[("ride", "Ride"), ("package", "Package")],
                default="ride",
                db_index=True,
            ),
        ),
        # 2. recipient_name — package recipient full name (blank for rides)
        migrations.AddField(
            model_name="riderequest",
            name="recipient_name",
            field=models.CharField(max_length=80, blank=True, default=""),
            preserve_default=False,
        ),
        # 3. recipient_phone — package recipient phone (blank for rides; PII-gated)
        migrations.AddField(
            model_name="riderequest",
            name="recipient_phone",
            field=models.CharField(max_length=50, blank=True, default=""),
            preserve_default=False,
        ),
        # 4. package_note — optional free-text instructions (blank for rides)
        migrations.AddField(
            model_name="riderequest",
            name="package_note",
            field=models.CharField(max_length=200, blank=True, default=""),
            preserve_default=False,
        ),
    ]
