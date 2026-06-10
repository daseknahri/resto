from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0034_profile_delivery_commission_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="daily_revenue_goal",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Owner-set daily revenue target. Shown as a progress bar on the home dashboard.",
                max_digits=10,
                null=True,
            ),
        ),
    ]
