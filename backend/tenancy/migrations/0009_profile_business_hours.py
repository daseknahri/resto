from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0008_set_basic_plan_max_languages"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="business_hours",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="business_hours_i18n",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
