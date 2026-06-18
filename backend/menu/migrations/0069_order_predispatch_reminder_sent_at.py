from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0068_ingredient_and_recipe_line"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="predispatch_reminder_sent_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "Stamped when the ~60-min pre-dispatch push reminder is sent to the customer. "
                    "Null = not yet sent. Used to prevent double-sending."
                ),
            ),
        ),
    ]
