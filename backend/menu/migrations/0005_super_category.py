from django.db import migrations, models


def attach_default_super_category(apps, schema_editor):
    SuperCategory = apps.get_model("menu", "SuperCategory")
    Category = apps.get_model("menu", "Category")

    default_super_category, _ = SuperCategory.objects.get_or_create(
        slug="menu",
        defaults={
            "name": "Menu",
            "position": 0,
            "is_published": True,
            "is_temporarily_disabled": False,
            "disabled_note": "",
            "name_i18n": {},
        },
    )
    Category.objects.filter(super_category__isnull=True).update(super_category=default_super_category)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0004_menu_i18n_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="SuperCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("name_i18n", models.JSONField(blank=True, default=dict)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_published", models.BooleanField(default=True)),
                ("is_temporarily_disabled", models.BooleanField(default=False)),
                ("disabled_note", models.CharField(blank=True, max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("position", "name"),
            },
        ),
        migrations.AddField(
            model_name="category",
            name="super_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="categories",
                to="menu.supercategory",
            ),
        ),
        migrations.RunPython(attach_default_super_category, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="category",
            name="super_category",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="categories",
                to="menu.supercategory",
            ),
        ),
    ]
