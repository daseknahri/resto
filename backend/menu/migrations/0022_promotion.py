from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0021_order_source_commission"),
    ]

    operations = [
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(blank=True, max_length=200)),
                (
                    "promo_type",
                    models.CharField(
                        choices=[
                            ("percentage", "Percentage off"),
                            ("fixed", "Fixed amount off"),
                            ("free_delivery", "Free delivery"),
                        ],
                        default="percentage",
                        max_length=20,
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Percentage (0–100) for percentage type; fixed amount for fixed type. Ignored for free_delivery.",
                        max_digits=8,
                    ),
                ),
                (
                    "min_order_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Minimum food subtotal required to apply this promotion.",
                        max_digits=8,
                    ),
                ),
                (
                    "days",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Days active: ['mon','tue',...]. Empty list = every day.",
                    ),
                ),
                (
                    "time_start",
                    models.CharField(
                        blank=True,
                        help_text="HH:MM — start of active time window. Blank = all day.",
                        max_length=5,
                    ),
                ),
                (
                    "time_end",
                    models.CharField(
                        blank=True,
                        help_text="HH:MM — end of active time window. Blank = all day.",
                        max_length=5,
                    ),
                ),
                (
                    "active_from",
                    models.DateField(
                        blank=True,
                        help_text="Start date (inclusive). Null = no start boundary.",
                        null=True,
                    ),
                ),
                (
                    "active_until",
                    models.DateField(
                        blank=True,
                        help_text="End date (inclusive). Null = no end boundary.",
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "max_uses",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Maximum number of orders this promotion applies to. Null = unlimited.",
                        null=True,
                    ),
                ),
                ("use_count", models.PositiveIntegerField(default=0)),
                (
                    "is_platform_flash",
                    models.BooleanField(
                        default=False,
                        help_text="True if created by the platform as a flash sale campaign.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
