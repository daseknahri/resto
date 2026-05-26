from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_savedaddress"),
    ]

    operations = [
        migrations.CreateModel(
            name="WalletVoucher",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=32, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("is_used", models.BooleanField(db_index=True, default=False)),
                (
                    "used_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="redeemed_vouchers",
                        to="accounts.customer",
                    ),
                ),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
