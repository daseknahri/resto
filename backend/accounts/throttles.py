from rest_framework.throttling import SimpleRateThrottle


class _IPThrottle(SimpleRateThrottle):
    """Throttle unauthenticated auth endpoints by client IP."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginBurstThrottle(_IPThrottle):
    scope = "auth_login_burst"


class LoginSustainedThrottle(_IPThrottle):
    scope = "auth_login_sustained"


class ActivationThrottle(_IPThrottle):
    scope = "auth_activation"


class PasswordResetRequestThrottle(_IPThrottle):
    scope = "auth_password_reset_request"


class PasswordResetConfirmThrottle(_IPThrottle):
    scope = "auth_password_reset_confirm"


class CustomerOtpRequestThrottle(_IPThrottle):
    scope = "customer_otp_request"


class CustomerOtpVerifyThrottle(_IPThrottle):
    scope = "customer_otp_verify"


class CustomerEmailOtpRequestThrottle(_IPThrottle):
    scope = "customer_email_otp_request"


class CustomerEmailOtpVerifyThrottle(_IPThrottle):
    scope = "customer_email_otp_verify"


class CustomerGoogleAuthThrottle(_IPThrottle):
    scope = "customer_google_auth"


class CustomerProfileUpdateThrottle(_IPThrottle):
    scope = "customer_profile_update"


class MarketplaceOrderThrottle(_IPThrottle):
    """Rate-limit marketplace order placement — prevents order flooding and inventory races."""
    scope = "marketplace_order"


class MarketplaceOrderStatusThrottle(_IPThrottle):
    """Rate-limit order-status polling — clients poll every 5–10 s while waiting."""
    scope = "marketplace_order_status"


class TranslateThrottle(SimpleRateThrottle):
    """Rate-limit the AI translate endpoint by authenticated user to prevent
    runaway credit consumption against the OpenRouter API."""
    scope = "translate"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            ident = str(user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
