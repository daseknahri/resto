from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0027_order_tip_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="supercategory",
            name="description",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Short tagline shown on the menu-selector card (e.g. 'Served 11 am – 3 pm').",
                max_length=280,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="supercategory",
            name="description_i18n",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="supercategory",
            name="image_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Cover image displayed on the menu-selector card.",
            ),
            preserve_default=False,
        ),
    ]
