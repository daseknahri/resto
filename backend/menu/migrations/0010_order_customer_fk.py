from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds a nullable platform-level Customer FK to Order.

    Anonymous orders (customer=None) continue to work exactly as before.
    When a customer creates a platform account, their orders are linked
    retroactively by matching customer_phone.

    Depends on accounts.0004_customer which runs in the public (shared) schema
    before tenant migrations are applied.
    """

    dependencies = [
        ("accounts", "0004_customer"),
        ("menu", "0009_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer",
            field=models.ForeignKey(
                "accounts.Customer",
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
            ),
        ),
    ]
