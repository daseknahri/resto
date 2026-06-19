from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0056_wallettransaction_vertical"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerServiceProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "vertical",
                    models.CharField(
                        db_index=True,
                        help_text="Consumer vertical this profile scopes (see accounts.verticals).",
                        max_length=16,
                    ),
                ),
                ("notify_updates", models.BooleanField(default=True)),
                ("notify_promotions", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_profiles",
                        to="accounts.customer",
                    ),
                ),
                (
                    "default_address",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="accounts.savedaddress",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="customerserviceprofile",
            constraint=models.UniqueConstraint(
                fields=("customer", "vertical"), name="customerserviceprofile_customer_vertical_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="customerserviceprofile",
            index=models.Index(fields=["customer", "vertical"], name="cust_service_profile_idx"),
        ),
    ]
