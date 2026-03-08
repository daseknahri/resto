from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0005_profile_reservation_url"),
        ("sales", "0006_lead_tenant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservationTimelineEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("note", "Note"),
                            ("status_change", "Status change"),
                            ("bulk_status_change", "Bulk status change"),
                        ],
                        default="note",
                        max_length=32,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                ("previous_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="reservation_timeline_events", to=settings.AUTH_USER_MODEL)),
                ("lead", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="timeline_events", to="sales.lead")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="reservation_timeline_events", to="tenancy.tenant")),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
    ]
