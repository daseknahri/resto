"""Add CustomerTenantOptOut for per-(customer, tenant) promo email opt-out."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0046_deliveryjob_business_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerTenantOptOut",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant_optouts",
                        to="accounts.customer",
                    ),
                ),
                (
                    "tenant_id",
                    models.IntegerField(
                        db_index=True,
                        help_text="FK to tenancy.Tenant (loose — no FK constraint for cross-schema safety).",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"unique_together": {("customer", "tenant_id")}},
        ),
        migrations.AddIndex(
            model_name="customertenantoptout",
            index=models.Index(fields=["customer", "tenant_id"], name="cust_tenant_optout_idx"),
        ),
    ]
