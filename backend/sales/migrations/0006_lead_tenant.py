from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0005_profile_reservation_url"),
        ("sales", "0005_alter_adminauditlog_action_tierupgraderequest_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="leads",
                to="tenancy.tenant",
            ),
        ),
    ]
