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
Cached for 10 minutes per (host, path) key via django.core.cache.
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
        try:
            host = request.get_host()  # honours X-Forwarded-Host when trusted
        except Exception:
            host = request.META.get("HTTP_HOST", "localhost")

        # ── 3. Cache look-up ──────────────────────────────────────────────────
        cache_key = f"ogpage:{host}:{path}"
        cached = cache.get(cache_key)
        if cached is not None:
            resp = HttpResponse(cached, content_type="text/html; charset=utf-8")
            resp["Cache-Control"] = "public, max-age=600"
            return resp

        # ── 4. Resolve tenant ─────────────────────────────────────────────────
        icon_url = f"https://{host}/icon-512.png"
        title = "Kepoli"
        description = "Order food, shop local, send packages and book rides — one app, one wallet."
        image = icon_url

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
        canonical_url = f"https://{host}{path}"
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
