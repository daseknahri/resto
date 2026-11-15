"""Fire-and-forget broadcast helper used from the (sync) HTTP request path.

Channels is imported lazily *inside* the function so this module is always safe
to import — if channels isn't installed or no layer is configured, ``broadcast``
is a logged no-op and the caller is never affected. Payloads should be
low-sensitivity "something changed" pings; clients refetch details over the
authenticated HTTP API rather than trusting data pushed over the socket.
"""
import logging

logger = logging.getLogger(__name__)


# A-51 (RUN8 G3b): the platform-admin group (ws/admin). Fixed name, NOT
# tenant-scoped — platform admins span tenants; membership is gated by
# AdminConsumer's IsPlatformAdmin check. Must stay in sync with
# realtime.consumers.ADMIN_GROUP.
ADMIN_GROUP = "platform.admin"


def broadcast_admin_event(event, payload=None):
    """Send ``{event, payload}`` to the platform-admin group. Returns True if
    handed off to the channel layer, False if skipped (no layer / error).
    Never raises — realtime must never break the HTTP caller.

    Payloads are low-sensitivity pings (ids + statuses, no customer PII);
    admin clients refetch details over the authenticated HTTP API.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return False
        async_to_sync(layer.group_send)(
            ADMIN_GROUP,
            {"type": "broadcast.message", "event": str(event), "payload": payload or {}},
        )
        return True
    except Exception as exc:  # pragma: no cover - realtime must never break callers
        logger.debug("admin broadcast skipped (%s): %s", event, exc)
        return False


def broadcast(schema_name, channel, event, payload=None):
    """Send ``{event, payload}`` to a tenant-scoped group. Returns True if handed
    off to the channel layer, False if skipped (no layer / error). Never raises."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from .groups import tenant_group

        layer = get_channel_layer()
        if layer is None:
            return False
        async_to_sync(layer.group_send)(
            tenant_group(schema_name, channel),
            {"type": "broadcast.message", "event": str(event), "payload": payload or {}},
        )
        return True
    except Exception as exc:  # pragma: no cover - realtime must never break callers
        logger.debug("realtime broadcast skipped (%s/%s): %s", schema_name, channel, exc)
        return False
