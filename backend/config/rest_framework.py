import os as _os

_DEBUG = _os.getenv("DJANGO_DEBUG", "False") == "True"

# In production:
#   • Only SessionAuthentication — no BasicAuth (avoids credential exposure over
#     plain HTTP and prevents API brute-forcing with static credentials).
#   • Only JSONRenderer — no browsable HTML API (reduces attack surface and
#     prevents CSRF-via-browsable-form in multi-tenant contexts).
_auth_classes = ["rest_framework.authentication.SessionAuthentication"]
if _DEBUG:
    _auth_classes.append("rest_framework.authentication.BasicAuthentication")

_renderer_classes = ["rest_framework.renderers.JSONRenderer"]
if _DEBUG:
    _renderer_classes.append("rest_framework.renderers.BrowsableAPIRenderer")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": _auth_classes,
    "DEFAULT_RENDERER_CLASSES": _renderer_classes,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # No global default throttle — customer-facing read endpoints (menu browsing,
    # order status polling, session checks) are called many times per minute on
    # shared restaurant WiFi and must not be rate-limited by IP.  Security-sensitive
    # endpoints declare their own throttle_classes explicitly.
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "public_leads": "100/hour",
        "user_leads": "1000/hour",
        "order_handoff": "120/hour",
        "checkout_intent": "60/hour",
        "place_order": "60/hour",
        "order_status": "300/hour",
        "auth_login_burst": "8/min",
        "auth_login_sustained": "50/day",
        "auth_activation": "20/hour",
        "auth_password_reset_request": "8/hour",
        "auth_password_reset_confirm": "20/hour",
        "customer_otp_request": "6/hour",
        "customer_otp_verify": "20/hour",
        "customer_email_otp_request": "6/hour",
        "customer_email_otp_verify": "20/hour",
        "customer_google_auth": "20/hour",
        "customer_profile_update": "30/hour",
        "staff_order_list": "300/min",
        "marketplace_order": "60/hour",
        "marketplace_order_status": "300/hour",
        "marketplace_browse": "120/min",
        "translate": "30/hour",
        "waiter_call": "10/min",
        "wallet_transfer": "20/hour",
        "driver_position": "60/min",
        "driver_status": "30/min",
        "driver_accept": "30/min",
        "delivery_tracking": "120/min",
        "reservation_availability": "240/hour",
        "waitlist_join": "20/hour",
        "ride_estimate": "120/hour",
        "ride_request": "30/hour",
        "ride_driver": "60/min",
        "admin_pii": "120/min",
        # OPS-5c item 7: driver doc uploads — 8 MB per submit + admin email each time
        "driver_doc_upload": "10/hour",
        # OPS-5c item 7: analytics ingestion keyed per (tenant, ip) — see AnalyticsEventThrottle
        "analytics_events_tenant": "600/hour",
    },
    "EXCEPTION_HANDLER": "config.exceptions.exception_handler",
}


