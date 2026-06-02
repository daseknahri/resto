"""End-to-end-ish tests for OwnerConsumer using Channels' in-memory layer.

These exercise the real connect → authorize → join-group → receive-broadcast path
without a database: the tenant/user are injected into the scope (in production the
TenantScopeMiddleware + AuthMiddleware populate them), and the authorization rule
operates on plain attributes, so no DB query happens. Skipped when channels isn't
installed.
"""
import asyncio
import unittest
from types import SimpleNamespace

from django.test import SimpleTestCase

from accounts.models import User

try:
    from channels.layers import get_channel_layer
    from channels.testing import WebsocketCommunicator

    from realtime import consumers as rt_consumers
    from realtime.consumers import CustomerOrderConsumer, OwnerConsumer
    from realtime.groups import tenant_group

    HAS_CHANNELS = True
except Exception:  # pragma: no cover
    HAS_CHANNELS = False


def _scoped_app(extra):
    """Wrap the consumer so the scope carries a pre-resolved tenant/user."""
    app = OwnerConsumer.as_asgi()

    async def application(scope, receive, send):
        scope = dict(scope)
        scope.update(extra)
        return await app(scope, receive, send)

    return application


def _user(**overrides):
    base = dict(
        is_authenticated=True,
        is_superuser=False,
        is_staff=False,
        is_platform_admin=False,
        tenant_id=1,
        role=User.Roles.TENANT_OWNER,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_TENANT = SimpleNamespace(id=1, schema_name="resto_a")


@unittest.skipUnless(HAS_CHANNELS, "channels not installed")
class OwnerConsumerTests(SimpleTestCase):
    def test_authorized_connects_and_receives_tenant_broadcast(self):
        asyncio.run(self._authorized())

    async def _authorized(self):
        comm = WebsocketCommunicator(
            _scoped_app({"tenant": _TENANT, "user": _user()}), "/ws/owner/"
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        # A broadcast to this tenant's owner group must reach the socket.
        await get_channel_layer().group_send(
            tenant_group("resto_a", "owner"),
            {"type": "broadcast.message", "event": "order.new", "payload": {"order_number": "X1"}},
        )
        msg = await comm.receive_json_from(timeout=2)
        self.assertEqual(msg["event"], "order.new")
        self.assertEqual(msg["payload"]["order_number"], "X1")
        await comm.disconnect()

    def test_other_tenant_broadcast_not_received(self):
        asyncio.run(self._isolation())

    async def _isolation(self):
        comm = WebsocketCommunicator(
            _scoped_app({"tenant": _TENANT, "user": _user()}), "/ws/owner/"
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        # Broadcast to a DIFFERENT tenant — must NOT arrive here.
        await get_channel_layer().group_send(
            tenant_group("resto_b", "owner"),
            {"type": "broadcast.message", "event": "order.new", "payload": {"order_number": "Y9"}},
        )
        self.assertTrue(await comm.receive_nothing(timeout=1))
        await comm.disconnect()

    def test_unauthenticated_rejected(self):
        asyncio.run(self._rejected({"tenant": _TENANT, "user": SimpleNamespace(is_authenticated=False)}))

    def test_wrong_tenant_user_rejected(self):
        asyncio.run(self._rejected({"tenant": _TENANT, "user": _user(tenant_id=999)}))

    def test_no_tenant_rejected(self):
        asyncio.run(self._rejected({"tenant": None, "user": _user()}))

    async def _rejected(self, extra):
        comm = WebsocketCommunicator(_scoped_app(extra), "/ws/owner/")
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()


def _order_app(extra):
    app = CustomerOrderConsumer.as_asgi()

    async def application(scope, receive, send):
        scope = dict(scope)
        scope.update(extra)
        return await app(scope, receive, send)

    return application


@unittest.skipUnless(HAS_CHANNELS, "channels not installed")
class CustomerOrderConsumerTests(SimpleTestCase):
    """The DB existence check is patched (no DB in this sandbox); we verify the
    connect/group/broadcast behavior around it."""

    def setUp(self):
        self._orig = rt_consumers._order_exists

        async def _exists_true(tenant, order_number):
            return True

        rt_consumers._order_exists = _exists_true

    def tearDown(self):
        rt_consumers._order_exists = self._orig

    def test_connects_and_receives_status_for_its_order(self):
        asyncio.run(self._ok())

    async def _ok(self):
        extra = {"tenant": _TENANT, "url_route": {"kwargs": {"order_number": "ORD-1"}}}
        comm = WebsocketCommunicator(_order_app(extra), "/ws/order/ORD-1/")
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await get_channel_layer().group_send(
            tenant_group("resto_a", "order.ORD-1"),
            {"type": "broadcast.message", "event": "status", "payload": {"status": "ready"}},
        )
        msg = await comm.receive_json_from(timeout=2)
        self.assertEqual(msg["event"], "status")
        self.assertEqual(msg["payload"]["status"], "ready")
        await comm.disconnect()

    def test_other_order_status_not_received(self):
        asyncio.run(self._isolation())

    async def _isolation(self):
        extra = {"tenant": _TENANT, "url_route": {"kwargs": {"order_number": "ORD-1"}}}
        comm = WebsocketCommunicator(_order_app(extra), "/ws/order/ORD-1/")
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await get_channel_layer().group_send(
            tenant_group("resto_a", "order.ORD-2"),
            {"type": "broadcast.message", "event": "status", "payload": {"status": "ready"}},
        )
        self.assertTrue(await comm.receive_nothing(timeout=1))
        await comm.disconnect()

    def test_rejected_when_order_missing(self):
        async def _exists_false(tenant, order_number):
            return False

        rt_consumers._order_exists = _exists_false
        asyncio.run(self._rejected_missing())

    async def _rejected_missing(self):
        extra = {"tenant": _TENANT, "url_route": {"kwargs": {"order_number": "NOPE"}}}
        comm = WebsocketCommunicator(_order_app(extra), "/ws/order/NOPE/")
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()
