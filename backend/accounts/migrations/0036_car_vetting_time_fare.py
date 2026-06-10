# Hand-written migration — Phase 2: car-document vetting tier + time-based fare.
# Depends on 0035_ride_hailing

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0035_ride_hailing"),
    ]

    operations = [
        # 1. Customer: driver_licence_url
        migrations.AddField(
            model_name="customer",
            name="driver_licence_url",
            field=models.URLField(blank=True),
        ),
        # 2. Customer: driver_insurance_url
        migrations.AddField(
            model_name="customer",
            name="driver_insurance_url",
            field=models.URLField(blank=True),
        ),
        # 3. Customer: driver_car_approved
        migrations.AddField(
            model_name="customer",
            name="driver_car_approved",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Admin verified licence+insurance; gates RIDE offers only — "
                    "deliveries unaffected."
                ),
            ),
        ),
        # 4. PlatformConfig: ride_per_minute
        migrations.AddField(
            model_name="platformconfig",
            name="ride_per_minute",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=8,
            ),
        ),
    ]
