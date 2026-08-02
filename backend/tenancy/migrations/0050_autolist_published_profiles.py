from django.db import migrations


def autolist_published_profiles(apps, schema_editor):
    """One-time: auto-list already-published businesses in the public marketplace.

    The "auto-list on publish" default (owner-approved) applies going forward via
    ProfileSerializer; this applies it retroactively to profiles that were published under the
    old opt-in default so the marketplace isn't empty. Only lists profiles that QUALIFY —
    published, not already listed, with a city and valid, non-null-island coordinates — so no
    broken marketplace cards are created. Owners keep full control via the directory toggle.
    """
    Profile = apps.get_model("tenancy", "Profile")
    (
        Profile.objects.filter(is_menu_published=True, directory_opt_in=False)
        .exclude(city="")
        .filter(
            lat__isnull=False,
            lng__isnull=False,
            lat__gte=-90,
            lat__lte=90,
            lng__gte=-180,
            lng__lte=180,
        )
        .exclude(lat=0, lng=0)
        .update(directory_opt_in=True)
    )


def noop_reverse(apps, schema_editor):
    # Not reversible per-row (prior opt-in state isn't recorded); leave listings as-is.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0049_profile_auto_accept_orders"),
    ]

    operations = [
        migrations.RunPython(autolist_published_profiles, noop_reverse),
    ]
