import logging
from typing import Any

from .models import AdminAuditLog

logger = logging.getLogger(__name__)


def get_request_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
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
