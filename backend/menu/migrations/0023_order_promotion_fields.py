from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0022_promotion"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="promotion_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Discount amount applied by a promotion at order placement time.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="applied_promotion_name",
            field=models.CharField(
                blank=True,
                help_text="Snapshot of the promotion name that was applied to this order.",
                max_length=100,
            ),
        ),
    ]
