from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0018_plan_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="delivery_enabled",
            field=models.BooleanField(
                default=True,
                help_text="When False, the delivery fulfillment option is hidden from the customer checkout.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="delivery_minimum_order",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=8,
                help_text="Minimum order total required to unlock the delivery option (0 = no minimum).",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="delivery_zone_description",
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text="Short description of the delivery area shown to customers.",
            ),
        ),
    ]
