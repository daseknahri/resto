from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0040_riderequest_delivery_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='notify_promotions',
            field=models.BooleanField(
                default=True,
                help_text="Receive occasional offers/announcements from restaurants you've ordered from.",
            ),
        ),
    ]
