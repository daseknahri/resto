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


class StaffOrderListThrottle(_IPThrottle):
    scope = "staff_order_list"
