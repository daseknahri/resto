# D G2: COD cash ledger — cash collected by the driver on a delivery handover.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0076_customer_is_suspended'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryjob',
            name='cash_collected',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Cash collected by the driver on a cash-on-delivery handover (0 for prepaid orders). The COD ledger — see _complete_delivered_order.', max_digits=8),
        ),
    ]
