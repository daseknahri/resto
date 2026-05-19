from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_deliveryzone_fee_tiers"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="loyalty_points",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Accumulated loyalty points, redeemable for wallet credits at each restaurant.",
            ),
        ),
    ]
