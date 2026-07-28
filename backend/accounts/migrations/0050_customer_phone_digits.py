"""Add Customer.phone_digits — last 9 digits of phone for btree-indexed search.

Includes a data migration that backfills existing rows so the column is usable
immediately after deploy without waiting for a full-table update.
"""
from django.db import migrations, models


def _backfill_phone_digits(apps, schema_editor):
    Customer = apps.get_model("accounts", "Customer")
    batch = []
    for c in Customer.objects.exclude(phone=None).exclude(phone="").only("id", "phone", "phone_digits"):
        digits = "".join(ch for ch in (c.phone or "") if ch.isdigit())
        c.phone_digits = digits[-9:] if digits else ""
        batch.append(c)
        if len(batch) >= 500:
            Customer.objects.bulk_update(batch, ["phone_digits"])
            batch = []
    if batch:
        Customer.objects.bulk_update(batch, ["phone_digits"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0049_customer_referral_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="phone_digits",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Last 9 digits of phone, stripped of non-digit chars — powers btree-indexed exact-match search.",
                max_length=9,
            ),
        ),
        # elidable: one-time backfill of a new column from existing rows — a fresh
        # schema has no rows to backfill and maintains phone_digits going forward, so
        # this can be dropped when these migrations are squashed (RISK STRUCT-2).
        migrations.RunPython(_backfill_phone_digits, migrations.RunPython.noop, elidable=True),
    ]
