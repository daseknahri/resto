"""Backfill the public CustomerOrderRef index from existing tenant orders.

The order-index signal only mirrors orders saved after it was deployed. This one-off
command walks every tenant schema and creates/updates a CustomerOrderRef for each
customer-linked order, so historical orders show up in the customer's cross-restaurant
history. Safe to re-run (idempotent upsert). Dry-run by default.

    python manage.py backfill_order_index            # report what would be indexed
    python manage.py backfill_order_index --apply     # write the index
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill the public CustomerOrderRef order index from existing tenant orders."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the index (otherwise dry-run).")
        parser.add_argument("--per-tenant", type=int, default=5000, help="Max orders to index per tenant.")

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context
        from tenancy.models import Tenant
        from accounts.models import CustomerOrderRef

        apply = options["apply"]
        per_tenant = options["per_tenant"]

        # Phase 1: collect customer-linked orders from every tenant schema.
        collected = []  # (tenant_id, name, slug, order dict)
        scanned = 0
        for tenant in Tenant.objects.all():
            try:
                with schema_context(tenant.schema_name):
                    from menu.models import Order
                    rows = list(
                        Order.objects.filter(customer_id__isnull=False)
                        .prefetch_related("items")
                        .order_by("-created_at")[:per_tenant]
                    )
            except Exception:
                continue  # skip broken/migrating schemas
            scanned += 1
            for o in rows:
                items_snap = [
                    {"slug": i.dish_slug, "name": i.dish_name, "qty": i.qty, "price": float(i.unit_price)}
                    for i in o.items.all()
                ]
                collected.append((tenant.id, tenant.name, tenant.slug, o, items_snap))

        if not apply:
            self.stdout.write(
                f"[dry-run] would index {len(collected)} order(s) from {scanned} restaurant(s). "
                "Re-run with --apply."
            )
            return

        # Phase 2: write the index in the public schema.
        written = 0
        for tenant_id, name, slug, o, items_snap in collected:
            CustomerOrderRef.objects.update_or_create(
                tenant_id=tenant_id,
                order_number=o.order_number,
                defaults={
                    "customer_id": o.customer_id,
                    "restaurant_name": name or "",
                    "restaurant_slug": slug or "",
                    "status": o.status or "",
                    "fulfillment_type": o.fulfillment_type or "",
                    "total": o.total or 0,
                    "currency": o.currency or "MAD",
                    "order_created_at": o.created_at,
                    "items_snapshot": items_snap,
                },
            )
            written += 1

        self.stdout.write(self.style.SUCCESS(f"Indexed {written} order(s) from {scanned} restaurant(s)."))
