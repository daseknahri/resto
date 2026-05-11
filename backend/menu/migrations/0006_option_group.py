from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0005_super_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="OptionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("name_i18n", models.JSONField(blank=True, default=dict)),
                ("min_select", models.PositiveIntegerField(default=1)),
                ("max_select", models.PositiveIntegerField(default=1)),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "dish",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="option_groups",
                        to="menu.dish",
                    ),
                ),
            ],
            options={"ordering": ("position", "name")},
        ),
        migrations.AddField(
            model_name="dishoption",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="options",
                to="menu.optiongroup",
            ),
        ),
        migrations.AddField(
            model_name="dishoption",
            name="position",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
