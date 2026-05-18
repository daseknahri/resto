from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0020_rating_customer_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="source",
            field=models.CharField(
                choices=[("direct", "Direct"), ("marketplace", "Marketplace")],
                db_index=True,
                default="direct",
                help_text="Whether this order originated from a direct QR/menu visit or the platform marketplace.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="commission_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Platform commission for marketplace orders (10% of food subtotal).",
                max_digits=10,
            ),
        ),
    ]
