from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0007_dishoption_ordering"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
