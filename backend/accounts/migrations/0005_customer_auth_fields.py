from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_customer"),
    ]

    operations = [
        # Make phone nullable (Google-only customers may not have a phone)
        migrations.AlterField(
            model_name="customer",
            name="phone",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=30,
                null=True,
                unique=True,
            ),
        ),
        # Track whether the phone number has been OTP-verified
        migrations.AddField(
            model_name="customer",
            name="phone_verified",
            field=models.BooleanField(default=False),
        ),
        # Google OAuth sub — unique identifier from Google's JWT
        migrations.AddField(
            model_name="customer",
            name="google_sub",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=200,
                null=True,
                unique=True,
            ),
        ),
    ]
