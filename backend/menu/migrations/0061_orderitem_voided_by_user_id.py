from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0060_orderitem_voided_at_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="voided_by_user_id",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
