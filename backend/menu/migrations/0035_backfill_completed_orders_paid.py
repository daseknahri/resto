"""
Backfill payment state for historical orders.

Before payment_status existed, a COMPLETED order had already been fulfilled and
paid in person (cash/card/wallet). Mark those as PAID so the new payment badges
and "needs payment" filters don't show finished orders as unpaid. Forward-only —
the reverse is a no-op (we never un-pay a settled order).
"""
from django.db import migrations
from django.db.models import F


def mark_completed_paid(apps, schema_editor):
    Order = apps.get_model("menu", "Order")
    completed = Order.objects.filter(status="completed")

    # Flip unpaid → paid for already-finished orders.
    completed.filter(payment_status="unpaid").update(payment_status="paid")

    # Best-effort paid_at: use the completion timestamp, else the created time.
    completed.filter(paid_at__isnull=True, status_updated_at__isnull=False).update(
        paid_at=F("status_updated_at")
    )
    completed.filter(paid_at__isnull=True).update(paid_at=F("created_at"))


def noop(apps, schema_editor):
    # Forward-only: do not revert settled orders back to unpaid.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0034_order_paid_at_order_payment_status_and_more"),
    ]

    operations = [
        migrations.RunPython(mark_completed_paid, noop),
    ]
