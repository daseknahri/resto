from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0024_profile_marketplace_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="delivery_zone_id",
            field=models.IntegerField(
                null=True,
                blank=True,
                db_index=True,
                help_text="ID of the DeliveryZone this restaurant is assigned to (public schema).",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="delivery_radius_km",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Maximum delivery distance in km from the restaurant's coordinates.",
            ),
        ),
    ]
