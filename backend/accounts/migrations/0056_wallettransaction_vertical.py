from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0055_customerorderref_vertical"),
    ]

    operations = [
        migrations.AddField(
            model_name="wallettransaction",
            name="vertical",
            field=models.CharField(
                blank=True,
                db_index=True,
                null=True,
                max_length=16,
                help_text=(
                    "Consumer vertical this money movement belongs to (reporting "
                    "only; the balance stays one global pool). Null for global rows (P1b)."
                ),
            ),
        ),
    ]
