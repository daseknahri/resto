from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="is_menu_published",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
