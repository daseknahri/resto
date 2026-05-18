from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0011_profile_delivery_fee"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="receipt_message",
            field=models.CharField(
                blank=True,
                default="",
                max_length=300,
                help_text="Optional thank-you note shown to the customer on their order confirmation page.",
            ),
            preserve_default=False,
        ),
    ]
