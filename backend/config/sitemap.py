"""
sitemap_view
------------
Serves GET /sitemap.xml on the PUBLIC schema host so search engines can discover
the SPA storefront. Without a sitemap, crawlers cannot enumerate the client-side
routes of the Vue SPA (there are no server-rendered <a> trails to follow).

The sitemap lists two groups of URLs:

  1. Static public pages — the marketing / discovery routes that always exist
     and are indexable (home, browse, directory, privacy, terms, contact). The
     reservation form (/reserve) is intentionally excluded: the SPA marks it
     noindex,nofollow (it is a personal/transactional form), so advertising it
     here would be a self-contradictory crawl signal.
  2. Live tenant storefronts — one URL per ACTIVE, directory-opted-in,
     menu-published tenant, pointing at the public marketplace storefront path
     ``/order/<slug>``. This mirrors the tenant-visibility rules used by the
     public DirectoryView / MarketplaceView (only ``lifecycle_status="active"``
     tenants are discoverable; suspended / canceled tenants drop out).

Host derivation is server-authoritative (NOT the spoofable Host header): we
prefer the configured BRAND_DOMAIN / PUBLIC_MENU_BASE_URL / TENANT_DOMAIN_SUFFIX
and only fall back to the request host (relative-ish) in dev when nothing is
configured.

Resilience: the whole sitemap must never 500 because of one bad tenant row.
Tenant enumeration is wrapped so a single failing row is skipped, and a total
failure degrades to "static pages only" rather than an error response.
"""

from urllib.parse import urlparse
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse

# Static public SPA routes that should always appear in the sitemap. These match
# the LandingLayout / CustomerLayout public routes in the Vue router and the
# Allow: rules in frontend/public/robots.txt. Every path here MUST be indexable
# on the SPA side (its route name in INDEXABLE_ROUTE_NAMES, see
# frontend/src/composables/useSeoMeta.js) — otherwise the sitemap would list a
# URL whose own page emits noindex. /reserve is a noindex form and is therefore
# deliberately omitted.
STATIC_PUBLIC_PATHS = (
    "/",
    "/browse",
    "/directory",
    "/privacy",
    "/terms",
    "/contact",
)

# Short cache so a freshly-published / suspended tenant shows up (or drops out)
# within the hour without hammering the cross-schema query on every crawl hit.
SITEMAP_CACHE_SECONDS = 3600


def _canonical_host(request) -> str:
    """Server-authoritative host for the sitemap (never trusts Host header in prod).

    Order: BRAND_DOMAIN → PUBLIC_MENU_BASE_URL → TENANT_DOMAIN_SUFFIX. Falls back
    to the request host only when nothing is configured (dev), so local runs still
    produce usable absolute URLs.
    """
    brand = (getattr(settings, "BRAND_DOMAIN", "") or "").strip()
    if brand:
        return brand.split("://")[-1].split("/")[0].split(":")[0]

    pub = (getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "").strip()
    if pub:
        host = urlparse(pub if "://" in pub else f"https://{pub}").hostname
        if host:
            return host

    suffix = (getattr(settings, "TENANT_DOMAIN_SUFFIX", "") or "").strip()
    if suffix:
        return suffix

    # Dev fallback only — there is no configured canonical host.
    try:
        return request.get_host().split(":")[0]
    except Exception:
        return "localhost"


def _base_url(host: str) -> str:
    """http:// for localhost dev, https:// everywhere else."""
    if host == "localhost" or host.endswith(".localhost"):
        return f"http://{host}"
    return f"https://{host}"


def _tenant_storefront_paths() -> list[str]:
    """Return ``/order/<slug>`` for each discoverable tenant.

    Mirrors DirectoryView visibility: ACTIVE lifecycle, opted into the directory,
    menu published. Resilient — never raises; a bad row is skipped and a total
    failure yields an empty list (static pages still ship).
    """
    paths: list[str] = []
    try:
        from tenancy.models import Profile

        rows = (
            Profile.objects
            .filter(
                directory_opt_in=True,
                is_menu_published=True,
                tenant__lifecycle_status="active",
            )
            .select_related("tenant")
            .order_by("tenant__name")
        )
        for profile in rows.iterator():
            try:
                slug = getattr(profile.tenant, "slug", None)
                if slug:
                    paths.append(f"/order/{slug}")
            except Exception:
                # One bad tenant row must not break the whole sitemap.
                continue
    except Exception:
        # Cross-schema query failed entirely → degrade to static-only sitemap.
        return []
    return paths


def _render_sitemap(base_url: str, paths) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in paths:
        loc = escape(f"{base_url}{path}")
        parts.append(f"  <url><loc>{loc}</loc></url>")
    parts.append("</urlset>")
    return "\n".join(parts)


def sitemap_view(request):
    host = _canonical_host(request)
    base_url = _base_url(host)

    paths = list(STATIC_PUBLIC_PATHS)
    paths.extend(_tenant_storefront_paths())

    xml = _render_sitemap(base_url, paths)

    response = HttpResponse(xml, content_type="application/xml")
    response["Cache-Control"] = f"public, max-age={SITEMAP_CACHE_SECONDS}"
    return response
