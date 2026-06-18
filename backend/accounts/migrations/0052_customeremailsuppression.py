from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0051_customer_loyalty_depth"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerEmailSuppression",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, unique=True, help_text="The suppressed email address (lower-cased by save).")),
                ("reason", models.CharField(
                    max_length=20,
                    choices=[("bounce", "Hard bounce"), ("complaint", "Spam complaint"), ("manual", "Manually suppressed")],
                    default="bounce",
                )),
                ("suppressed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("raw_event", models.JSONField(null=True, blank=True, help_text="Raw ESP webhook payload for audit.")),
            ],
            options={"ordering": ("-suppressed_at",)},
        ),
    ]
