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
