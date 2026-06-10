from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0044_customernote"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="attributes",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Retail product attributes (sku, barcode, brand, unit). "
                    "Empty for restaurant dishes. Kepoli Phase 1 seam — see KEPOLI_ARCHITECTURE.md."
                ),
            ),
        ),
    ]
