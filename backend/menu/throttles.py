from django.db import connection
from rest_framework.throttling import SimpleRateThrottle


class _IPThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        # OPS-5d C: uvicorn runs with --proxy-headers, so DRF's get_ident()
        # trusts X-Forwarded-For unboundedly — an attacker can rotate XFF[0] to
        # reset the per-IP bucket every request.  Use get_request_ip (rightmost-
        # minus-TRUSTED_PROXY_COUNT with a REMOTE_ADDR fallback) so the key is
        # tied to the real client IP our proxy saw.  Fall back to get_ident only
        # if get_request_ip yields nothing (e.g. no REMOTE_ADDR in a test stub).
        # Lazy import (matching PlaceOrderThrottle's lazy model import) to avoid
        # pulling sales.models in at app-init / throttle-module import time.
        from sales.audit import get_request_ip

        ident = get_request_ip(request) or self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class OrderHandoffThrottle(_IPThrottle):
    scope = "order_handoff"


class CheckoutIntentThrottle(_IPThrottle):
    scope = "checkout_intent"


class AnalyticsEventThrottle(SimpleRateThrottle):
    """OPS-5c item 7: analytics ingestion throttle keyed on (tenant_schema, ip).

    AnalyticsEventIngestView is AllowAny and called from every menu page view.
    A pure IP key collapses all tenants behind a shared-office NAT or CDN into
    one bucket, so a busy restaurant can 429 another restaurant's analytics.

    Mirrors WaiterCallThrottle: key on (schema, ip) so each restaurant gets its
    own independent 600/hour bucket.  Falls back to IP-only if the schema is not
    available (public-host requests are rejected by the view anyway).
    """

    scope = "analytics_events_tenant"

    def get_cache_key(self, request, view):
        schema = ""
        try:
            schema = getattr(getattr(connection, "tenant", None), "schema_name", "") or ""
        except Exception:
            pass

        ip = self.get_ident(request)
        if schema:
            ident = f"{schema}:{ip}"
        else:
            ident = ip
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PlaceOrderThrottle(SimpleRateThrottle):
    """OPS-4 G: per-user for authenticated staff/owner, IP for anonymous customers.

    Staff place orders via the waiter app from devices that share a NAT IP.
    Keying on IP means all devices in a restaurant share one bucket, so a
    burst of waiter-created orders can 429 the legitimate customer checkout
    on the same network.  Authenticated TENANT_STAFF/OWNER requests key on
    user.pk; anonymous customer checkouts fall back to the standard IP key.
    """

    scope = "place_order"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            from accounts.models import User as _U
            if getattr(user, "role", None) in (_U.Roles.TENANT_OWNER, _U.Roles.TENANT_STAFF):
                pk = getattr(user, "pk", None) or getattr(user, "id", None)
                if pk is not None:
                    return self.cache_format % {
                        "scope": self.scope,
                        "ident": f"user:{pk}",
                    }
        # Anonymous customers → IP-based (standard behaviour)
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class StaffOrderListThrottle(SimpleRateThrottle):
    """OPS-3 contract G: scoped per authenticated user, not per IP.

    A restaurant's 5 devices share one NAT IP — keying on IP means every
    poll from every device consumes the same bucket, causing 429 bursts on
    reconnect.  Authenticated staff/owner endpoints should key on user.pk so
    each user gets their own independent bucket.  Anonymous requests fall
    back to IP (standard get_ident behaviour).
    """

    scope = "staff_order_list"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            pk = getattr(user, "pk", None) or getattr(user, "id", None)
            if pk is not None:
                return self.cache_format % {
                    "scope": self.scope,
                    "ident": f"user:{pk}",
                }
        # Fallback: anonymous callers → IP-based (standard behaviour)
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class WaiterCallThrottle(SimpleRateThrottle):
    """OPS-3 contract G: scoped per (tenant-schema + table_slug), not per IP.

    AllowAny, so there is no user to key on.  IP-based throttling collapses
    all tables in a restaurant behind one NAT IP into a single bucket — one
    busy table's flood of presses can 429 every other table.  Keying on
    (schema, table_slug) gives each physical table its own independent limit.

    The table_slug is read from the POST body; if absent we fall back to IP.
    The tenant schema_name is taken from the DB connection's tenant attribute
    (set by django-tenants middleware before the view runs).
    """

    scope = "waiter_call"

    def get_cache_key(self, request, view):
        table_slug = None
        # Body may not be parsed yet on throttle check — use request.data
        # which DRF has already parsed at this point.
        try:
            table_slug = (
                str(request.data.get("table") or request.data.get("table_slug") or "").strip()
                or None
            )
        except Exception:
            pass

        schema = ""
        try:
            schema = getattr(getattr(connection, "tenant", None), "schema_name", "") or ""
        except Exception:
            pass

        if table_slug and schema:
            return self.cache_format % {
                "scope": self.scope,
                "ident": f"tbl:{schema}:{table_slug}",
            }

        # Fallback: IP-based (no tenant or no table_slug in body yet)
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
