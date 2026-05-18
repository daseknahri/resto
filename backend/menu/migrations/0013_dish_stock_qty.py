from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0012_order_delivery_fee"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="stock_qty",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                default=None,
                help_text=(
                    "Remaining stock count. null = unlimited. When an order is placed, "
                    "the qty is decremented atomically. Reaching 0 automatically sets "
                    "is_available=False so the dish shows as sold-out on the menu."
                ),
            ),
        ),
    ]
