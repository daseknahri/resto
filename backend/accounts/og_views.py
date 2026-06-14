"""
Social-crawler OG endpoint — GET /api/og/

Nginx routes bot user-agents here; real users never see it.
Returns a minimal standalone HTML page with Open Graph + Twitter Card
meta tags so social crawlers (Facebook, Twitter, Slack, etc.) get
rich preview data.

Resolution order
----------------
1. Host header → Domain → Tenant (name / tagline / hero/logo).
2. ?path matches ^/order/([A-Za-z0-9_-]+) → look up Tenant by slug.
3. Platform default ("Kepoli").

Security
--------
All tenant-controlled strings are HTML-escaped before interpolation.
Image/canonical URLs are validated to start with http:// or https://;
anything else falls back to the platform icon.
The ?path param is normalised to start with "/" and is HTML-escaped.

Caching
-------
Cached for 10 minutes per (resolved-tenant-id, sanitised-path) key via
django.core.cache. The inbound Host header is NOT part of the key — it is
spoofable (X-Forwarded-Host), so keying on it would let an attacker fan out
unbounded cache entries for one real page. The cache key is derived from the
authoritatively-resolved tenant id and a length-bounded, sanitised path.
"""

import re

from django.core.cache import cache
from django.http import HttpResponse
from django.utils.html import escape
from django.views import View

# Imported at module level so tests can patch them via accounts.og_views.*
from tenancy.models import Domain, Profile, Tenant  # noqa: E402

_OG_TTL = 600  # seconds (10 min)
_SLUG_RE = re.compile(r"^/order/([A-Za-z0-9_-]+)")
_SAFE_URL_RE = re.compile(r"^https?://")
# Cache-key path bound: a long ?path can't be turned into an unbounded set of
# distinct cache rows for one (tenant) page. The full path is still used in the
# rendered body (escaped); only the KEY component is truncated + sanitised.
_OG_CACHE_PATH_MAX = 128
_OG_CACHE_PATH_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_./?=&%:+~-]")


def _og_cache_key(tenant, path: str) -> str:
    """Build the cache key from the RESOLVED tenant id (not the spoofable Host)
    plus a length-bounded, sanitised path. `tenant` is None for the platform
    fallback (no tenant), which gets its own stable namespace."""
    tid = getattr(tenant, "id", None) if tenant is not None else None
    scope = f"t{tid}" if tid is not None else "platform"
    # Sanitise + bound the path so it can't smuggle weird bytes or balloon the
    # key space. The authoritative content is keyed by tenant id; the path only
    # disambiguates same-tenant variants.
    safe_path = _OG_CACHE_PATH_UNSAFE_RE.sub("_", path)[:_OG_CACHE_PATH_MAX]
    return f"ogpage:{scope}:{safe_path}"


def _safe_url(url: str, fallback: str) -> str:
    """Return url if it starts with http:// or https://, else fallback."""
    if url and _SAFE_URL_RE.match(url):
        return url
    return fallback


def _render_og(*, title: str, description: str, image: str, url: str, path: str) -> str:
    t = escape(title)
    d = escape(description)
    # image and url are already validated safe URLs — escape the value anyway
    # in case the fallback icon URL contains characters that need escaping.
    img = escape(image)
    canon = escape(url)
    path_escaped = escape(path)

    return (
        "<!doctype html>"
        "<html><head>"
        f"<title>{t}</title>"
        '<meta charset="utf-8">'
        '<meta name="robots" content="noindex">'
        '<meta property="og:type" content="website">'
        '<meta property="og:site_name" content="Kepoli">'
        f'<meta property="og:title" content="{t}">'
        f'<meta property="og:description" content="{d}">'
        f'<meta property="og:image" content="{img}">'
        f'<meta property="og:url" content="{canon}">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{t}">'
        f'<meta name="twitter:description" content="{d}">'
        f'<meta name="twitter:image" content="{img}">'
        f'<meta http-equiv="refresh" content="0;url={path_escaped}">'
        "</head>"
        f'<body><a href="{path_escaped}">Continue to {t}</a></body>'
        "</html>"
    )


