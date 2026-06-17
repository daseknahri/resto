from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0047_customertenantoptout"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="perm_void",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Staff can void order items and trigger the resulting partial wallet "
                    "refund. Default True preserves existing behaviour; set False for "
                    "waiters who should handle orders but not reverse them."
                ),
            ),
        ),
    ]
