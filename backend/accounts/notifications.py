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


def create_customer_notification(
    *,
    customer_id,
    title: str,
    body: str = "",
    url: str = "",
    type: str = "",  # noqa: A002 — mirrors the model field name
    vertical: str = "general",
) -> None:
    """Persist ONE customer-facing inbox row mirroring an outbound push event.

    Called alongside ``record_notification`` at the customer push call-sites in
    accounts.push so a missed/denied/backgrounded Web Push is no longer lost — the
    inbox is the durable, deep-linkable source of truth (Careem/Grab pattern), push is
    just the delivery channel. Same title/body/url as the push.

    Writes in the PUBLIC schema (the model lives there, like CustomerPushSubscription) so
    it is correct off the request path. Best-effort: any failure is swallowed so it can
    never break (or slow to breaking) the notification path it instruments.
    """
    if not customer_id or not title:
        return
    try:
        from django_tenants.utils import schema_context
        from .models import CustomerNotification

        with schema_context("public"):
            CustomerNotification.objects.create(
                customer_id=int(customer_id),
                title=str(title)[:160],
                body=str(body)[:400],
                url=str(url)[:300],
                type=str(type)[:40],
                vertical=str(vertical or "general")[:12],
            )
    except Exception:  # noqa: BLE001 — the inbox must never break the caller
        logger.debug("create_customer_notification failed (non-fatal)", exc_info=True)