class OGView(View):
    """GET /api/og/?path=<original-request-uri>

    AllowAny, no session, GET only.  Used exclusively by the nginx
    bot-detection layer — real browsers are never sent here.
    """

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        # ── 1. Normalise path param ───────────────────────────────────────────
        raw_path = (request.GET.get("path") or "").strip()
        if not raw_path.startswith("/"):
            raw_path = "/"
        # "//evil.com" is a protocol-relative URL — the meta-refresh would send
        # a misrouted human off-site. Collapse any leading slash run to one.
        if raw_path.startswith("//"):
            raw_path = "/" + raw_path.lstrip("/")
        path = raw_path  # validated

        # ── 2. Determine host ─────────────────────────────────────────────────
        # request.get_host() honours X-Forwarded-Host (spoofable upstream), so this
        # is used ONLY to look up the tenant — NEVER to key the cache (a spoofed
        # Host could otherwise fan out unbounded cache entries for one real page).
        # The canonical / og:image host below is re-derived from the RESOLVED
        # tenant's authoritative domain so a spoofed Host can't be baked into the
        # preview URLs either.
        try:
            host = request.get_host()
        except Exception:
            host = request.META.get("HTTP_HOST", "localhost")
        # Normalise: lowercase + strip port so equivalent Hosts resolve the same tenant.
        host = (host or "localhost").strip().lower().split(":")[0]

        # ── 3. Resolve tenant (BEFORE the cache look-up, so the key is keyed on the
        #       authoritative tenant id rather than the spoofable inbound Host) ────
        tenant = None
        profile = None

        # Resolution path A: host → Domain → Tenant
        try:
            domain_obj = Domain.objects.select_related("tenant").get(domain=host)
            tenant = domain_obj.tenant
            if not getattr(tenant, "is_active", True):
                tenant = None
        except Exception:
            tenant = None

        # Resolution path B (fallback): slug from /order/<slug>
        if tenant is None:
            m = _SLUG_RE.match(path)
            if m:
                slug = m.group(1)
                try:
                    tenant = Tenant.objects.get(slug=slug, is_active=True)
                except Exception:
                    tenant = None

        # ── 4. Cache look-up — keyed on RESOLVED tenant id + bounded path ──────
        cache_key = _og_cache_key(tenant, path)
        cached = cache.get(cache_key)
        if cached is not None:
            resp = HttpResponse(cached, content_type="text/html; charset=utf-8")
            resp["Cache-Control"] = "public, max-age=600"
            return resp

        # Defaults (used when no tenant / no profile resolved).
        icon_url = f"https://{host}/icon-512.png"
        title = "Kepoli"
        description = "Order food, shop local, send packages and book rides — one app, one wallet."
        image = icon_url

        # Canonical / og:image host — prefer the resolved tenant's authoritative
        # primary domain, and for the no-tenant "platform" fallback use a
        # server-authoritative brand host (NOT the spoofable inbound Host): the
        # OPS-5g cache key collapses all hosts for a path to one "ogpage:platform"
        # row, so a spoofed Host would otherwise be cached and served to everyone
        # (cross-user og:image/canonical poisoning). Falls back to the inbound host
        # only in dev where no brand domain is configured.
        from django.conf import settings as _og_settings
        _brand = (
            getattr(_og_settings, "BRAND_DOMAIN", "")
            or getattr(_og_settings, "PUBLIC_MENU_BASE_URL", "")
            or ""
        ).strip()
        _brand_host = _brand.replace("https://", "").replace("http://", "").strip("/").split("/")[0].lower()
        canonical_host = _brand_host or host
        if tenant is not None:
            try:
                primary = tenant.domains.filter(is_primary=True).first()
                authoritative = getattr(primary, "domain", "") if primary is not None else ""
                if isinstance(authoritative, str) and authoritative.strip():
                    canonical_host = authoritative.strip().lower()
            except Exception:
                canonical_host = host

        # Re-derive the icon fallback from the authoritative host (not the inbound
        # Host header) so the og:image fallback URL can't be pointed off-domain.
        icon_url = f"https://{canonical_host}/icon-512.png"
        if image == f"https://{host}/icon-512.png":
            image = icon_url

        # Build metadata from tenant / profile
        if tenant is not None:
            title = tenant.name  # will be escaped in _render_og
            try:
                profile = Profile.objects.filter(tenant=tenant).first()
            except Exception:
                profile = None

            if profile is not None:
                tagline = getattr(profile, "tagline", "") or ""
                description = tagline if tagline else "Order online — menu, delivery and more."
                hero = getattr(profile, "hero_url", "") or ""
                logo = getattr(profile, "logo_url", "") or ""
                image = _safe_url(hero, None) or _safe_url(logo, None) or icon_url
            else:
                description = "Order online — menu, delivery and more."

        # ── 5. Render ─────────────────────────────────────────────────────────
        # Canonical URL uses the authoritative tenant host, not the inbound Host.
        canonical_url = f"https://{canonical_host}{path}"
        html = _render_og(
            title=title,
            description=description,
            image=image,
            url=canonical_url,
            path=path,
        )

        # ── 6. Cache + respond ────────────────────────────────────────────────
        cache.set(cache_key, html, _OG_TTL)
        resp = HttpResponse(html, content_type="text/html; charset=utf-8")
        resp["Cache-Control"] = "public, max-age=600"
        return resp
