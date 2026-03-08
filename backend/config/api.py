from django.db import connection
from django.http import JsonResponse
from django.utils.timezone import now


def health_view(request):
    tenant = getattr(request, "tenant", None)
    return JsonResponse(
        {
            "status": "ok",
            "time": now().isoformat(),
            "schema": connection.schema_name,
            "tenant": {
                "id": getattr(tenant, "id", None),
                "slug": getattr(tenant, "slug", None),
                "name": getattr(tenant, "name", None),
            }
            if tenant
            else None,
        }
    )
