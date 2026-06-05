from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0029_profile_cod_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='timezone',
            field=models.CharField(blank=True, help_text="IANA timezone (e.g. 'Africa/Casablanca') used to evaluate the business-hours schedule for auto open/close. Blank falls back to the platform default.", max_length=64),
        ),
    ]
