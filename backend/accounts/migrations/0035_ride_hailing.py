# Hand-written migration — ride-hailing MVP.
# Depends on 0034_deliveryjob_declined_by_deliveryjob_is_open_pool_and_more

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0034_deliveryjob_declined_by_deliveryjob_is_open_pool_and_more"),
    ]

    operations = [
        # 1. Add driver_vehicle_type to Customer
        migrations.AddField(
            model_name="customer",
            name="driver_vehicle_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("motorbike", "Motorbike"),
                    ("car", "Car"),
                    ("bicycle", "Bicycle"),
                ],
                default="",
                help_text="Structured vehicle type for ride dispatch (motorbike|car|bicycle).",
                max_length=12,
            ),
        ),
        # 2. Add ride-hailing fare fields to PlatformConfig
        migrations.AddField(
            model_name="platformconfig",
            name="ride_base_fare",
            field=models.DecimalField(decimal_places=2, default=Decimal("8.00"), max_digits=8),
        ),
        migrations.AddField(
            model_name="platformconfig",
            name="ride_per_km",
            field=models.DecimalField(decimal_places=2, default=Decimal("3.50"), max_digits=8),
        ),
        migrations.AddField(
            model_name="platformconfig",
            name="ride_minimum_fare",
            field=models.DecimalField(decimal_places=2, default=Decimal("12.00"), max_digits=8),
        ),
        migrations.AddField(
            model_name="platformconfig",
            name="ride_commission_pct",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5),
        ),
        # 3. Create RideRequest
        migrations.CreateModel(
            name="RideRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pickup_lat", models.FloatField()),
                ("pickup_lng", models.FloatField()),
                ("dropoff_lat", models.FloatField()),
                ("dropoff_lng", models.FloatField()),
                ("pickup_address", models.CharField(blank=True, max_length=255)),
                ("dropoff_address", models.CharField(blank=True, max_length=255)),
                ("distance_km", models.FloatField()),
                ("fare", models.DecimalField(decimal_places=2, max_digits=8)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[("wallet", "Wallet"), ("cash", "Cash")],
                        default="wallet",
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("searching", "Searching for driver"),
                            ("accepted", "Driver accepted"),
                            ("arrived", "Driver arrived"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="searching",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("arrived_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "rider_driver_rating",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "driver_rider_rating",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("paid_with_wallet", models.BooleanField(default=False)),
                (
                    "rider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rides",
                        to="accounts.customer",
                    ),
                ),
                (
                    "driver",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"is_driver": True},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="driven_rides",
                        to="accounts.customer",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="riderequest",
            index=models.Index(fields=["status"], name="accounts_ri_status_6ae20e_idx"),
        ),
        migrations.AddIndex(
            model_name="riderequest",
            index=models.Index(fields=["driver", "status"], name="accounts_ri_driver__94b95c_idx"),
        ),
    ]
