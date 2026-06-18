from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0063_add_dish_cost_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="tablelink",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("occupied", "Occupied"),
                    ("dirty", "Dirty"),
                    ("reserved", "Reserved"),
                ],
                db_index=True,
                default="open",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="tablelink",
            name="capacity",
            field=models.PositiveSmallIntegerField(
                default=4,
                help_text="Maximum number of covers this table can seat.",
            ),
        ),
    ]
