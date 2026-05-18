from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0023_profile_directory_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="lat",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Latitude of the restaurant (decimal degrees). Used for distance sorting in the marketplace.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="lng",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Longitude of the restaurant (decimal degrees). Used for distance sorting in the marketplace.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="price_tier",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "€"), (2, "€€"), (3, "€€€")],
                default=2,
                help_text="General price range indicator shown in the marketplace.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Dietary and feature tags used for marketplace filtering.",
            ),
        ),
    ]
