from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0023_order_promotion_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.IntegerField(db_index=True, help_text="accounts.User pk")),
                ("endpoint", models.TextField(unique=True)),
                ("p256dh", models.TextField(help_text="Client public key (URL-safe base64)")),
                ("auth", models.CharField(help_text="Auth secret (URL-safe base64)", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
