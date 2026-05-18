from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0020_tenant_payment_overdue_since"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="deletion_requested_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Set when the owner requests account deletion. Admin should review and complete the offboarding.",
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="deletion_reason",
            field=models.CharField(
                max_length=500,
                blank=True,
                help_text="Optional reason provided by the owner when requesting deletion.",
            ),
        ),
    ]
