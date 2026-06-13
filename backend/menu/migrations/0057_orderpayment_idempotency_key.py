"""OPS-3 contract D: add OrderPayment.idempotency_key + conditional unique constraint.

Redis-down backstop: the StaffOrderPaymentView cache short-circuit can be bypassed
when Redis is unavailable.  This DB-level constraint ensures that even if the cache
check is skipped, a replayed POST with the same idempotency_key cannot produce a
second OrderPayment row.  The endpoint catches IntegrityError and returns the
existing row's order payload instead.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0056_order_idempotency_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderpayment",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                help_text="Client-minted key; uniqueness enforced by DB constraint when non-null.",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="orderpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=["idempotency_key"],
                name="uniq_orderpayment_idempotency_key",
            ),
        ),
    ]
