from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0005_profile_reservation_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="canceled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="canceled_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="tenant",
            name="lifecycle_status",
            field=models.CharField(
                choices=[("active", "Active"), ("suspended", "Suspended"), ("canceled", "Canceled")],
                db_index=True,
                default="active",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="suspended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
