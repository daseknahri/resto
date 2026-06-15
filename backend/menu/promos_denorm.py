"""Denormalize per-tenant promos onto the public-schema Profile (B8-followup).

Promotions (menu.Promotion) live in each restaurant's own schema. The public
marketplace listing iterates the PUBLIC Profile page and used to switch into
every tenant's schema to fetch the active promos and derive a "promo_badge" — an
O(N_tenants) cross-schema N+1 per request (the LAST one in the listing loop;
ratings were already killed in B8).

`recompute_tenant_promos` collapses that into a single denormalized read: it
serializes this tenant's is_active promos (only the fields the badge needs) INSIDE
the tenant schema, ordered the SAME way the view selected on (highest discount
first), then writes that list onto the public Profile.marketplace_promos. The
listing view then evaluates "live now" in-memory at request time on the
denormalized schedule — exactly like the flash-sale schedule denorm — with no
per-tenant schema switch.

Only the SCHEDULE is denormalized (the time/date window). Whether a promo is live
right now is computed at REQUEST time by accounts.views._promo_badge_from_denorm,
so the badge stays correct as the clock crosses a window boundary without any
re-denormalization.

Kept correct on the empty edge: a tenant with no is_active promos gets an empty
list (no badge).
"""
import logging

logger = logging.getLogger(__name__)


def _serialize_promo(promo) -> dict:
    """Serialize ONLY the fields the marketplace badge + windowing rule need.

    discount_value is stored as a string so the "fixed" badge ("-{value} off")
    renders byte-identical to the old in-loop `f"-{promo.discount_value} off"`
    (where discount_value was a Decimal). Dates are ISO strings or None.
    """
    return {
        "promo_type": promo.promo_type,
        "discount_value": str(promo.discount_value),
        "days": list(promo.days or []),
        "time_start": promo.time_start or "",
        "time_end": promo.time_end or "",
        "active_from": promo.active_from.isoformat() if promo.active_from else None,
        "active_until": promo.active_until.isoformat() if promo.active_until else None,
    }


def recompute_tenant_promos(tenant) -> None:
    """Recompute and persist the denormalized promo schedule for one tenant.

    Fetches menu.Promotion (is_active=True) inside the tenant's schema, serializes
    the badge fields to a list ordered by highest discount first (mirroring the old
    `Promotion.objects.filter(is_active=True).order_by("-discount_value")[:5]`
    selection), then updates the PUBLIC Profile.marketplace_promos for that tenant.
    Best-effort: any failure is logged and swallowed so a promo save/delete never
    500s over the denormalization.
    """
    if tenant is None:
        return
    schema_name = getattr(tenant, "schema_name", None)
    try:
        from django_tenants.utils import get_public_schema_name, schema_context

        # Never query Promotion against the public schema (the table isn't there).
        if not schema_name or schema_name == get_public_schema_name():
            return

        with schema_context(schema_name):
            from menu.models import Promotion
            # Same ordering the view selected on: highest discount first. The view
            # capped at [:5]; preserve that so selection is identical (the badge
            # only ever uses the first live entry).
            promos = [
                _serialize_promo(p)
                for p in Promotion.objects.filter(is_active=True).order_by("-discount_value")[:5]
            ]

        with schema_context(get_public_schema_name()):
            from tenancy.models import Profile
            Profile.objects.filter(tenant=tenant).update(marketplace_promos=promos)

        # The public marketplace/directory listing caches its (cross-tenant)
        # response keyed by a global version. Bump it so a promo change shows
        # immediately instead of waiting out the list-cache TTL. Imported lazily to
        # avoid an import cycle (menu must not import accounts at module load).
        # Best-effort — a bust failure must never break the promo save.
        from accounts.views import _bust_public_list_cache
        _bust_public_list_cache()
    except Exception:
        # Denormalization is best-effort — never break a promo save/delete over it.
        logger.exception(
            "Failed to recompute denormalized promos for tenant schema=%s", schema_name
        )
