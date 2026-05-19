from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_delivery_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryzone",
            name="fee_tiers",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='e.g. [{"km_up_to": 3, "fee": 2.5}, {"km_up_to": null, "fee": 5.0}]',
            ),
        ),
    ]
