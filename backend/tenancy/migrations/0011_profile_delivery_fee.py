from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0010_profile_business_hours_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="delivery_fee",
            field=models.DecimalField(
                max_digits=8,
                decimal_places=2,
                default=0,
                help_text="Fixed delivery fee added to the order total for delivery orders (0 = free delivery).",
            ),
        ),
    ]
