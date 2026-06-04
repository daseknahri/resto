from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0025_customerpushsubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='driver_approved',
            field=models.BooleanField(default=False, help_text='A platform admin has vetted and approved this driver. Only approved drivers can go online or accept jobs.'),
        ),
        migrations.AddField(
            model_name='customer',
            name='driver_vehicle',
            field=models.CharField(blank=True, help_text="Driver's vehicle, supplied at application (e.g. 'Motorbike — 1234-AB').", max_length=120),
        ),
    ]
