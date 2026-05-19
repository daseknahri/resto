from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0026_loyaltyconfig_order_points_earned"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tip_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Optional gratuity added by the customer at checkout.",
                max_digits=8,
            ),
        ),
    ]
