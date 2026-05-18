from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0013_dish_stock_qty"),
    ]

    operations = [
        migrations.CreateModel(
            name="Rating",
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
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rating",
                        to="menu.order",
                    ),
                ),
                (
                    "score",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                ("comment", models.TextField(blank=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
