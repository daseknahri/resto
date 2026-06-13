from django.db import migrations, models


class Migration(migrations.Migration):
    """Add audit fields to OrderPayment for payment-method correction (OPS-2 contract D).

    Approach: inline correction fields on OrderPayment rather than a separate log
    table. Rationale: a payment row is already the unit of record; adding three
    nullable fields keeps the correction auditable per-payment without a JOIN and
    without changing any existing read paths.

    Fields:
      original_method   -- captured on first correction only; blank means never corrected.
      corrected_at      -- when the correction was applied.
      corrected_by_name -- display name of the staff member who corrected it.

    Boundary: this correction ONLY relabels how a recorded payment was tendered
    (cash vs wallet). It does NOT move money: wallet ledger, wallet_amount_paid,
    and WalletTransaction rows are untouched. The Z-report cash/wallet split reads
    the (possibly corrected) method field so the drawer totals reflect reality.
    """

    dependencies = [
        ("menu", "0054_course_sequencing"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderpayment",
            name="original_method",
            field=models.CharField(
                blank=True,
                help_text="The method value before the first correction. Blank = this payment has never been corrected.",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="orderpayment",
            name="corrected_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When the method was last corrected.",
            ),
        ),
        migrations.AddField(
            model_name="orderpayment",
            name="corrected_by_name",
            field=models.CharField(
                blank=True,
                max_length=80,
                help_text="Display name of the staff member who corrected the method.",
            ),
        ),
    ]
