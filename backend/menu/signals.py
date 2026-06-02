"""Keep the public-schema customer order index in sync with tenant orders.

Orders live in each tenant's schema; CustomerOrderRef (public schema) mirrors the
ones placed by a signed-in customer so their cross-restaurant history is queryable
without scanning every tenant schema. The mirror runs in the same transaction as the
order save, so it rolls back with the order if the order isn't committed.
"""
import logging

from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="menu.Order")
def mirror_order_to_public_index(sender, instance, **kwargs):
    # Only customer-linked orders belong in a customer's history.
    if not getattr(instance, "customer_id", None):
        return

    tenant = getattr(connection, "tenant", None)
    tenant_id = getattr(tenant, "id", None)
    if tenant_id is None:
        return  # not in a tenant context — nothing to attribute the order to

    try:
        from accounts.models import CustomerOrderRef

        # Build a compact items snapshot for re-order (slugs + prices).
        try:
            items_snap = [
                {
                    "slug": item.dish_slug,
                    "name": item.dish_name,
                    "qty": item.qty,
                    "price": float(item.unit_price),
                }
                for item in instance.items.all()
            ]
        except Exception:
            items_snap = []

        CustomerOrderRef.objects.update_or_create(
            tenant_id=tenant_id,
            order_number=instance.order_number,
            defaults={
                "customer_id": instance.customer_id,
                "restaurant_name": getattr(tenant, "name", "") or "",
                "restaurant_slug": getattr(tenant, "slug", "") or "",
                "status": instance.status or "",
                "fulfillment_type": instance.fulfillment_type or "",
                "total": instance.total or 0,
                "currency": instance.currency or "MAD",
                "order_created_at": instance.created_at,
                "items_snapshot": items_snap,
            },
        )
    except Exception:
        # The order index is best-effort — never break order placement/updates over it.
        logger.exception("Failed to mirror order %s to public index", getattr(instance, "order_number", "?"))
