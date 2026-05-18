from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0014_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="allergens",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of allergen keys present in this dish (e.g. ['gluten', 'eggs']).",
            ),
        ),
    ]
