from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0036_pharmacy_business_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="auto_reset_availability",
            field=models.BooleanField(
                default=False,
                help_text="Automatically re-enable all sold-out dishes at ~05:00 local time each day.",
            ),
        ),
    ]
