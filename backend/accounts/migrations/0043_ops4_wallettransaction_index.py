"""OPS-4 C: add a composite index to WalletTransaction.

  wallettx_tenant_type_created_idx : (tenant_id, type, created_at)

Covers the refund aggregate query used in OPS-2 (cancel-refund EXISTS check)
and the OPS-3 financial statement (filter type=REFUND, tenant_id, created_at
range).  WalletTransaction is in the shared public schema (accounts app).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0042_winbacknudge"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(
                fields=["tenant_id", "type", "created_at"],
                name="wallettx_tid_type_cat_idx",
            ),
        ),
    ]
