from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0039_alter_riderequest_dispatched_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='riderequest',
            name='delivery_code',
            field=models.CharField(blank=True, default='', max_length=6),
        ),
        migrations.AddField(
            model_name='riderequest',
            name='code_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='riderequest',
            name='code_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
