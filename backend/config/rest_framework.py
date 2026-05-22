REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
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
        "analytics_events": "600/hour",
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
    },
    "EXCEPTION_HANDLER": "config.exceptions.exception_handler",
}


