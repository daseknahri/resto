from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0006_tenant_lifecycle_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="address_i18n",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="profile",
            name="description_i18n",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="profile",
            name="tagline_i18n",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

