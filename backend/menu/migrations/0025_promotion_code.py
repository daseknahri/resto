from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0024_push_subscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="promotion",
            name="code",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text=(
                    "Optional customer-redeemable code (e.g. WELCOME10). "
                    "When set, the promotion is NOT applied automatically — the customer must enter it at checkout. "
                    "Leave blank for auto-applied promotions."
                ),
                max_length=20,
            ),
            preserve_default=False,
        ),
    ]
