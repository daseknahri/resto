from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0019_profile_delivery_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="payment_overdue_since",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Set when subscription payment is overdue. Tenant enters a 7-day grace period; after that the account should be suspended.",
            ),
        ),
    ]
