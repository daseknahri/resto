from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0064_tablelink_status_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="Shift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "user_id",
                    models.IntegerField(
                        db_index=True,
                        help_text="accounts.User pk of the staff member.",
                    ),
                ),
                (
                    "user_name",
                    models.CharField(
                        blank=True,
                        max_length=150,
                        help_text="Name snapshot taken at clock-in for reporting.",
                    ),
                ),
                ("clock_in", models.DateTimeField(db_index=True)),
                (
                    "clock_out",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="Null while the shift is still open (not yet clocked out).",
                    ),
                ),
                (
                    "hourly_rate",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                        help_text="Optional hourly wage rate — used to compute labor cost on the Z-report.",
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-clock_in",),
            },
        ),
        migrations.AddIndex(
            model_name="shift",
            index=models.Index(fields=["user_id", "clock_in"], name="menu_shift_user_clockin_idx"),
        ),
    ]
