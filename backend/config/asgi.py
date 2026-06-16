import asyncio
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.sentry import init_sentry

init_sentry()

# Standard Django HTTP app (created before importing anything that touches the app
# registry / models).
django_asgi_app = get_asgi_application()


class BoundedHTTPMiddleware:
    """Hard timeout on HTTP requests only — websockets and SSE streams are exempt.

    WEBSOCKET SAFETY: the guard on scope["type"] == "http" is mandatory. Wrapping
    the entire ProtocolTypeRouter (or the websocket branch) with asyncio.wait_for
    would cancel long-lived order-update consumers after `timeout` seconds, breaking
    live order tracking. By checking the scope type first we only bound synchronous
    HTTP requests; WebSocket connections (and lifespan events) are never touched.

    SSE STREAM SAFETY: OrderTrackingView (GET /api/marketplace/track/<order>/?stream=1)
    returns a StreamingHttpResponse whose generator polls for up to 90 seconds.
    Applying wait_for to this path would cancel the stream at `timeout` seconds —
    well before the natural 90-second deadline — returning a 500 to the client.
    Paths that start with SSE_EXEMPT_PREFIXES are passed through without a timeout.

    Timeout is tunable via HTTP_REQUEST_TIMEOUT env var (default 120 s). 120 s is
    deliberately above the 90-second SSE deadline so that even non-exempt paths
    (regular API calls) have comfortable headroom. Set to 0 to disable entirely
    (useful for debugging slow management-command-driven requests).
    """

    # Paths whose responses are long-lived HTTP streams (SSE). These must never
    # be wrapped with asyncio.wait_for because the stream outlives any reasonable
    # per-request timeout. Add any future streaming endpoints here.
    SSE_EXEMPT_PREFIXES = ("/api/marketplace/track/",)

    def __init__(self, app, timeout: int = 120):
        self.app = app
        self.timeout = timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.timeout > 0:
            path = scope.get("path", "")
            if any(path.startswith(prefix) for prefix in self.SSE_EXEMPT_PREFIXES):
                # Long-lived SSE stream — bypass the timeout entirely.
                await self.app(scope, receive, send)
                return
            await asyncio.wait_for(self.app(scope, receive, send), timeout=self.timeout)
        else:
            await self.app(scope, receive, send)


# HTTP_REQUEST_TIMEOUT must be comfortably above the longest-lived HTTP response
# the server emits. OrderTrackingView SSE streams run for up to 90 seconds, so
# the default is 120 s. The SSE path is also explicitly exempted in
# BoundedHTTPMiddleware.SSE_EXEMPT_PREFIXES as a belt-and-braces guard.
_http_timeout = int(os.environ.get("HTTP_REQUEST_TIMEOUT", "120"))

try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter

    from realtime.middleware import TenantScopeMiddleware
    from realtime.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            # BoundedHTTPMiddleware wraps only the http branch; websockets are
            # never passed through it — see class docstring for why this matters.
            "http": BoundedHTTPMiddleware(django_asgi_app, timeout=_http_timeout),
            # Host → tenant resolution, then session auth, then route to a consumer.
            "websocket": TenantScopeMiddleware(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            ),
        }
    )
except Exception:
    # Channels not installed / not configured → serve HTTP only. WS clients simply
    # fail to connect and fall back to polling.
    application = BoundedHTTPMiddleware(django_asgi_app, timeout=_http_timeout)
