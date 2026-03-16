from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0009_profile_business_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="business_hours_schedule",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
