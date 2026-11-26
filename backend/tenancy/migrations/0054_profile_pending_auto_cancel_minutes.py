# Generated for Wave M M-22: Profile.pending_auto_cancel_minutes (0 = OFF).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0053_plan_max_branches'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='pending_auto_cancel_minutes',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Minutes a 'pending' order may wait after being escalated before the "
                    "platform auto-refunds & cancels it. 0 = never auto-cancel (OFF, the "
                    "default). Must exceed pending_sla_minutes to take effect."
                ),
            ),
        ),
    ]
