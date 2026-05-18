from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0011_dish_is_available"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_fee",
            field=models.DecimalField(
                max_digits=8,
                decimal_places=2,
                default=0,
                help_text="Delivery fee captured at order time (snapshot from Profile.delivery_fee).",
            ),
        ),
    ]
