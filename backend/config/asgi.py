import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.sentry import init_sentry

init_sentry()

# Standard Django HTTP app (created before importing anything that touches the app
# registry / models).
django_asgi_app = get_asgi_application()

try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter

    from realtime.middleware import TenantScopeMiddleware
    from realtime.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            # Host → tenant resolution, then session auth, then route to a consumer.
            "websocket": TenantScopeMiddleware(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            ),
        }
    )
except Exception:
    # Channels not installed / not configured → serve HTTP only. WS clients simply
    # fail to connect and fall back to polling.
    application = django_asgi_app
