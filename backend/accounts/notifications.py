"""
record_notification — write a single NotificationLog row for an outbound notification
attempt. Best-effort: any failure here is swallowed so it can never break (or slow to the
point of breaking) the notification path it instruments.

Used by the web-push / SMS / email / WhatsApp dispatch functions across the app.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def record_notification(
    *,
    channel: str,
    event: str = "",
    status: str = "sent",
    recipient: str = "",
    detail: str = "",
    reference: str = "",
    error: str = "",
    tenant_id=None,
    schema_name: str = "",
) -> None:
    """Persist one notification-attempt row. Never raises.

    Pass either ``tenant_id`` directly, or ``schema_name`` to have it resolved to the
    owning tenant (best-effort). Strings are truncated to the model's field limits.
    """
    try:
        from .models import NotificationLog

        if tenant_id is None and schema_name:
            try:
                from tenancy.models import Tenant
                tenant_id = (
                    Tenant.objects.filter(schema_name=schema_name)
                    .values_list("id", flat=True)
                    .first()
                )
            except Exception:
                tenant_id = None

        NotificationLog.objects.create(
            channel=str(channel)[:12],
            event=str(event)[:40],
            status=str(status)[:10],
            recipient=str(recipient)[:120],
            detail=str(detail)[:200],
            reference=str(reference)[:40],
            error=str(error)[:300],
            tenant_id=tenant_id,
        )
    except Exception:  # noqa: BLE001 — auditing must never break the caller
        logger.debug("record_notification failed (non-fatal)", exc_info=True)
