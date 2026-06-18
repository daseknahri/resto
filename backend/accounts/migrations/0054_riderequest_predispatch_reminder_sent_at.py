from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0053_customer_doc_expiry_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="riderequest",
            name="predispatch_reminder_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "Stamped when the ~30-min pre-dispatch reminder is sent to the rider. "
                    "Null = not yet sent. Used to prevent double-sending."
                ),
            ),
        ),
    ]
