from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0054_riderequest_predispatch_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerorderref",
            name="vertical",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=16,
                help_text=(
                    "Consumer vertical (food/shops/pharmacy/...) derived from the "
                    "tenant's business_type at index time. Blank until backfilled (P1a)."
                ),
            ),
        ),
    ]
