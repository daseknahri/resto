from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0021_tenant_deletion_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="max_covers_per_slot",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Maximum number of covers (guests) per time slot. 0 = unlimited — capacity management disabled.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="slot_duration_minutes",
            field=models.PositiveSmallIntegerField(
                default=60,
                choices=[(30, "30 minutes"), (60, "1 hour"), (90, "1.5 hours"), (120, "2 hours")],
                help_text="Duration of each reservation time slot in minutes. Used when max_covers_per_slot > 0.",
            ),
        ),
    ]
