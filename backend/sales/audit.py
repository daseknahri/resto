import logging
from typing import Any

from django.conf import settings

from .models import AdminAuditLog

logger = logging.getLogger(__name__)


def get_request_ip(request) -> str | None:
    """Return the real client IP, trusted-proxy-aware.

    Architecture assumption: a single Nginx/Coolify reverse proxy sits in front
    of Django. The rightmost IP in X-Forwarded-For is the one that proxy saw
    (i.e. the last hop we trust). We skip TRUSTED_PROXY_COUNT IPs from the
    right (default 1 for the single-proxy setup) to arrive at the client IP.

    Override via settings.TRUSTED_PROXY_COUNT (int, default 1).
    - TRUSTED_PROXY_COUNT=0 disables XFF processing entirely (bare Django).
    - TRUSTED_PROXY_COUNT=2 for a two-proxy chain (load-balancer + app-proxy).

    Without a proxy, falls back to REMOTE_ADDR.
    Client-supplied leading XFF entries are intentionally ignored: a client can
    forge them, but it cannot forge the rightmost entry added by our proxy.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        trusted_count = max(0, int(getattr(settings, "TRUSTED_PROXY_COUNT", 1)))
        if trusted_count == 0:
            # Admin has disabled XFF processing — use REMOTE_ADDR only.
            return request.META.get("REMOTE_ADDR")
        ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        if ips:
            # The proxy appended the real client IP at the end; skip the last
            # trusted_count entries (those are our own proxy hops) to find it.
            # With a single proxy (count=1) the client IP is at index -1.
            idx = len(ips) - trusted_count
            if idx >= 0:
                return ips[idx]
            # More proxy-count than IPs (mis-config or bare internal call);
            # use the first available entry as a best-effort fallback.
            return ips[0]
    return request.META.get("REMOTE_ADDR")


def log_admin_action(
    *,
    action: str,
    request=None,
    actor=None,
    tenant=None,
    lead=None,
    target_repr: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write audit entries without breaking business flow if logging fails."""
    resolved_actor = actor
    if resolved_actor is None and request is not None:
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            resolved_actor = user

    ip_address = get_request_ip(request) if request is not None else None
    try:
        AdminAuditLog.objects.create(
            action=action,
            actor=resolved_actor,
            tenant=tenant,
            lead=lead,
            target_repr=target_repr or "",
            ip_address=ip_address,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to persist admin audit log for action=%s", action)
