"""Backfill vertical tags on existing rows during deploy (C13 / P1).

Runs as part of ``migrate`` (the shared/public phase) BEFORE the app serves
traffic, so the ``?vertical=`` per-service reads never see a half-migrated DB —
closing the deploy→backfill window without a manual step. The standalone
``backfill_order_ref_vertical`` / ``backfill_wallet_vertical`` commands remain
for ops re-runs. Idempotent: only fills blank/null ``vertical``. Memory-safe:
DB-side ``update()`` keyed by the (small) set of distinct tenant_ids.

The business_type→vertical map is INLINED (not imported from accounts.verticals)
so the migration stays independent of future code changes — Django best practice.
See KEPOLI_ACCOUNT_ARCHITECTURE.md §7.
"""
from django.db import migrations

# Mirror of accounts/verticals.py at write time. pharmacy is its own vertical.
_BT_TO_VERTICAL = {
    "restaurant": "food",
    "cafe": "food",
    "bakery": "shops",
    "grocery": "shops",
    "retail": "shops",
    "pharmacy": "pharmacy",
}


def _vertical_for_bt(bt):
    if not bt:
        return "food"
    return _BT_TO_VERTICAL.get(str(bt).strip().lower(), "food")


def backfill(apps, schema_editor):
    CustomerOrderRef = apps.get_model("accounts", "CustomerOrderRef")
    WalletTransaction = apps.get_model("accounts", "WalletTransaction")
    Profile = apps.get_model("tenancy", "Profile")

    # One query: {tenant_id: business_type} (Profile is public/shared).
    bt_map = dict(Profile.objects.values_list("tenant_id", "business_type"))

    # 1. CustomerOrderRef.vertical — blank rows, batched per tenant.
    for tid in list(
        CustomerOrderRef.objects.filter(vertical="")
        .values_list("tenant_id", flat=True)
        .distinct()
    ):
        CustomerOrderRef.objects.filter(vertical="", tenant_id=tid).update(
            vertical=_vertical_for_bt(bt_map.get(tid))
        )

    # 2. WalletTransaction.vertical — null rows. CASHOUT -> driver; other
    #    tenant-attributed rows -> the tenant's vertical; the rest stay null
    #    (global: top-up, P2P transfer, adjustment).
    WalletTransaction.objects.filter(
        vertical__isnull=True, type="cashout"
    ).update(vertical="driver")
    base = WalletTransaction.objects.filter(
        vertical__isnull=True, tenant_id__isnull=False
    ).exclude(type="cashout")
    for tid in list(base.values_list("tenant_id", flat=True).distinct()):
        bt = bt_map.get(tid)
        if bt:
            base.filter(tenant_id=tid).update(vertical=_vertical_for_bt(bt))


def reverse(apps, schema_editor):
    # Irreversible data backfill — no-op reverse (columns remain, just un-tagged).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0057_customerserviceprofile"),
        ("tenancy", "0033_profile_business_type"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
