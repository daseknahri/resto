from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0003_profile_publish_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="is_menu_temporarily_disabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="is_open",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="menu_disabled_note",
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
