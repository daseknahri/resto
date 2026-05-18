from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0013_lead_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="tierupgraderequest",
            name="invoice_amount",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                null=True,
                blank=True,
                help_text="Amount paid for this upgrade (set by admin when approving). Used to generate the invoice PDF.",
            ),
        ),
        migrations.AddField(
            model_name="tierupgraderequest",
            name="invoice_currency",
            field=models.CharField(
                max_length=8,
                default="USD",
                blank=True,
                help_text="Currency code for the invoice amount (e.g. USD, EUR, MAD).",
            ),
        ),
    ]
