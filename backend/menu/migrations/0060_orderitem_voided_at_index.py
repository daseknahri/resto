from django.db import migrations, models


class Migration(migrations.Migration):
    """Partial index on OrderItem.voided_at WHERE is_voided=True.

    The Z-report aggregates voided items every shift close; without this index
    each query full-scans OrderItem even though voided rows are a small fraction
    of the total.  A partial index covers only the voided rows, keeping it
    tiny and fast to maintain.
    """

    dependencies = [
        ("menu", "0059_order_commission_rate_applied_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="orderitem",
            index=models.Index(
                condition=models.Q(is_voided=True),
                fields=["voided_at"],
                name="menu_orderitem_voided_at_idx",
            ),
        ),
    ]
