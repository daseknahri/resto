from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0050_dish_low_stock_threshold"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComboComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("qty", models.PositiveSmallIntegerField(default=1, help_text="How many units of this component are included per combo ordered.")),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "component",
                    models.ForeignKey(
                        help_text="The component dish included in this combo.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="part_of_combos",
                        to="menu.dish",
                    ),
                ),
                (
                    "dish",
                    models.ForeignKey(
                        help_text="The combo dish that owns this component.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="combo_components",
                        to="menu.dish",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "unique_together": {("dish", "component")},
            },
        ),
        migrations.AddField(
            model_name="orderitem",
            name="combo_components",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Placement snapshot of combo components. "
                    "Each entry: {dish_id, name, qty} where qty is per-unit (×item.qty to get total). "
                    "Empty for non-combo dishes."
                ),
            ),
        ),
    ]
