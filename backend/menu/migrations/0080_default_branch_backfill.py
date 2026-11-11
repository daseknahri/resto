"""Phase 3 multi-branch: default-branch backfill (data migration).

Runs inside each tenant schema via the migrate_schemas --tenant deploy
loop. For the schema being migrated:

  * create the tenant's default Branch (slug "main") from its Profile —
    name from the Tenant row, address/phone/whatsapp/business-hours copied;
  * backfill Order.branch and TableSection.branch to it (rows that predate
    the branch entity belonged to the tenant's one location by definition).

The Profile lives in the PUBLIC schema (tenancy app), so its fields are
read with schema-qualified SQL; the writes use the historical (schema-
local) models. Idempotent: if a default branch already exists it is
reused and only still-null FKs are filled. Reversible: FKs are nulled and
the backfilled branch (is_default + slug "main") is removed.
"""
import json

from django.db import connection, migrations


def _tenant_and_profile():
    schema = connection.schema_name
    with connection.cursor() as cur:
        cur.execute(
            "SELECT t.name, p.address, p.phone, p.whatsapp, "
            "p.business_hours_schedule "
            "FROM public.tenancy_tenant t "
            "LEFT JOIN public.tenancy_profile p ON p.tenant_id = t.id "
            "WHERE t.schema_name = %s",
            [schema],
        )
        row = cur.fetchone()
    if row is None:
        return (schema, "", "", "", None)
    name, address, phone, whatsapp, hours = row
    if isinstance(hours, str):
        try:
            hours = json.loads(hours)
        except ValueError:
            hours = None
    return (name or schema, address or "", phone or "", whatsapp or "", hours)


def forwards(apps, schema_editor):
    if connection.schema_name == "public":
        return
    Branch = apps.get_model("menu", "Branch")
    Order = apps.get_model("menu", "Order")
    TableSection = apps.get_model("menu", "TableSection")
    branch = Branch.objects.filter(is_default=True).first()
    if branch is None:
        name, address, phone, whatsapp, hours = _tenant_and_profile()
        branch = Branch.objects.create(
            name=name,
            slug="main",
            address=address,
            phone=phone,
            whatsapp=whatsapp,
            business_hours_schedule=hours,
            is_active=True,
            is_default=True,
            sort_order=0,
        )
    Order.objects.filter(branch__isnull=True).update(branch=branch)
    TableSection.objects.filter(branch__isnull=True).update(branch=branch)


def backwards(apps, schema_editor):
    if connection.schema_name == "public":
        return
    Branch = apps.get_model("menu", "Branch")
    Order = apps.get_model("menu", "Order")
    TableSection = apps.get_model("menu", "TableSection")
    Order.objects.all().update(branch=None)
    TableSection.objects.all().update(branch=None)
    Branch.objects.filter(slug="main", is_default=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0079_branch_order_branch_tablesection_branch_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
