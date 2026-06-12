from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0037_profile_auto_reset_availability"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="winback_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Send a single re-engagement push to customers who haven't ordered recently.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="winback_inactive_weeks",
            field=models.PositiveSmallIntegerField(
                default=4,
                help_text="Nudge customers whose most-recent order is older than this many weeks (1–52).",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="winback_message",
            field=models.CharField(
                max_length=200,
                blank=True,
                help_text="Push body text. Leave blank to use the default message.",
            ),
        ),
    ]
