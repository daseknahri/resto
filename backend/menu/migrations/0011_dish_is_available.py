from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0010_order_customer_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="is_available",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Temporary daily availability. False = sold out (visible on menu "
                    "but cannot be ordered). Use is_published=False to permanently remove "
                    "from the menu."
                ),
            ),
        ),
    ]
