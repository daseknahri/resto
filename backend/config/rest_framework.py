REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "sales.throttles.PublicLeadThrottle",
        "sales.throttles.UserLeadsThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "public_leads": "100/hour",
        "user_leads": "1000/hour",
        "order_handoff": "120/hour",
        "checkout_intent": "60/hour",
        "analytics_events": "600/hour",
        "auth_login_burst": "8/min",
        "auth_login_sustained": "50/day",
        "auth_activation": "20/hour",
        "auth_password_reset_request": "8/hour",
        "auth_password_reset_confirm": "20/hour",
    },
    "EXCEPTION_HANDLER": "config.exceptions.exception_handler",
}


