"""Keep the public-schema customer order index in sync with tenant orders.

Orders live in each tenant's schema; CustomerOrderRef (public schema) mirrors the
ones placed by a signed-in customer so their cross-restaurant history is queryable
without scanning every tenant schema. The mirror runs in the same transaction as the
order save, so it rolls back with the order if the order isn't committed.
"""
import logging

from django.db import connection
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender="menu.Order")
def compute_phone_digits(sender, instance, **kwargs):
    """Keep customer_phone_digits in sync with customer_phone on every save."""
    raw = instance.customer_phone or ""
    digits = "".join(c for c in raw if c.isdigit())
    instance.customer_phone_digits = digits[-9:] if digits else ""


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


def _denormalize_current_tenant_rating():
    """Recompute the denormalized rating summary for the CURRENT tenant (B8).

    Ratings live per-tenant; the public marketplace/directory reads a
    denormalized copy on the public Profile. Whenever a Rating is written or
    deleted we refresh that copy for the tenant whose schema is currently
    active. No-op on the public schema (Rating isn't there) or when there's no
    real tenant on the connection. Best-effort — never break the rating
    save/delete over the denormalization.
    """
    tenant = getattr(connection, "tenant", None)
    if tenant is None or getattr(tenant, "schema_name", None) is None:
        return  # not in a tenant context — nothing to denormalize
    try:
        from django_tenants.utils import get_public_schema_name
        if tenant.schema_name == get_public_schema_name():
            return  # public schema has no Rating table
        from .ratings import recompute_tenant_rating
        recompute_tenant_rating(tenant)
    except Exception:
        logger.exception("Failed to denormalize rating for current tenant")


@receiver(post_save, sender="menu.Rating")
def denormalize_rating_on_save(sender, instance, created=False, update_fields=None, **kwargs):
    # B8-followup: the denorm only depends on `score`. An owner-reply save
    # (update_fields={"owner_reply", "owner_reply_at"}) leaves the average/count
    # unchanged, so skip the cross-schema Avg/Count + Profile UPDATE for partial
    # saves that don't touch score. Recompute on create, on a full save
    # (update_fields is None), or when score is among the updated fields.
    if not created and update_fields is not None and "score" not in set(update_fields):
        return
    _denormalize_current_tenant_rating()


@receiver(post_delete, sender="menu.Rating")
def denormalize_rating_on_delete(sender, instance, **kwargs):
    _denormalize_current_tenant_rating()


def _denormalize_current_tenant_promos():
    """Recompute the denormalized promo schedule for the CURRENT tenant (B8-followup).

    Promotions live per-tenant; the public marketplace reads a denormalized copy
    (the schedule) on the public Profile.marketplace_promos and evaluates "live now"
    in-memory at request time. Whenever a Promotion is written or deleted we refresh
    that copy for the tenant whose schema is currently active. No-op on the public
    schema (Promotion isn't there) or when there's no real tenant on the connection.
    Best-effort — never break the promo save/delete over the denormalization.
    """
    tenant = getattr(connection, "tenant", None)
    if tenant is None or getattr(tenant, "schema_name", None) is None:
        return  # not in a tenant context — nothing to denormalize
    try:
        from django_tenants.utils import get_public_schema_name
        if tenant.schema_name == get_public_schema_name():
            return  # public schema has no Promotion table
        from .promos_denorm import recompute_tenant_promos
        recompute_tenant_promos(tenant)
    except Exception:
        logger.exception("Failed to denormalize promos for current tenant")


@receiver(post_save, sender="menu.Promotion")
def denormalize_promos_on_save(sender, instance, **kwargs):
    _denormalize_current_tenant_promos()


@receiver(post_delete, sender="menu.Promotion")
def denormalize_promos_on_delete(sender, instance, **kwargs):
    _denormalize_current_tenant_promos()
