from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0006_option_group"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="dishoption",
            options={"ordering": ("position", "name")},
        ),
    ]
