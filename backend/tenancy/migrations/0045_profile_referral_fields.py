from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0044_profile_closure_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="referral_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Enable the customer referral programme for this tenant.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="referral_reward_points",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text=(
                    "Loyalty points awarded to both the referrer AND the referee when "
                    "the referee completes their first paid order."
                ),
            ),
        ),
    ]
