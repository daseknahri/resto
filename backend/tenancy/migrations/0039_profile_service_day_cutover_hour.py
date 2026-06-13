from django.db import migrations, models


class Migration(migrations.Migration):
    """Add Profile.service_day_cutover_hour.

    The tenant-local hour (0..11) at which one service day rolls to the next.
    Default 0 = calendar midnight -> NO-OP for existing tenants (fully non-breaking).
    A late-night venue sets this to e.g. 3 or 4 so that orders placed at 2 am
    are attributed to the previous day's service window.
    """

    dependencies = [
        ("tenancy", "0038_profile_winback"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="service_day_cutover_hour",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Tenant-local hour (0–11) at which one service day rolls to the next. 0 = calendar midnight (default, no behaviour change). Set to e.g. 3 for a late-night venue so 2 am orders belong to yesterday's shift.",
            ),
        ),
    ]
