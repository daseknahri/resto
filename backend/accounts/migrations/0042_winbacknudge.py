from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add WinbackNudge — durable dedupe table for the win-back cron.
    Lives in the public schema (accounts app) so it is queryable from any
    schema_context without a cross-schema join.
    """

    dependencies = [
        ("accounts", "0041_customer_notify_promotions"),
    ]

    operations = [
        migrations.CreateModel(
            name="WinbackNudge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tenant_id",
                    models.IntegerField(
                        db_index=True,
                        help_text="FK to tenancy.Tenant (loose — no FK constraint for cross-schema safety).",
                    ),
                ),
                (
                    "customer_id",
                    models.BigIntegerField(
                        db_index=True,
                        help_text="FK to accounts.Customer.",
                    ),
                ),
                (
                    "sent_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
            ],
            options={
                "ordering": ("-sent_at",),
                "indexes": [
                    models.Index(
                        fields=("tenant_id", "customer_id", "sent_at"),
                        name="winbacknudge_tenant_cust_sent",
                    ),
                ],
            },
        ),
    ]
