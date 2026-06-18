from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0045_profile_referral_fields")]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="price_monthly",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Monthly subscription price shown on the marketing page. Leave null to display 'Price TBD'.",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="currency",
            field=models.CharField(
                default="MAD",
                help_text="ISO 4217 currency code for price_monthly (e.g. MAD, USD, EUR).",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="billing_period",
            field=models.CharField(
                default="monthly",
                help_text="Billing period shown on the marketing page (e.g. monthly, annually).",
                max_length=20,
            ),
        ),
    ]
