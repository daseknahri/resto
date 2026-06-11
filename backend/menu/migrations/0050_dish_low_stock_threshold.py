from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0049_campaign"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="low_stock_threshold",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    "Stock level at or below which this dish appears in the low-stock alert list. "
                    "Defaults to 3. Ignored when stock_qty is null (unlimited)."
                ),
            ),
        ),
    ]
