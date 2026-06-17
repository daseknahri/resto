"""
Add DeliveryJob.business_type (snapshot of tenant's business type at job creation).

Eliminates the extra Profile query at single-job endpoints by storing the
business type on the job itself rather than re-fetching it per request.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0045_deliveryjob_commission_rate_applied"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryjob",
            name="business_type",
            field=models.CharField(
                max_length=40,
                blank=True,
                default="restaurant",
                help_text=(
                    "Snapshot of the tenant's Profile.business_type at job creation. "
                    "Avoids a cross-schema Profile query on every single-job serialization."
                ),
            ),
        ),
    ]
