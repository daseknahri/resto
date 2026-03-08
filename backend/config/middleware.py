import re

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_tenant_domain_model


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in getattr(settings, "CORS_ALLOWED_ORIGINS", []):
        return True
    for pattern in getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", []):
        if re.match(pattern, origin):
            return True
    return False


def _set_cors_headers(response, request):
    origin = request.META.get("HTTP_ORIGIN", "")
    if _origin_allowed(origin):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        response["Vary"] = "Origin"
    if request.method == "OPTIONS":
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        request_headers = request.META.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "")
        if request_headers:
            response["Access-Control-Allow-Headers"] = request_headers
    return response


class TenantAwareMainMiddleware(TenantMainMiddleware):
    """Tenant middleware with actionable JSON responses for invalid tenant hosts."""

    def _not_found_response(self, request, *, detail: str, code: str, host: str, status_code: int):
        payload = {
            "detail": detail,
            "code": code,
            "host": host,
            "hint": "Provision tenant/domain first and ensure host maps to an existing tenant domain.",
        }
        response = JsonResponse(payload, status=status_code)
        return _set_cors_headers(response, request)

    @staticmethod
    def _is_public_host(hostname: str) -> bool:
        return hostname in {"localhost", "127.0.0.1"}

    def process_request(self, request):
        connection.set_schema_to_public()
        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            return self._not_found_response(
                request,
                detail="Invalid host header.",
                code="invalid_host",
                host=request.META.get("HTTP_HOST", ""),
                status_code=404,
            )

        domain_model = get_tenant_domain_model()
        try:
            tenant = self.get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            if self._is_public_host(hostname):
                connection.set_schema_to_public()
                self.setup_url_routing(request, force_public=True)
                return
            status_code = 200 if request.method == "OPTIONS" else 404
            return self._not_found_response(
                request,
                detail="No tenant found for this host.",
                code="tenant_not_found",
                host=hostname,
                status_code=status_code,
            )

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        self.setup_url_routing(request)
