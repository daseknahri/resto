from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_customer_auth_fields")]
    operations = [
        migrations.AddField(
            model_name="customer",
            name="email_verified",
            field=models.BooleanField(default=False),
        ),
    ]
