from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_user_staff_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerRating",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trust_ratings",
                        to="accounts.customer",
                    ),
                ),
                ("tenant_id", models.IntegerField(db_index=True)),
                ("order_number", models.CharField(blank=True, db_index=True, max_length=20)),
                ("score", models.PositiveSmallIntegerField()),
                ("note", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("customer", "tenant_id", "order_number")},
            },
        ),
    ]
