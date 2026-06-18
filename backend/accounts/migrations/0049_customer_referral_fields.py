from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0048_user_perm_void"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="referral_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Unique shareable code. Auto-generated; null until the customer "
                    "record is first saved."
                ),
                max_length=12,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="referred_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Customer who referred this one.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="referrals",
                to="accounts.customer",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="referral_reward_given",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Reward already issued for this customer being a referral "
                    "— never re-issue."
                ),
            ),
        ),
    ]
