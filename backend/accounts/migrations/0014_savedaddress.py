from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_customer_loyalty_points"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_addresses",
                        to="accounts.customer",
                    ),
                ),
                ("label", models.CharField(blank=True, help_text="Friendly label, e.g. 'Home', 'Work'. Optional.", max_length=60)),
                ("address", models.TextField(max_length=300)),
                ("location_url", models.URLField(blank=True, max_length=500)),
                ("lat", models.FloatField(blank=True, null=True)),
                ("lng", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
