"""Denormalize per-tenant ClosureDate rows onto the public-schema Profile.

ClosureDate (menu.ClosureDate) lives in each restaurant's own tenant schema.
The public marketplace listing runs in the public schema and cannot query
tenant-schema tables, so it previously skipped the closure date check entirely
(see the "Intentionally skips" comment in accounts/views.py _compute_is_open_now).

`recompute_tenant_closures` collapses that gap: it reads ClosureDate rows from
the TENANT schema, serializes them as a sorted list of ISO date strings, then
writes the list to the PUBLIC Profile.closure_dates. The marketplace checks
today's tenant-local date against that list in-memory — no cross-schema query.
"""
import logging

logger = logging.getLogger(__name__)


def recompute_tenant_closures(tenant) -> None:
    """Recompute and persist the denormalized closure dates for one tenant.

    Called from menu/signals.py post_save/post_delete signals on ClosureDate.
    Best-effort: any failure is logged and swallowed so a ClosureDate save/delete
    never 500s over the denormalization.
    """
    if tenant is None:
        return
    schema_name = getattr(tenant, "schema_name", None)
    try:
        from django_tenants.utils import get_public_schema_name, schema_context

        if not schema_name or schema_name == get_public_schema_name():
            return

        with schema_context(schema_name):
            from menu.models import ClosureDate
            dates = list(
                ClosureDate.objects.values_list("date", flat=True).order_by("date")
            )
            iso_dates = [d.isoformat() for d in dates]

        with schema_context(get_public_schema_name()):
            from tenancy.models import Profile
            Profile.objects.filter(tenant=tenant).update(closure_dates=iso_dates)

    except Exception:
        logger.exception(
            "Failed to denormalize closure dates for tenant %s (schema=%s)",
            getattr(tenant, "id", "?"),
            schema_name,
        )
