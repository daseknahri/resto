from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0043_profile_marketplace_promos"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="closure_dates",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text=(
                    "Denormalized list of ISO date strings (YYYY-MM-DD) on which the tenant "
                    "is closed. Auto-maintained by menu ClosureDate post_save/post_delete signals."
                ),
            ),
        ),
    ]
