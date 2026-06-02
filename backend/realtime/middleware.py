"""Channels middleware that resolves the django-tenants tenant from the WebSocket
Host header and attaches it to the scope, mirroring how the HTTP
TenantAwareMainMiddleware resolves tenants by host. A socket whose host doesn't
map to a tenant gets ``tenant=None`` and is rejected by the consumer.
"""
from channels.db import database_sync_to_async


def _host_from_scope(scope):
    for name, value in scope.get("headers", []) or []:
        if name == b"host":
            try:
                return value.decode("latin1").split(":", 1)[0].strip().lower()
            except Exception:
                return ""
    return ""


@database_sync_to_async
def _resolve_tenant(host):
    if not host:
        return None
    from django.db import connection
    from django_tenants.utils import get_tenant_domain_model

    connection.set_schema_to_public()
    try:
        domain = get_tenant_domain_model().objects.select_related("tenant").get(domain=host)
        return domain.tenant
    except Exception:
        return None


class TenantScopeMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["tenant"] = await _resolve_tenant(_host_from_scope(scope))
        return await self.inner(scope, receive, send)
