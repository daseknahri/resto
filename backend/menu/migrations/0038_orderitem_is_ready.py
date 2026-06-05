from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0037_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='is_ready',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='ready_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
