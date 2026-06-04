from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0028_profile_platform_delivery_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='cod_enabled',
            field=models.BooleanField(default=False, help_text='Allow trusted repeat customers to pay cash on handover for pickup/delivery instead of prepaying from their wallet.'),
        ),
        migrations.AddField(
            model_name='profile',
            name='cod_min_paid_orders',
            field=models.PositiveSmallIntegerField(default=3, help_text='Number of completed & paid orders a customer must have before cash-on-handover is offered to them.'),
        ),
    ]
