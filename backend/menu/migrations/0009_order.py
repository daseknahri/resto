from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0008_dish_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_number", models.CharField(db_index=True, max_length=20, unique=True)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("confirmed", "Confirmed"),
                        ("preparing", "Preparing"),
                        ("ready", "Ready"),
                        ("completed", "Completed"),
                        ("cancelled", "Cancelled"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=20,
                )),
                ("customer_name", models.CharField(blank=True, max_length=80)),
                ("customer_phone", models.CharField(blank=True, max_length=30)),
                ("customer_note", models.TextField(blank=True)),
                ("fulfillment_type", models.CharField(
                    blank=True,
                    choices=[("pickup", "Pickup"), ("delivery", "Delivery"), ("table", "Table")],
                    max_length=20,
                )),
                ("table_label", models.CharField(blank=True, max_length=40)),
                ("table_slug", models.SlugField(blank=True, max_length=55)),
                ("delivery_address", models.TextField(blank=True)),
                ("delivery_location_url", models.URLField(blank=True, max_length=500)),
                ("delivery_lat", models.FloatField(blank=True, null=True)),
                ("delivery_lng", models.FloatField(blank=True, null=True)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=8)),
                ("owner_note", models.TextField(blank=True)),
                ("estimated_ready_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status_updated_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="menu.order")),
                ("dish_slug", models.SlugField(max_length=210)),
                ("dish_name", models.CharField(max_length=200)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=8)),
                ("qty", models.PositiveIntegerField(default=1)),
                ("note", models.CharField(blank=True, max_length=120)),
                ("options", models.JSONField(blank=True, default=list)),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ],
            options={
                "ordering": ("id",),
            },
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["status", "created_at"], name="menu_order_status_created_idx"),
        ),
    ]
