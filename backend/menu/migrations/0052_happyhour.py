from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0051_combocomponent_orderitem_combo_components"),
    ]

    operations = [
        migrations.CreateModel(
            name="HappyHour",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("days", models.JSONField(default=list, help_text="List of weekday ints — 0=Monday … 6=Sunday (Python weekday() convention).")),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("percent_off", models.PositiveSmallIntegerField(help_text="Percentage discount applied to dish.price (1–90).")),
                ("categories", models.ManyToManyField(blank=True, help_text="Restrict rule to these categories. Empty = all categories.", related_name="happy_hours", to="menu.category")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("id",),
            },
        ),
    ]
