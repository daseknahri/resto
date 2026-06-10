from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0035_profile_daily_revenue_goal"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="business_type",
            field=models.CharField(
                choices=[
                    ("restaurant", "Restaurant"),
                    ("cafe", "Café"),
                    ("bakery", "Bakery"),
                    ("grocery", "Grocery"),
                    ("retail", "Retail / Shop"),
                    ("pharmacy", "Pharmacy / Parapharmacie"),
                ],
                default="restaurant",
                help_text=(
                    "Vertical this tenant operates in. Gates restaurant-only features "
                    "(tables, dine-in, waiter, kitchen, reservations) for non-restaurant types."
                ),
                max_length=20,
            ),
        ),
    ]
