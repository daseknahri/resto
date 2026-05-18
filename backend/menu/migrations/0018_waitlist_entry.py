from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0017_closure_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "booked_for",
                    models.DateTimeField(
                        db_index=True,
                        help_text="The desired date/time slot the customer is waiting for.",
                    ),
                ),
                ("party_size", models.PositiveSmallIntegerField(default=1)),
                ("name", models.CharField(max_length=150)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("email", models.EmailField(blank=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("waiting", "Waiting"),
                            ("notified", "Notified"),
                            ("converted", "Converted"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="waiting",
                        max_length=20,
                    ),
                ),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ("created_at",),
            },
        ),
    ]
