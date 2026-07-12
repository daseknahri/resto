"""Detect (and optionally fix) drifted public order-mirror CONTENT — RISK DATA-2 residual.

`CustomerOrderRef` (public schema) mirrors a tenant `Order`'s status/total/items_snapshot
via the `mirror_order_to_public_index` post_save signal (see `menu/signals.py`). That
signal is fire-and-forget best-effort: if it ever silently fails (an exception swallowed
by the signal's own try/except, a bulk `Order.objects.filter(...).update(...)` that
bypasses `save()` and never fires the signal, a partial write) the mirror falls out of
sync with the tenant order it's supposed to reflect — a stale status badge, a wrong total
in "My Orders", a re-order button offering an item that was later voided/comped.

This is DIFFERENT from `reconcile_order_refs` (RISK DATA-1), which detects mirrors whose
`Order` no longer exists at all (orphans, handled by deleting the mirror). This command
instead only looks at mirrors whose `Order` DOES still exist, and checks whether the
mirrored CONTENT still matches it.

Reuses `mirror_order_to_public_index` verbatim to recompute the mirror — the payload shape
(items-snapshot filtering, vertical lookup, field mapping) is intentionally NOT
re-implemented here; duplicating it would let this detector itself drift from what the
signal actually writes. To stay detect-only by default (mirrors `reconcile_order_refs`),
each candidate is checked inside one DB transaction: the real signal function runs (which
writes the recomputed value), the row is snapshotted before and after, and — unless the
values actually differ AND `--fix` was passed — the row is written back to its original
values before the transaction commits, so a plain run leaves no lasting change.

IMPORTANT gotcha this command works around: recomputing the mirror needs
`connection.tenant` to be the REAL `Tenant` row — `mirror_order_to_public_index` reads
`tenant.id` / `.name` / `.slug` off it. `django_tenants.utils.schema_context` (used by
`reconcile_order_refs` for its cheap existence check, since it only needs the search path)
sets `connection.tenant` to a bare `FakeTenant(schema_name=...)` that has no `.id` — under
that, the signal's `if tenant_id is None: return` guard fires and it silently no-ops. This
command uses `tenant_context(tenant)` instead, which sets `connection.tenant` to the actual
`Tenant` instance, so the reused signal function behaves exactly as it does when called
from a real request.

    python manage.py reconcile_order_content [--fix] [--limit 1000]

Only mirrors that already exist for a still-existing order are checked — an order with no
mirror at all (never customer-linked, or already an orphan) is out of scope for this
command (DATA-1's job). Never deletes anything; a drifted row is only ever re-synced back
to what the live order currently says, never removed. Safe to re-run — recomputing an
in-sync mirror is a no-op. Schedule alongside `reconcile_order_refs` / `sweep_delivery_jobs`
on a light cadence (e.g. hourly).
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import tenant_context

logger = logging.getLogger(__name__)

# Bookkeeping fields excluded from the before/after comparison: the PK never carries
# content, and `updated_at` (auto_now) changes on every write regardless of content.
_IGNORED_FIELDS = {"id", "updated_at"}


def _snapshot(ref):
    """Comparable dict of a CustomerOrderRef's current field values.

    Deliberately generic (driven by `_meta`, not a hand-picked field list) so the
    comparison automatically tracks whatever `mirror_order_to_public_index` actually
    writes, instead of this command re-declaring that list by hand and risking its own
    drift from the signal it's supposed to be checking.
    """
    return {
        f.attname: getattr(ref, f.attname)
        for f in ref._meta.concrete_fields
        if f.name not in _IGNORED_FIELDS
    }


class Command(BaseCommand):
    help = (
        "Detect (and with --fix, re-sync) public CustomerOrderRef mirrors whose content "
        "has drifted from the live tenant Order they mirror (RISK DATA-2 residual)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix", action="store_true",
            help="Re-sync drifted mirrors via mirror_order_to_public_index. "
                 "Detect-only (no writes) by default.",
        )
        parser.add_argument(
            "--limit", type=int, default=1000,
            help="Max mirrors to check per tenant (default 1000).",
        )

    def handle(self, *args, **options):
        from tenancy.models import Tenant
        from accounts.models import CustomerOrderRef
        from menu.models import Order
        from menu.signals import mirror_order_to_public_index

        do_fix = options["fix"]
        limit = options["limit"]

        stats = dict(tenants=0, mirrors_checked=0, drifted=0, fixed=0)
        samples = []

        # Only ACTIVE tenants carry live traffic worth reconciling — mirrors the tenant
        # selection in reconcile_profile_denorms (RISK DATA-5).
        for tenant in Tenant.objects.filter(lifecycle_status=Tenant.LifecycleStatus.ACTIVE):
            tid = tenant.id

            # Cheap pass (public schema): which order_numbers does this tenant even have a
            # mirror for? Only those are in scope — no mirror at all means the order was
            # never customer-linked, or is already an orphan (reconcile_order_refs' job).
            order_numbers = list(
                CustomerOrderRef.objects.filter(tenant_id=tid)
                .values_list("order_number", flat=True)[:limit]
            )
            if not order_numbers:
                continue
            stats["tenants"] += 1

            try:
                with tenant_context(tenant):
                    orders = Order.objects.filter(
                        order_number__in=order_numbers, customer__isnull=False
                    ).prefetch_related("items")

                    for order in orders:
                        ref = CustomerOrderRef.objects.filter(
                            tenant_id=tid, order_number=order.order_number
                        ).first()
                        if ref is None:
                            continue  # raced away since the cheap pass — not our concern

                        stats["mirrors_checked"] += 1
                        before = _snapshot(ref)

                        with transaction.atomic():
                            # Reuse the exact signal logic to recompute the mirror.
                            mirror_order_to_public_index(sender=Order, instance=order)

                            after_ref = CustomerOrderRef.objects.filter(
                                tenant_id=tid, order_number=order.order_number
                            ).first()
                            after = _snapshot(after_ref) if after_ref is not None else before

                            if before != after:
                                stats["drifted"] += 1
                                if len(samples) < 10:
                                    samples.append(f"{tenant.slug}:{order.order_number}")
                                if do_fix:
                                    stats["fixed"] += 1
                                else:
                                    # Detect-only: put the row back exactly as it was.
                                    CustomerOrderRef.objects.filter(
                                        tenant_id=tid, order_number=order.order_number
                                    ).update(**before)
            except Exception as exc:  # missing schema / read error — skip, don't fabricate drift
                self.stdout.write(
                    f"  [warn] tenant {getattr(tenant, 'slug', tid)}: cannot reconcile ({exc}); skipping"
                )
                continue

        self.stdout.write(self.style.SUCCESS(
            "reconcile_order_content: tenants_scanned={tenants} mirrors_checked={mirrors_checked} "
            "drifted={drifted} fixed={fixed}".format(**stats)
        ))
        if stats["drifted"]:
            level = self.style.SUCCESS if do_fix else self.style.WARNING
            action = "re-synced" if do_fix else "detected (re-run with --fix to re-sync)"
            self.stdout.write(level(
                f"{stats['drifted']} drifted mirror(s) {action}. Sample: {', '.join(samples)}"
            ))
