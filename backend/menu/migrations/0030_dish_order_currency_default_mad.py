"""
Change the default currency on Dish and Order from "USD" to "MAD",
and backfill all existing rows that still have the old "USD" default.

Safe to run: UPDATE WHERE currency = 'USD' will not touch any row that was
intentionally set to a non-USD value.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0029_currencyrate"),
    ]

    operations = [
        # 1. Change the column default (affects new rows only)
        migrations.AlterField(
            model_name="dish",
            name="currency",
            field=models.CharField(default="MAD", max_length=8),
        ),
        migrations.AlterField(
            model_name="order",
            name="currency",
            field=models.CharField(default="MAD", max_length=8),
        ),
        # 2. Backfill: rows with the old "USD" placeholder → "MAD"
        migrations.RunSQL(
            sql="UPDATE menu_dish  SET currency = 'MAD' WHERE currency = 'USD';",
            reverse_sql="UPDATE menu_dish  SET currency = 'USD' WHERE currency = 'MAD';",
        ),
        migrations.RunSQL(
            sql="UPDATE menu_order SET currency = 'MAD' WHERE currency = 'USD';",
            reverse_sql="UPDATE menu_order SET currency = 'USD' WHERE currency = 'MAD';",
        ),
    ]
