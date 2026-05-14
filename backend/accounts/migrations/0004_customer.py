from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_passwordresettoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(db_index=True, max_length=30, unique=True)),
                ("email", models.EmailField(blank=True)),
                ("name", models.CharField(blank=True, max_length=80)),
                ("locale", models.CharField(default="en", max_length=10)),
                ("wallet_balance", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="WalletTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(
                    choices=[
                        ("topup", "Top-up"),
                        ("payment", "Payment"),
                        ("refund", "Refund"),
                        ("bonus", "Bonus"),
                    ],
                    max_length=20,
                )),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("tenant_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="wallet_transactions",
                    to="accounts.customer",
                )),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
