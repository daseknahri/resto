# R6-06: arrival timestamp for the (c2) pickup-SLA split.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0079_drivercashoutrequest_pending_code_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryjob',
            name='at_restaurant_at',
            field=models.DateTimeField(blank=True, help_text='When the driver arrived at the restaurant (ASSIGNED → AT_RESTAURANT). The (c2) pickup-SLA wait is measured from here; null on legacy rows, which fall back to the assignment clock.', null=True),
        ),
    ]
