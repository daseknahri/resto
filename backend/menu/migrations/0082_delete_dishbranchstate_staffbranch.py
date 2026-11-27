"""R6-07: delete the dead per-branch models (DishBranchState, StaffBranch).

No code read them (repo-wide grep: zero hits outside models/migrations) and no
endpoint ever created a row. The tables are dropped — but only after a guard
proves the current schema holds no rows: if a tenant ever got rows in by hand,
the migration aborts loudly instead of silently destroying data.
"""

from django.db import migrations


def check_empty(apps, schema_editor):
    DishBranchState = apps.get_model("menu", "DishBranchState")
    StaffBranch = apps.get_model("menu", "StaffBranch")
    if DishBranchState.objects.exists() or StaffBranch.objects.exists():
        raise RuntimeError(
            "R6-07: refusing to drop menu_dishbranchstate/menu_staffbranch — "
            "rows exist in this schema. Delete or migrate them by hand first."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0081_commissionstatementline_payment_status"),
    ]

    operations = [
        migrations.RunPython(check_empty, migrations.RunPython.noop),
        migrations.DeleteModel(name="DishBranchState"),
        migrations.DeleteModel(name="StaffBranch"),
    ]
