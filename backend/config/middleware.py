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
        # OPS-5-A: tag every Sentry event with the resolved tenant so errors
        # are attributable to a specific restaurant. No-op when sentry_sdk is
        # absent or not yet initialised (DSN was not configured).
        try:
            import sentry_sdk
            sentry_sdk.set_tag("tenant_slug", getattr(tenant, "slug", None))
            sentry_sdk.set_tag("tenant_id", getattr(tenant, "id", None))
        except Exception:
            pass


class CrossTenantSessionGuardMiddleware:
    """AUTHZ-1 backstop: a staff identity is only valid on its own tenant's host.

    The session cookie is scoped to the parent domain, so an authenticated
    tenant-owner/staff session rides along to EVERY tenant subdomain. Each
    owner/staff endpoint is supposed to re-check ``user.tenant_id ==
    request.tenant.id`` by hand — the Z-report leak and the order-status IDOR
    both happened where that line was forgotten. This middleware makes the
    check structural: on a tenant host, a tenant-bound user whose ``tenant_id``
    does not match the request's tenant is DOWNGRADED to anonymous for this
    request. Views then fail closed through their normal auth checks; a
    forgotten per-view guard becomes a 401/403, not a leak.

    Deliberately a downgrade, not a 403: the same human may legitimately
    browse another restaurant's public pages as a guest while logged in as
    staff of their own restaurant (the shared cookie makes that the common
    case, not an attack).

    Scope notes:
    - Platform superadmins are exempt — they operate across tenants by design.
    - A tenant-bound role with ``tenant_id=None`` is also downgraded
      (fail-closed: such a user owns no tenant, so it has no business holding
      staff identity on any tenant host). Logged distinctly for triage.
    - Customers are unaffected: customer identity lives in
      ``request.session["customer_id"]``, never in ``request.user``.
    - The session is NOT flushed — the same browser session may carry a
      customer identity for this tenant, and the staff login stays fully
      valid on its own subdomain.
    - Covers everything behind Django/DRF SessionAuthentication (which reads
      ``request.user`` set here). WS consumers authenticate separately.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_tenant_host(request) -> bool:
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            # Public/main host: TenantAwareMainMiddleware never sets request.tenant.
            return False
        from django_tenants.utils import get_public_schema_name

        return getattr(tenant, "schema_name", None) != get_public_schema_name()

    def __call__(self, request):
        if self._is_tenant_host(request):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                from accounts.models import User

                # is_superuser bypass matches the existing guards
                # (_is_tenant_owner, IsPlatformAdmin): a createsuperuser
                # account carries the DEFAULT role (tenant_owner) with no
                # tenant, and must keep working across tenant hosts.
                tenant_bound = not getattr(user, "is_superuser", False) and getattr(
                    user, "role", None
                ) in (
                    User.Roles.TENANT_OWNER,
                    User.Roles.TENANT_STAFF,
                )
                if tenant_bound and user.tenant_id != request.tenant.id:
                    request_logger.warning(
                        "cross_tenant_session_downgraded",
                        extra={
                            "structured": {
                                "event": "cross_tenant_session_downgraded",
                                "user_id": user.id,
                                "user_role": user.role,
                                "user_tenant_id": user.tenant_id,
                                "request_tenant_id": request.tenant.id,
                                "method": request.method,
                                "path": request.path,
                            }
                        },
                    )
                    from django.contrib.auth.models import AnonymousUser

                    request.user = AnonymousUser()
        return self.get_response(request)


class RequestLoggingMiddleware:
    """Emit structured request logs with tenant/user context and request IDs."""

    # Query-param names whose VALUES are secrets/PII and must never reach app logs or
    # Sentry breadcrumbs. The driver cash-out ?code= is a 6-digit bearer credential
    # (menu/views.py OwnerDriverCashoutLookupView) and the order-lookup ?phone= is
    # customer PII (menu/views.py). Matched case-insensitively.
    SENSITIVE_QUERY_PARAMS = frozenset({
        "code", "phone", "token", "credential", "delivery_code",
        "password", "secret", "otp",
    })
    _REDACTED = "***"

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _host(request) -> str:
        try:
            return request.get_host()
        except Exception:
            return request.META.get("HTTP_HOST", "")

    @classmethod
    def _safe_path(cls, request) -> str:
        """request.path plus a query string with sensitive values redacted.

        Replaces get_full_path() so secrets/PII in the query string (?code=, ?phone=,
        ?token=, …) never land in logs, while keeping benign params for debuggability.
        Preserves key order and repeated keys; redacts the VALUE only, never the key.
        """
        from urllib.parse import parse_qsl, urlencode

        path = request.path
        try:
            raw_qs = request.META.get("QUERY_STRING", "") or ""
            if not raw_qs:
                return path
            pairs = parse_qsl(raw_qs, keep_blank_values=True)
            redacted = [
                (key, cls._REDACTED if key.lower() in cls.SENSITIVE_QUERY_PARAMS else value)
                for key, value in pairs
            ]
            qs = urlencode(redacted)
            return f"{path}?{qs}" if qs else path
        except Exception:
            # Never let log scrubbing break the request; fall back to the bare path
            # (which carries no query string, so it leaks nothing).
            return path

    @staticmethod
    def _client_ip(request) -> str:
        """Return the real client IP using the same trusted-proxy logic as sales.audit.

        Reads TRUSTED_PROXY_COUNT from settings (default 1 for single Nginx proxy).
        Uses the rightmost-minus-count entry from X-Forwarded-For so a client
        cannot spoof it by prepending fake IPs.
        """
        from django.conf import settings as _cfg
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            trusted_count = max(0, int(getattr(_cfg, "TRUSTED_PROXY_COUNT", 1)))
            if trusted_count == 0:
                return request.META.get("REMOTE_ADDR", "")
            ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
            if ips:
                idx = len(ips) - trusted_count
                if idx >= 0:
                    return ips[idx]
                # OPS-5c item 5: count exceeds XFF length — fall back to
                # REMOTE_ADDR, not XFF[0] (which is client-spoofable).
                return request.META.get("REMOTE_ADDR", "")
        return request.META.get("REMOTE_ADDR", "")

    def __call__(self, request):
        request_id = (request.META.get("HTTP_X_REQUEST_ID", "") or "").strip() or uuid.uuid4().hex
        request.request_id = request_id
        # R15: stamp the per-request request_id onto the Sentry scope so a Sentry 5xx can
        # be pivoted straight to its structured "http_request" log line (same request_id),
        # cutting MTTR. Guarded: a no-op when sentry_sdk is absent / Sentry isn't
        # initialised (DSN unset in dev/tests), so it never crashes the request. The tenant
        # tag is already set in TenantAwareMainMiddleware (OPS-5-A) — not duplicated here.
        try:
            import sentry_sdk
            sentry_sdk.set_tag("request_id", request_id)
        except Exception:
            pass
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
                        "path": self._safe_path(request),
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
