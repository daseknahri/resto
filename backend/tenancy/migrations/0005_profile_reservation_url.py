from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0004_profile_open_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="reservation_url",
            field=models.URLField(blank=True),
        ),
    ]
