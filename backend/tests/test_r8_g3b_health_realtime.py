"""RUN8 G3b W5 — health endpoint (A-49) + platform-admin realtime (A-51).

Health (A-49):
  * /api/health/ stays public (uptime monitors call it without credentials) but
    ``schema`` and ``tenant`` are returned only to authenticated callers.
  * Per-IP throttle (HealthThrottle, scope "health", 60/min in
    config/rest_framework.py) — the throttle test patches the rate to 3/min on
    the CLASS (see note below).
  * The 200/503 policy is unchanged (503 only when the DB check fails).

Realtime (A-51):
  * AdminConsumer (ws/admin) is IsPlatformAdmin-gated: anonymous and
    non-admin sockets are rejected with 4403, mirroring OwnerConsumer.
  * broadcast_admin_event() delivers to every connected admin socket.
  * The AdminRides force-resolve action publishes ``ride.updated`` to the
    admin group — proven end-to-end (HTTP POST -> live socket receipt).

Run on the laptop (from the repo root):
  .\\.venv\\Scripts\\python.exe -m pytest tests/test_r8_g3b_health_realtime.py -q -p no:cacheprovider

Consumer tests are TransactionTestCase (not TestCase): the consumer resolves
the user via database_sync_to_async in a thread, which cannot see TestCase's
uncommitted transaction. CHANNEL_LAYERS is overridden to InMemoryChannelLayer
so no Redis is needed.

Two staging fixes (2026-11-15, first run failed 4/11):
  * Throttle rate: DRF binds SimpleRateThrottle.THROTTLE_RATES at import time
    (``THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES`` on the class),
    so override_settings(REST_FRAMEWORK=...) can NEVER change the rate for an
    already-imported throttle class — the probe showed the rate stayed 60/min
    inside the override. The test therefore patches the rate on the class
    with patch.dict(HealthThrottle.THROTTLE_RATES, ...) instead.
  * Consumer tests are ``async def`` (not sync tests with per-call
    async_to_sync): each async_to_sync() call runs on a FRESH event loop that
    is closed when the call returns, so the app task created by the first
    connect() call is cancelled before receive/disconnect run (loop
    closed=True in the traceback). One async test method = one loop for the
    whole connect -> broadcast -> receive -> disconnect flow. Sync helpers
    (ORM, test Client, broadcast_admin_event's internal async_to_sync) run
    via sync_to_async.
  * Force-resolve POST goes through APIRequestFactory + force_authenticate
    (not the test Client): the HTTP tenant middleware 404s the test Client's
    ``testserver`` host ("No tenant found for this host"), so the view is
    never reached. The middleware behaviour is out of scope for this test.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.auth import AuthMiddlewareStack
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, RideRequest, User
from accounts.throttles import HealthThrottle
from config.api import health_view
from realtime import broadcast as realtime_broadcast
from realtime import consumers as realtime_consumers
from realtime.middleware import TenantScopeMiddleware
from realtime.routing import websocket_urlpatterns

# In-memory channel layer for every test in this file (no Redis needed).
INMEMORY_CHANNELS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def _make_admin(username="w5-admin"):
    return User.objects.create_user(
        username=username, password="x", role=User.Roles.PLATFORM_SUPERADMIN
    )


def _make_plain_user(username="w5-user"):
    return User.objects.create_user(
        username=username, password="x", role=User.Roles.TENANT_OWNER
    )


def _make_ride():
    rider = Customer.objects.create(phone="+212600000001")
    return RideRequest.objects.create(
        rider=rider,
        pickup_lat=33.5,
        pickup_lng=-7.5,
        dropoff_lat=33.6,
        dropoff_lng=-7.6,
        distance_km=5.0,
        fare=Decimal("10.00"),
        status=RideRequest.Status.SEARCHING,
    )


def _tenant():
    # request.tenant as the tenant middleware would set it on a tenant host.
    return SimpleNamespace(id=3, slug="kepoli", name="Kepoli")


class HealthViewTests(TestCase):
    """A-49: auth-gating of schema/tenant + 200/503 policy."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/health/")
        if user is not None:
            force_authenticate(req, user=user)
        if tenant is not None:
            req.tenant = tenant
        return health_view(req)

    def test_anonymous_gets_coarse_payload_only(self):
        resp = self._get(tenant=_tenant())
        self.assertEqual(resp.status_code, 200)
        # Coarse status surface stays public for uptime monitors.
        self.assertIn(resp.data["status"], ("ok", "degraded"))
        self.assertEqual(
            set(resp.data["checks"]),
            {"db", "cache", "celery", "channel_layer", "media"},
        )
        self.assertIn("time", resp.data)
        # ...but no tenant identity and no DB schema name for anonymous probers.
        self.assertNotIn("schema", resp.data)
        self.assertNotIn("tenant", resp.data)

    def test_authenticated_gets_schema_and_tenant(self):
        admin = _make_admin()
        resp = self._get(user=admin, tenant=_tenant())
        self.assertEqual(resp.status_code, 200)
        self.assertIn("schema", resp.data)
        self.assertEqual(
            resp.data["tenant"], {"id": 3, "slug": "kepoli", "name": "Kepoli"}
        )

    def test_authenticated_without_tenant_gets_tenant_null(self):
        # Public host: no tenant resolved, but the schema is still shown.
        admin = _make_admin()
        resp = self._get(user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("schema", resp.data)
        self.assertIsNone(resp.data["tenant"])

    def test_db_down_returns_503_down(self):
        with patch(
            "config.api._check_db", return_value={"ok": False, "latency_ms": None}
        ):
            resp = self._get()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data["status"], "down")
        # Still coarse-only for anonymous callers, even when down.
        self.assertNotIn("schema", resp.data)
        self.assertNotIn("tenant", resp.data)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class HealthThrottleTests(TestCase):
    """A-49: the public endpoint is throttled per IP (rate patched to 3/min)."""

    def setUp(self):
        # Belt & braces: drop any throttle history left by other tests so the
        # 3/min bucket starts empty (the distinct REMOTE_ADDR below already
        # isolates this bucket, but a shared cache must never flake the count).
        from django.core.cache import cache

        cache.clear()

    def test_throttle_returns_429_after_limit(self):
        # NOTE: override_settings(REST_FRAMEWORK=...) does NOT change the rate:
        # DRF binds THROTTLE_RATES on the throttle class at import time, so the
        # patched dict below is the only way to lower the rate in-test.
        with patch.dict(HealthThrottle.THROTTLE_RATES, {"health": "3/min"}):
            factory = APIRequestFactory()
            statuses = []
            for _ in range(4):
                # Distinct REMOTE_ADDR: this bucket is independent of the
                # 127.0.0.1 history built up by HealthViewTests in the same process.
                resp = health_view(factory.get("/api/health/", REMOTE_ADDR="10.9.9.9"))
                statuses.append(resp.status_code)
        self.assertEqual(statuses[:3], [200, 200, 200])
        self.assertEqual(statuses[3], 429)


