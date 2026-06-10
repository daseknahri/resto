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


class _CustomerThrottle(SimpleRateThrottle):
    """Throttle per signed-in customer/driver (session customer_id), falling back to IP."""

    def get_cache_key(self, request, view):
        try:
            cid = request.session.get("customer_id")
        except Exception:
            cid = None
        ident = f"c{cid}" if cid else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class DriverPositionThrottle(_CustomerThrottle):
    """Cap how fast a driver can post GPS updates (floods the DB + tracking clients)."""
    scope = "driver_position"


class DriverStatusUpdateThrottle(_CustomerThrottle):
    """Cap driver job-status transitions (anti-spam; also brute-force backstop for the code)."""
    scope = "driver_status"


class DriverJobAcceptThrottle(_CustomerThrottle):
    scope = "driver_accept"


class DeliveryTrackingThrottle(_CustomerThrottle):
    """Cap customer delivery-tracking polls (every ~10 s, plus tabs / SSE reconnects)."""
    scope = "delivery_tracking"


class ReservationAvailabilityThrottle(_IPThrottle):
    """Rate-limit public slot-availability polling (a DB-querying AllowAny endpoint)."""
    scope = "reservation_availability"


class WaitlistJoinThrottle(_IPThrottle):
    """Rate-limit public waitlist joins — prevents spam entries."""
    scope = "waitlist_join"


class MarketplaceOrderThrottle(_IPThrottle):
    """Rate-limit marketplace order placement — prevents order flooding and inventory races."""
    scope = "marketplace_order"


class MarketplaceOrderStatusThrottle(_IPThrottle):
    """Rate-limit order-status polling — clients poll every 5–10 s while waiting."""
    scope = "marketplace_order_status"


class MarketplaceBrowseThrottle(_IPThrottle):
    """Rate-limit the public marketplace/directory LISTING endpoints (AllowAny,
    DB-querying) against scraping / amplification. Generous so real browsing is
    never blocked; the response cache makes throttled hits cheap anyway."""
    scope = "marketplace_browse"


class WalletTransferThrottle(SimpleRateThrottle):
    """Rate-limit peer-to-peer wallet transfers, per customer (fallback: IP).

    Money movement is abuse-sensitive: cap how fast one account can fire transfers,
    independent of the feature flag, so a compromised/abused session can't drain a
    wallet in a burst.
    """
    scope = "wallet_transfer"

    def get_cache_key(self, request, view):
        cid = None
        try:
            cid = request.session.get("customer_id")
        except Exception:
            cid = None
        ident = f"c{cid}" if cid else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RideEstimateThrottle(_IPThrottle):
    """Rate-limit ride fare estimates — cheap but spammable."""
    scope = "ride_estimate"


class RideRequestThrottle(_CustomerThrottle):
    """Rate-limit ride creation per customer."""
    scope = "ride_request"


class RideDriverThrottle(_CustomerThrottle):
    """Rate-limit driver ride actions (accept/status)."""
    scope = "ride_driver"


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
