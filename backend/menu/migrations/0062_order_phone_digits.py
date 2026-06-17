"""
Add customer_phone_digits to Order for btree-indexed phone search.

customer_phone stores the raw phone (e.g. "+212600123456" or "06 00 12 34 56").
icontains on that column is a LIKE '%..%' scan — the existing btree is useless.
This migration:
  1. Adds customer_phone_digits CharField(max_length=9, default="").
  2. Backfills it from existing customer_phone values.
  3. Adds a btree index so exact-match phone searches hit the index.
"""
from django.db import migrations, models


def backfill_phone_digits(apps, schema_editor):
    Order = apps.get_model("menu", "Order")
    batch_size = 1000
    qs = Order.objects.filter(customer_phone__gt="").only("id", "customer_phone")
    updates = []
    for order in qs.iterator(chunk_size=batch_size):
        digits = "".join(c for c in order.customer_phone if c.isdigit())
        order.customer_phone_digits = digits[-9:] if digits else ""
        updates.append(order)
        if len(updates) >= batch_size:
            Order.objects.bulk_update(updates, ["customer_phone_digits"])
            updates = []
    if updates:
        Order.objects.bulk_update(updates, ["customer_phone_digits"])


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0061_orderitem_voided_by_user_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_phone_digits",
            field=models.CharField(
                max_length=9,
                blank=True,
                default="",
                help_text=(
                    "Last 9 digits of customer_phone, stored for btree exact-match search. "
                    "Auto-maintained by the pre_save signal in menu/signals.py."
                ),
            ),
        ),
        migrations.RunPython(backfill_phone_digits, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["customer_phone_digits"],
                name="order_phone_digits_idx",
            ),
        ),
    ]
