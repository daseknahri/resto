"""Run 8 D-01: statement rows carry payment state.

Adds CommissionStatementLine.payment_status so a frozen row records whether
the billed order was paid or still-uncollected COD cash at freeze time.
Hand-written to match what `makemigrations` generates for the model change
(the gate's `makemigrations --check` verifies the pair agrees).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0080_default_branch_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="commissionstatementline",
            name="payment_status",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
    ]
