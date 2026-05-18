from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0018_waitlist_entry"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="wallet_amount_paid",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Amount deducted from the customer's wallet at order placement.",
                max_digits=10,
            ),
        ),
    ]
