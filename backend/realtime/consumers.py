"""WebSocket consumers.

OwnerConsumer is a per-tenant real-time channel for owner/staff. It carries only
low-sensitivity "something changed" pings (e.g. ``order.new``); the client reacts
by refetching over the authenticated HTTP API, so no customer PII ever crosses
the socket. Authorisation mirrors menu.permissions.IsTenantEditorOrReadOnly so a
logged-in *customer* on the same host can never join the owner channel.
"""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .groups import tenant_group


@database_sync_to_async
def _is_tenant_staff(user, tenant):
    # Reuse the exact same rule as the HTTP edit permission — one source of truth,
    # so socket auth can never drift from API auth. (DB access — user.role etc.)
    from menu.permissions import user_can_edit_tenant

    return user_can_edit_tenant(user, tenant)


class OwnerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        tenant = self.scope.get("tenant")
        user = self.scope.get("user")
        if not await _is_tenant_staff(user, tenant):
            await self.close(code=4403)  # unauthorized / wrong tenant
            return
        self.group = tenant_group(tenant.schema_name, "owner")
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def broadcast_message(self, message):
        # Group → socket. Only forward the server-authored event + payload.
        await self.send_json({"event": message.get("event"), "payload": message.get("payload", {})})

    async def receive_json(self, content, **kwargs):
        # Client → server is not trusted for fan-out; ignore (sockets are receive-only).
        return


@database_sync_to_async
def _order_exists(tenant, order_number):
    if tenant is None or not order_number:
        return False
    from django_tenants.utils import schema_context

    from menu.models import Order

    try:
        with schema_context(tenant.schema_name):
            return Order.objects.filter(order_number=order_number).exists()
    except Exception:
        return False


class CustomerOrderConsumer(AsyncJsonWebsocketConsumer):
    """Guest channel for a single order's live status (the customer tracking page).

    No login: the order number is the access credential — exactly as for the
    AllowAny HTTP order-status endpoint, so this exposes nothing extra. Scoped to
    the tenant + order, and receive-only. Carries low-sensitivity status pings.
    """

    async def connect(self):
        tenant = self.scope.get("tenant")
        order_number = (self.scope.get("url_route", {}).get("kwargs", {}) or {}).get("order_number", "")
        if not await _order_exists(tenant, order_number):
            await self.close(code=4404)  # unknown order / tenant
            return
        self.group = tenant_group(tenant.schema_name, f"order.{order_number}")
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def broadcast_message(self, message):
        await self.send_json({"event": message.get("event"), "payload": message.get("payload", {})})

    async def receive_json(self, content, **kwargs):
        return
