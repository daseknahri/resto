from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds a nullable platform-level Customer FK to Rating.

    Mirrors the existing Order.customer FK pattern (see 0010_order_customer_fk).
    Anonymous ratings (customer=None) continue to work.  When a rated order is
    linked to a Customer account, the rating gains that link so the customer can
    see their own rating history.
    """

    dependencies = [
        ("accounts", "0009_customer_rating"),
        ("menu", "0019_order_wallet_amount_paid"),
    ]

    operations = [
        migrations.AddField(
            model_name="rating",
            name="customer",
            field=models.ForeignKey(
                "accounts.Customer",
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="restaurant_ratings",
            ),
        ),
    ]
