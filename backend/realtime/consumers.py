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
def _check_order_ownership(tenant, order_number, session_customer_id, delivery_code_claim):
    """Return True if the connecting client is allowed to track this order.

    OPS-5-D: SECURITY gate — mirrors CustomerOrderStatusView ownership logic.

    Gate rules (any one sufficient):
      1. The order exists AND the session customer_id matches order.customer_id.
         This covers every customer who placed the order while logged in.
      2. The order exists AND the caller presents the correct delivery_code.
         This covers delivery orders where the customer shares a tracking link
         that embeds the code, and is intentionally a low-entropy secret
         (12-char alphanumeric, generated at order time).
      3. The order exists AND order.customer_id is null (anonymous / dine-in
         order with no linked account).  The order number itself is the
         credential for anonymous flows, mirroring the AllowAny HTTP endpoint.

    Residual risk (documented):
      - Order numbers are short (sequential / low entropy) and this endpoint is
        unauthenticated.  An attacker who can enumerate order numbers and who
        connects from a browser that has never placed an order (no session
        customer_id) can subscribe to an anonymous order's status stream.  The
        stream carries only status-change pings (no PII), so the practical
        impact is low.  The mitigation is: for orders WITH a linked customer
        (customer_id set), the session gate enforces ownership strictly.
      - delivery_code is 12 chars (alphanumeric), giving ~62^12 ≈ 3×10^21
        combinations — brute-force infeasible in practice.
    """
    if tenant is None or not order_number:
        return False
    from django_tenants.utils import schema_context
    from menu.models import Order

    try:
        with schema_context(tenant.schema_name):
            order = Order.objects.filter(order_number=order_number).only(
                "id", "customer_id", "delivery_code"
            ).first()
    except Exception:
        return False

    if order is None:
        return False

    # Rule 3: anonymous order — no linked customer account, order number is credential.
    if not order.customer_id:
        return True

    # Rule 1: session customer_id matches.
    if session_customer_id is not None:
        try:
            if int(session_customer_id) == int(order.customer_id):
                return True
        except (TypeError, ValueError):
            pass

    # Rule 2: delivery_code presented and matches (non-empty codes only).
    if delivery_code_claim and order.delivery_code:
        if str(delivery_code_claim).strip() == order.delivery_code:
            return True

    return False


class CustomerOrderConsumer(AsyncJsonWebsocketConsumer):
    """Guest channel for a single order's live status (the customer tracking page).

    OPS-5-D: Ownership gate applied at connect time.

    Auth context available in scope
    --------------------------------
    The ASGI stack is: TenantScopeMiddleware → AuthMiddlewareStack → URLRouter.
    AuthMiddlewareStack wraps Django's SessionMiddleware, so scope["session"] is
    a populated Django session dict by the time connect() is called.  We read
    session["customer_id"] from it (the same key that PlaceOrderView writes when
    it links an order to a Customer).

    Gate (any one sufficient — see _check_order_ownership docstring):
      1. session customer_id == order.customer_id   (logged-in customer who owns the order)
      2. ?delivery_code=<code> query-string claim == order.delivery_code   (link-sharing)
      3. order.customer_id is null   (anonymous / dine-in with no platform account)

    Rejection: close with code 4403 (consistent with OwnerConsumer).

    Residual risk
    -------------
    Anonymous orders (order.customer_id is null, e.g. dine-in walk-ins) are
    accessible to anyone who knows the order_number.  Order numbers are short
    and sequential, so an attacker can enumerate them.  The stream carries
    only low-sensitivity status pings (no PII such as name/phone/address), so
    the practical impact is limited to observing the kitchen status of a
    stranger's dine-in order.  Mitigating this fully would require either:
      (a) linking ALL orders to a customer account (breaks anonymous dine-in
          without a forced sign-up), or
      (b) replacing sequential order numbers with unguessable tokens.
    Both are product-level decisions outside the scope of this fix.  The gate
    as implemented is the strongest correct gate possible without changing the
    ordering flow.
    """

    async def connect(self):
        tenant = self.scope.get("tenant")
        order_number = (self.scope.get("url_route", {}).get("kwargs", {}) or {}).get("order_number", "")

        # Read session customer_id — AuthMiddlewareStack populates scope["session"].
        session = self.scope.get("session") or {}
        try:
            session_customer_id = session.get("customer_id")
        except Exception:
            session_customer_id = None

        # Optional delivery_code from the WebSocket query string.
        # Clients embed it as ws://.../<order_number>/?delivery_code=<code>
        query_string = (self.scope.get("query_string") or b"").decode("latin1")
        delivery_code_claim = None
        if query_string:
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(query_string)
                codes = qs.get("delivery_code", [])
                if codes:
                    delivery_code_claim = codes[0]
            except Exception:
                pass

        allowed = await _check_order_ownership(
            tenant, order_number, session_customer_id, delivery_code_claim
        )
        if not allowed:
            await self.close(code=4403)
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
