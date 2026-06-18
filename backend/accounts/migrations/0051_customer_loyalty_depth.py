from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0050_customer_phone_digits"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="lifetime_loyalty_points",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Total loyalty points ever earned (never decremented). Used for tier calculation.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="birthday",
            field=models.DateField(
                null=True,
                blank=True,
                help_text="Customer's date of birth (YYYY-MM-DD). Day+month used for annual birthday reward.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="loyalty_birthday_rewarded_year",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                help_text="Year the birthday loyalty bonus was last awarded. Guards against double-credit.",
            ),
        ),
    ]
