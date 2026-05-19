from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0025_promotion_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="points_earned",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Loyalty points credited to the customer for this order. Null = loyalty not active at placement time.",
            ),
        ),
        migrations.CreateModel(
            name="LoyaltyConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False, help_text="Whether the loyalty programme is active for this restaurant.")),
                ("points_per_unit", models.PositiveIntegerField(default=10, help_text="Loyalty points earned per 1 unit of currency spent (e.g. 10 = 10 pts per $1).")),
                ("redeem_threshold", models.PositiveIntegerField(default=100, help_text="Minimum points balance required before a customer can redeem.")),
                ("points_value", models.DecimalField(decimal_places=4, default="0.0100", help_text="Currency value of one loyalty point (e.g. 0.01 = 1 pt is worth $0.01).", max_digits=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Loyalty Config"},
        ),
    ]
