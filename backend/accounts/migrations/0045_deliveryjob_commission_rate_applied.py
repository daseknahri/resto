from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0044_usertotp_device'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryjob',
            name='delivery_commission_rate_applied',
            field=models.DecimalField(
                default=0,
                decimal_places=4,
                max_digits=7,
                help_text=(
                    "The delivery_commission_pct rate (0-100) that was in effect when "
                    "platform_commission was computed. Snapshotted so audits are not "
                    "affected by later rate changes."
                ),
            ),
        ),
    ]
