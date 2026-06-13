"""OPS-3 contract A: add Order.idempotency_key + conditional unique constraint.

The field is nullable so all existing rows (no key) are unconstrained.
The conditional UniqueConstraint ensures that when a key IS supplied it cannot
appear on two orders within the same tenant schema, making retry-safe dedup safe.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0055_orderpayment_correction"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Client-minted UUIDv4 sent at placement time; used for retry-safe dedup.",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=["idempotency_key"],
                name="uniq_order_idempotency_key",
            ),
        ),
    ]
