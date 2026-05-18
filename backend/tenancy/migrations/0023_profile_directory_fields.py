from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0022_profile_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="directory_opt_in",
            field=models.BooleanField(
                default=False,
                help_text="Show this restaurant in the platform's public directory. Off by default.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="cuisine_type",
            field=models.CharField(
                blank=True,
                max_length=60,
                help_text="Cuisine category shown in the directory (e.g. Italian, Moroccan, Japanese).",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="city",
            field=models.CharField(
                blank=True,
                max_length=80,
                help_text="City shown in the directory.",
            ),
        ),
    ]
