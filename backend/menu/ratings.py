"""Denormalize per-tenant ratings onto the public-schema Profile (B8).

Ratings (menu.Rating) live in each restaurant's own schema. The public
marketplace / directory listing iterates the PUBLIC Profile page and used to
switch into every tenant's schema to aggregate that tenant's ratings — an
O(N_tenants) cross-schema N+1 per request (papered over with a 90s cache).

`recompute_tenant_rating` collapses that into a single denormalized read: it
computes the aggregate INSIDE the tenant schema, then writes the rounded
average (1dp) + count onto the public Profile.rating_avg / rating_count. The
listing views then read those columns straight off the already-fetched Profile.

Kept correct on the empty edge: deleting the last rating leaves avg=None,
count=0 (Avg over zero rows is None; Count is 0).
"""
import logging

logger = logging.getLogger(__name__)


def recompute_tenant_rating(tenant) -> None:
    """Recompute and persist the denormalized rating summary for one tenant.

    Aggregates menu.Rating inside the tenant's schema, then updates the PUBLIC
    Profile row for that tenant. Best-effort: any failure is logged and
    swallowed so a rating save/delete never 500s over the denormalization.
    """
    if tenant is None:
        return
    schema_name = getattr(tenant, "schema_name", None)
    try:
        from django.db.models import Avg, Count
        from django_tenants.utils import get_public_schema_name, schema_context

        # Never aggregate Rating against the public schema (the table isn't there).
        if not schema_name or schema_name == get_public_schema_name():
            return

        with schema_context(schema_name):
            from menu.models import Rating
            agg = Rating.objects.aggregate(avg=Avg("score"), cnt=Count("id"))

        cnt = agg["cnt"] or 0
        avg = round(float(agg["avg"]), 1) if cnt else None

        with schema_context(get_public_schema_name()):
            from tenancy.models import Profile
            Profile.objects.filter(tenant=tenant).update(
                rating_avg=avg,
                rating_count=cnt,
            )

        # The public marketplace/directory listing caches its (cross-tenant) response
        # keyed by a global version. Bump it so the new rating shows immediately
        # instead of waiting out the list-cache TTL. Imported lazily to avoid an
        # import cycle (menu must not import accounts at module load). Best-effort —
        # a bust failure must never break the rating save.
        from accounts.views import _bust_public_list_cache
        _bust_public_list_cache()
    except Exception:
        # Denormalization is best-effort — never break a rating save/delete over it.
        logger.exception(
            "Failed to recompute denormalized rating for tenant schema=%s", schema_name
        )
