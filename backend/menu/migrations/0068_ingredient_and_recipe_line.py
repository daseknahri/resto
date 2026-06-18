from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0067_loyaltyconfig_tier_and_bonuses"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ingredient",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("unit", models.CharField(
                    choices=[
                        ("g", "g"), ("kg", "kg"), ("ml", "ml"), ("L", "L"),
                        ("unit", "unit"), ("oz", "oz"), ("lb", "lb"),
                        ("tsp", "tsp"), ("tbsp", "tbsp"),
                    ],
                    default="unit",
                    max_length=8,
                )),
                ("stock_quantity", models.DecimalField(
                    decimal_places=3,
                    default=Decimal("0.000"),
                    max_digits=12,
                    help_text="Current stock level in the ingredient's unit.",
                )),
                ("low_stock_threshold", models.DecimalField(
                    blank=True,
                    decimal_places=3,
                    max_digits=12,
                    null=True,
                    help_text="Alert when stock_quantity falls at or below this value. null = no alert.",
                )),
                ("cost_per_unit", models.DecimalField(
                    blank=True,
                    decimal_places=4,
                    max_digits=10,
                    null=True,
                    help_text="Cost per unit in the venue's default currency.",
                )),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="RecipeLine",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dish", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="recipe_lines",
                    to="menu.dish",
                )),
                ("ingredient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="recipe_lines",
                    to="menu.ingredient",
                )),
                ("quantity", models.DecimalField(
                    decimal_places=3,
                    max_digits=10,
                    help_text="Amount of the ingredient consumed per one serving of this dish.",
                )),
            ],
            options={"unique_together": {("dish", "ingredient")}},
        ),
    ]
