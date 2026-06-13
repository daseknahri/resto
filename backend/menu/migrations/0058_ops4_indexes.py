"""OPS-4 C: add performance indexes to the Order model.

  - order_customer_phone_idx : Order.customer_phone — CRM GROUP BY, win-back,
    return-rate, and search all scan by this column (4 paths).
  - order_status_paid_at_idx : (status, paid_at) — Z-report / digest paid_at
    range queries filter on both columns.

These are the only two indexes added in this migration; the WalletTransaction
composite index (tenant_id, type, created_at) is in the accounts app migration
0043 to keep app-level boundaries clean.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0057_orderpayment_idempotency_key"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["customer_phone"],
                name="order_customer_phone_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["status", "paid_at"],
                name="order_status_paid_at_idx",
            ),
        ),
    ]
