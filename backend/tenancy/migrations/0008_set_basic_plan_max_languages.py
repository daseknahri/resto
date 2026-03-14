from django.db import migrations


def set_basic_plan_max_languages(apps, schema_editor):
    Plan = apps.get_model("tenancy", "Plan")
    Plan.objects.filter(code="starter").update(max_languages=3)


def noop_reverse(apps, schema_editor):
    # Do not force rollback values.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0007_profile_i18n_fields"),
    ]

    operations = [
        migrations.RunPython(set_basic_plan_max_languages, noop_reverse),
    ]

