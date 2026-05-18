from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0017_add_menu_card_layout_to_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="max_dishes",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Maximum number of dishes allowed. 0 means unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="max_staff_accounts",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Maximum number of staff accounts allowed. 0 means unlimited.",
            ),
        ),
    ]
