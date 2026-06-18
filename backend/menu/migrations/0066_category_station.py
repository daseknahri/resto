"""Add optional prep-station field to Category and OrderItem.

Category.station  — owner-assigned name (e.g. 'bar', 'grill', 'cold').
OrderItem.station — snapshot of Category.station at order placement.

Existing rows default to "" (no station / show everywhere), which is the
correct backward-compatible behaviour: kitchen screens without a station
filter continue to see all items unchanged.
"""
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False  # AddIndexConcurrently requires running outside a transaction.

    dependencies = [
        ("menu", "0065_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="station",
            field=models.CharField(
                blank=True,
                default="",
                max_length=40,
                help_text=(
                    "Optional prep station name (e.g. 'bar', 'grill', 'cold'). "
                    "Dishes in this category inherit the station at order placement time so "
                    "the kitchen screen can filter by station. Leave blank to show everywhere."
                ),
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="station",
            field=models.CharField(
                blank=True,
                default="",
                max_length=40,
                help_text="Prep station snapshot from Category.station at order placement.",
            ),
        ),
        # Index on OrderItem.station so the kitchen-screen ?station= filter is fast.
        AddIndexConcurrently(
            model_name="orderitem",
            index=models.Index(
                fields=["station"],
                name="menu_orderitem_station_idx",
            ),
        ),
    ]
