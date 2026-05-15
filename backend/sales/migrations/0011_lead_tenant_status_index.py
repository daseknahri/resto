from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0010_alter_adminauditlog_action"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(fields=["tenant_id", "status"], name="lead_tenant_status_idx"),
        ),
    ]
