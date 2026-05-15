from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_customer_email_verified")]
    operations = [
        migrations.AlterField(
            model_name="customer",
            name="email",
            field=models.EmailField(blank=True, db_index=True),
        ),
    ]
