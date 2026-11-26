# Generated for Wave M M-09: at most one PENDING cash-out request per code.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0078_customer_topup_attempt'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='drivercashoutrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='pending'),
                fields=('code',),
                name='uniq_pending_cashout_code',
            ),
        ),
    ]
