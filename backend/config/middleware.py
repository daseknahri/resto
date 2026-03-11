import re
import time
import uuid
import logging

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_tenant_domain_model

request_logger = logging.getLogger("app.request")


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
        normalized = (hostname or "").strip().lower().split(":", 1)[0]
        return normalized in set(getattr(settings, "PUBLIC_SCHEMA_HOSTS", []))

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
        if not getattr(tenant, "is_active", True):
            status_code = 200 if request.method == "OPTIONS" else 423
            return self._not_found_response(
                request,
                detail="Tenant is inactive. Contact support to reactivate your account.",
                code="tenant_inactive",
                host=hostname,
                status_code=status_code,
            )
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        self.setup_url_routing(request)


class RequestLoggingMiddleware:
    """Emit structured request logs with tenant/user context and request IDs."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _host(request) -> str:
        try:
            return request.get_host()
        except Exception:
            return request.META.get("HTTP_HOST", "")

    @staticmethod
    def _client_ip(request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def __call__(self, request):
        request_id = (request.META.get("HTTP_X_REQUEST_ID", "") or "").strip() or uuid.uuid4().hex
        request.request_id = request_id
        started_at = time.perf_counter()
        response = None
        raised = False

        try:
            response = self.get_response(request)
            return response
        except Exception:
            raised = True
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            tenant = getattr(request, "tenant", None)
            user = getattr(request, "user", None)
            is_authenticated = bool(getattr(user, "is_authenticated", False))
            status_code = getattr(response, "status_code", 500 if raised else 0)
            log_level = logging.INFO
            if status_code >= 500:
                log_level = logging.ERROR
            elif status_code >= 400:
                log_level = logging.WARNING

            request_logger.log(
                log_level,
                "http_request",
                extra={
                    "structured": {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.get_full_path(),
                        "status": status_code,
                        "duration_ms": duration_ms,
                        "host": self._host(request),
                        "client_ip": self._client_ip(request),
                        "tenant_id": getattr(tenant, "id", None),
                        "tenant_slug": getattr(tenant, "slug", None),
                        "schema_name": getattr(tenant, "schema_name", None),
                        "user_id": getattr(user, "id", None) if is_authenticated else None,
                        "user_role": getattr(user, "role", None) if is_authenticated else None,
                    }
                },
            )

            if response is not None:
                response["X-Request-ID"] = request_id
