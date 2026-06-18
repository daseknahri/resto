from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0066_category_station"),
    ]

    operations = [
        migrations.AddField(
            model_name="loyaltyconfig",
            name="tier_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Enable Bronze/Silver/Gold tier progression. Silver and Gold members earn points faster.",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="tier_silver_threshold",
            field=models.PositiveIntegerField(
                default=500,
                help_text="Lifetime points required to reach Silver tier.",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="tier_gold_threshold",
            field=models.PositiveIntegerField(
                default=2000,
                help_text="Lifetime points required to reach Gold tier.",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="tier_silver_multiplier",
            field=models.DecimalField(
                default="1.50",
                max_digits=4,
                decimal_places=2,
                help_text="Points-per-unit multiplier for Silver members (e.g. 1.5 = 50% bonus).",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="tier_gold_multiplier",
            field=models.DecimalField(
                default="2.00",
                max_digits=4,
                decimal_places=2,
                help_text="Points-per-unit multiplier for Gold members (e.g. 2.0 = double points).",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="first_order_bonus_points",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Bonus points awarded on a customer's first order at this restaurant. 0 = disabled.",
            ),
        ),
        migrations.AddField(
            model_name="loyaltyconfig",
            name="birthday_bonus_points",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Bonus points awarded when a customer orders on their birthday. 0 = disabled.",
            ),
        ),
    ]