@override_settings(CHANNEL_LAYERS=INMEMORY_CHANNELS)
class AdminConsumerTests(TransactionTestCase):
    """A-51: AdminConsumer auth gate + broadcast receipt."""

    def setUp(self):
        self.application = TenantScopeMiddleware(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        )

    @staticmethod
    def _session_headers(user):
        from django.test import Client

        client = Client()
        client.force_login(user)
        sessionid = client.cookies["sessionid"].value
        return [(b"cookie", f"sessionid={sessionid}".encode())]

    async def _communicator(self, user=None):
        headers = []
        if user is not None:
            headers = await sync_to_async(self._session_headers)(user)
        return WebsocketCommunicator(self.application, "/ws/admin/", headers=headers)

    async def test_admin_can_connect(self):
        admin = await sync_to_async(_make_admin)()
        communicator = await self._communicator(user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_non_admin_is_rejected_4403(self):
        user = await sync_to_async(_make_plain_user)()
        communicator = await self._communicator(user=user)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_anonymous_is_rejected_4403(self):
        communicator = await self._communicator(user=None)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_broadcast_admin_event_reaches_admin_socket(self):
        admin = await sync_to_async(_make_admin)()
        communicator = await self._communicator(user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        try:
            sent = await sync_to_async(realtime_broadcast.broadcast_admin_event)(
                "ride.updated",
                {"ride_id": 7, "status": "cancelled", "resolved": "cancelled"},
            )
            self.assertTrue(sent)
            message = await communicator.receive_json_from()
            self.assertEqual(message["event"], "ride.updated")
            self.assertEqual(message["payload"]["ride_id"], 7)
            self.assertEqual(message["payload"]["status"], "cancelled")
        finally:
            await communicator.disconnect()

    def test_admin_group_constant_matches_broadcast(self):
        # consumers.ADMIN_GROUP and broadcast.ADMIN_GROUP must name the same
        # group or publishers and subscribers silently miss each other.
        self.assertEqual(realtime_consumers.ADMIN_GROUP, realtime_broadcast.ADMIN_GROUP)
        self.assertEqual(realtime_consumers.ADMIN_GROUP, "platform.admin")


@override_settings(
    CHANNEL_LAYERS=INMEMORY_CHANNELS,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ForceResolvePublishesTests(TransactionTestCase):
    """A-51: the AdminRides force-resolve action publishes to ws/admin."""

    async def test_force_resolve_broadcasts_ride_updated_to_admin_socket(self):
        from accounts.ride_views import AdminRideForceResolveView

        admin = await sync_to_async(_make_admin)()
        ride = await sync_to_async(_make_ride)()

        headers = await sync_to_async(AdminConsumerTests._session_headers)(admin)
        communicator = WebsocketCommunicator(
            TenantScopeMiddleware(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            ),
            "/ws/admin/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        try:
            # APIRequestFactory + force_authenticate: the test Client's
            # "testserver" host is rejected by the HTTP tenant middleware
            # ("No tenant found for this host"), so the view is called
            # directly — the middleware behaviour is out of scope here.
            def _do_post():
                factory = APIRequestFactory()
                req = factory.post(
                    f"/api/admin/rides/{ride.id}/force-resolve/",
                    data={"action": "cancel", "reason": "stuck test"},
                    format="json",
                )
                force_authenticate(req, user=admin)
                return AdminRideForceResolveView.as_view()(req, ride_id=ride.id)

            resp = await sync_to_async(_do_post)()
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data["resolved"], "cancelled")

            message = await communicator.receive_json_from()
            self.assertEqual(message["event"], "ride.updated")
            self.assertEqual(message["payload"]["ride_id"], ride.id)
            self.assertEqual(message["payload"]["status"], "cancelled")
            self.assertEqual(message["payload"]["resolved"], "cancelled")
        finally:
            await communicator.disconnect()

    # Keep get_channel_layer import used (broadcast path sanity in async ctx).
    def test_channel_layer_override_is_inmemory(self):
        self.assertEqual(
            get_channel_layer().__class__.__name__, "InMemoryChannelLayer"
        )
