from django.db import connection
from rest_framework.throttling import SimpleRateThrottle


class _IPThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class OrderHandoffThrottle(_IPThrottle):
    scope = "order_handoff"


class CheckoutIntentThrottle(_IPThrottle):
    scope = "checkout_intent"


class AnalyticsEventThrottle(_IPThrottle):
    scope = "analytics_events"


class PlaceOrderThrottle(_IPThrottle):
    scope = "place_order"


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
