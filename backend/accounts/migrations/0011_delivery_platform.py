from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_platform_flash_sale"),
    ]

    operations = [
        # ── Customer driver fields ──────────────────────────────────────────────
        migrations.AddField(
            model_name="customer",
            name="is_driver",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="is_driver_online",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customer",
            name="driver_lat",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="driver_lng",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="driver_position_updated_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        # ── DeliveryZone ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="DeliveryZone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, help_text="e.g. 'Paris 1–4 Arrondissements'")),
                ("city", models.CharField(max_length=100, db_index=True)),
                ("polygon", models.JSONField(default=list, help_text="List of {lat, lng} objects forming the zone boundary.")),
                ("center_lat", models.FloatField(null=True, blank=True)),
                ("center_lng", models.FloatField(null=True, blank=True)),
                ("approx_radius_km", models.FloatField(default=5.0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("city", "name"),
            },
        ),
        # ── DeliveryJob ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="DeliveryJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("order_number", models.CharField(max_length=20, db_index=True)),
                ("driver", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="delivery_jobs",
                    to="accounts.customer",
                    limit_choices_to={"is_driver": True},
                )),
                ("status", models.CharField(
                    choices=[
                        ("searching", "Searching for driver"),
                        ("assigned", "Driver assigned"),
                        ("at_restaurant", "At restaurant"),
                        ("picked_up", "Picked up"),
                        ("delivered", "Delivered"),
                        ("failed", "Failed"),
                    ],
                    default="searching",
                    max_length=20,
                    db_index=True,
                )),
                ("pickup_address", models.CharField(max_length=200, blank=True)),
                ("pickup_lat", models.FloatField(null=True, blank=True)),
                ("pickup_lng", models.FloatField(null=True, blank=True)),
                ("delivery_address", models.CharField(max_length=200, blank=True)),
                ("delivery_lat", models.FloatField(null=True, blank=True)),
                ("delivery_lng", models.FloatField(null=True, blank=True)),
                ("delivery_fee", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("driver_payout", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("zone", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="jobs",
                    to="accounts.deliveryzone",
                )),
                ("assigned_at", models.DateTimeField(null=True, blank=True)),
                ("picked_up_at", models.DateTimeField(null=True, blank=True)),
                ("delivered_at", models.DateTimeField(null=True, blank=True)),
                ("failed_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer_driver_rating", models.PositiveSmallIntegerField(null=True, blank=True)),
                ("customer_driver_note", models.CharField(max_length=200, blank=True)),
                ("driver_customer_rating", models.PositiveSmallIntegerField(null=True, blank=True)),
                ("driver_customer_note", models.CharField(max_length=200, blank=True)),
                ("restaurant_driver_rating", models.PositiveSmallIntegerField(null=True, blank=True)),
                ("restaurant_driver_note", models.CharField(max_length=200, blank=True)),
            ],
            options={
                "ordering": ("-created_at",),
                "unique_together": {("tenant_id", "order_number")},
            },
        ),
    ]
