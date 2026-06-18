from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0052_customeremailsuppression"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="driver_licence_expiry",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Expiry date of the uploaded driving licence. Admin-set when approving docs.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="driver_insurance_expiry",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Expiry date of the uploaded car insurance. Admin-set when approving docs.",
            ),
        ),
    ]
