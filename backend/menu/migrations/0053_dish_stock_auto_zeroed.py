from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0052_happyhour"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="stock_auto_zeroed",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Set to True when the automatic checkout stock decrement drives stock_qty to 0. "
                    "Cleared when stock becomes positive again (restock/void/cancel) or when the "
                    "owner explicitly writes stock_qty via the Inventory API. "
                    "The 5 AM auto_reset_availability cron only re-enables dishes where this is "
                    "True, avoiding unwanted re-enabling of intentionally zeroed dishes."
                ),
            ),
        ),
    ]
