from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0043_rating_owner_reply"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_id", models.IntegerField(db_index=True, help_text="Refers to accounts.Customer.id (public schema) — no DB-level FK.")),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("customer_id",)},
            },
        ),
    ]
