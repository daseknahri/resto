# R6-26: new Profiles default to Africa/Casablanca.
#
# The platform's restaurants are Moroccan; a blank timezone made business-hours
# auto open/close, service-day cutover, the 05:00 availability reset, the daily
# summary's "yesterday" and dashboard day buckets all run on UTC — one hour off
# local time most of the year. The model default covers every Profile creation
# path (lead provisioning, get_or_create on the profile endpoint, admin) with
# no per-site default. AlterField does not backfill: existing blank rows keep
# "" and the UTC fallback until the owner sets a timezone (the OwnerProfile
# brand tab already has the control — StepBrand loads + saves it).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0054_profile_pending_auto_cancel_minutes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='timezone',
            field=models.CharField(
                blank=True,
                default='Africa/Casablanca',
                help_text=(
                    "IANA timezone (e.g. 'Africa/Casablanca') used to evaluate the business-hours "
                    "schedule for auto open/close. New profiles default to Africa/Casablanca; "
                    "blank falls back to the platform default (UTC)."
                ),
                max_length=64,
            ),
        ),
    ]
