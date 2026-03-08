from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tagline", models.CharField(blank=True, max_length=150)),
                ("description", models.TextField(blank=True)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("whatsapp", models.CharField(blank=True, max_length=50)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("google_maps_url", models.URLField(blank=True)),
                ("facebook_url", models.URLField(blank=True)),
                ("instagram_url", models.URLField(blank=True)),
                ("tiktok_url", models.URLField(blank=True)),
                ("primary_color", models.CharField(default="#0F766E", max_length=7)),
                ("secondary_color", models.CharField(default="#F59E0B", max_length=7)),
                ("language", models.CharField(default="en", max_length=5)),
                ("logo_url", models.URLField(blank=True)),
                ("hero_url", models.URLField(blank=True)),
                (
                    "tenant",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to="tenancy.tenant"),
                ),
            ],
        ),
    ]
