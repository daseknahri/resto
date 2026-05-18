from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_customer_rating"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformFlashSale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("discount_value", models.DecimalField(
                    decimal_places=2, max_digits=5,
                    help_text="Percentage off the food subtotal (e.g. 15.00 = 15%).",
                )),
                ("active_from", models.DateTimeField()),
                ("active_until", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("max_redemptions", models.PositiveIntegerField(
                    blank=True, null=True,
                    help_text="Maximum total redemptions across all opted-in restaurants. Null = unlimited.",
                )),
                ("redemption_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-active_from",),
            },
        ),
        migrations.CreateModel(
            name="PlatformFlashSaleOptIn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("flash_sale", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="opt_ins",
                    to="accounts.platformflashsale",
                )),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("opted_in_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-opted_in_at",),
                "unique_together": {("flash_sale", "tenant_id")},
            },
        ),
    ]
