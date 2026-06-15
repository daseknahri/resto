import hashlib
import json
import logging
import math
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import StaticHTMLRenderer

from sales.audit import log_admin_action
from sales.models import AdminAuditLog
from sales.permissions import IsPlatformAdmin
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.openstate import schedule_open_now, tenant_local_now

from .messaging import send_password_reset_email
from .models import Customer
from .throttles import (
    ActivationThrottle,
    AdminPIIThrottle,
    CustomerEmailOtpRequestThrottle,
    CustomerEmailOtpVerifyThrottle,
    CustomerGoogleAuthThrottle,
    CustomerOtpRequestThrottle,
    CustomerOtpVerifyThrottle,
    CustomerProfileUpdateThrottle,
    CustomerReservationsThrottle,
    DeliveryRatingThrottle,
    DeliveryTrackingThrottle,
    EmailUnsubscribeThrottle,
    DriverJobAcceptThrottle,
    DriverPositionThrottle,
    DriverStatusUpdateThrottle,
    MarketplaceBrowseThrottle,
    LoginBurstThrottle,
    LoginSustainedThrottle,
    MarketplaceOrderStatusThrottle,
    MarketplaceOrderThrottle,
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
    StaffChangePasswordThrottle,
    WalletTransferThrottle,
)
try:
    # OPS-5g: the dedicated voucher-redeem throttle (scope "voucher_redeem") lives in
    # accounts.throttles. Imported defensively so this module still loads if the
    # throttle hasn't landed yet — the redeem view always has a working throttle either
    # way (a redeemed voucher code maps straight to wallet credit → brute-force target).
    from .throttles import VoucherRedeemThrottle
except ImportError:  # pragma: no cover - fallback only until the canonical class lands
    from rest_framework.throttling import SimpleRateThrottle

    class VoucherRedeemThrottle(SimpleRateThrottle):
        """Per-signed-in-customer throttle on voucher redemption (fallback: IP)."""
        scope = "voucher_redeem"

        def get_cache_key(self, request, view):
            try:
                cid = request.session.get("customer_id")
            except Exception:
                cid = None
            ident = f"c{cid}" if cid else self.get_ident(request)
            return self.cache_format % {"scope": self.scope, "ident": ident}
from .serializers import (
    ActivationSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)

logger = logging.getLogger("app.customer")


def _parse_coord(value, lo: float, hi: float) -> float | None:
    """Parse a latitude or longitude value, returning None for out-of-range or
    non-finite inputs (inf, NaN) to prevent corrupt coordinates reaching the DB."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if (math.isfinite(f) and lo <= f <= hi) else None


def serialize_user_session(user):
    tenant = getattr(user, "tenant", None)
    # The admin endpoints (OPS-5b/5d) are is_staff-free — they gate on
    # is_superuser / is_platform_admin. Converge this flag onto the same predicate
    # so a staff-only user isn't shown an admin console that would 403 on use.
    can_access_admin_console = bool(user.is_superuser or user.is_platform_admin)
    # Effective permissions: owners and platform-level admins have everything; tenant
    # staff respect their per-account flags. The frontend reads `permissions` to gate
    # waiter-app features, and uses role/`can_edit_tenant_menu` for route access.
    # NOTE: this dict is a UI hint only — server-side enforcement lives in the
    # effective_perm_* methods + DRF permission classes, so dropping is_staff here
    # does not relax any real authorization. (is_staff dropped for consistency.)
    all_access = bool(user.is_tenant_owner or user.is_superuser or user.is_platform_admin)
    perm_manage_orders = bool(all_access or user.perm_manage_orders)
    perm_view_revenue = bool(all_access or user.perm_view_revenue)
    perm_edit_menu = bool(all_access or user.perm_edit_menu)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_platform_admin": user.is_platform_admin,
        "can_access_admin_console": can_access_admin_console,
        "can_edit_tenant_menu": perm_edit_menu,
        "permissions": {
            "manage_orders": perm_manage_orders,
            "view_revenue": perm_view_revenue,
            "edit_menu": perm_edit_menu,
        },
        "tenant": {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.name,
            "is_active": tenant.is_active,
            "lifecycle_status": getattr(tenant, "lifecycle_status", "active"),
        }
        if tenant
        else None,
    }


def _canonical_brand_host() -> str:
    """Server-authoritative host for tenant-less users (e.g. password-reset links).

    NEVER derived from request headers (Host / X-Forwarded-Host are attacker-
    controlled → host-header poisoning of the reset link). Prefer the configured
    public menu base URL host, then the tenant domain suffix; final fallback is a
    safe localhost for dev. Configure PUBLIC_MENU_BASE_URL / TENANT_DOMAIN_SUFFIX
    (or DJANGO_BRAND_DOMAIN) in production so links point at the real frontend.
    """
    from urllib.parse import urlparse as _urlparse
    brand = (getattr(settings, "BRAND_DOMAIN", "") or "").strip()
    if brand:
        return brand.split("://")[-1].split("/")[0].split(":")[0]
    pub = (getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "").strip()
    if pub:
        host = _urlparse(pub if "://" in pub else f"https://{pub}").hostname
        if host:
            return host
    suffix = (getattr(settings, "TENANT_DOMAIN_SUFFIX", "") or "").strip()
    if suffix:
        return suffix
    return "localhost"


def build_frontend_base_url(request, user):
    domain = None
    tenant = getattr(user, "tenant", None)
    if tenant is not None:
        primary = tenant.domains.filter(is_primary=True).first()
        if primary:
            domain = primary.domain

    # OPS-5f: do NOT fall back to request.get_host() — it honours the spoofable
    # Host / X-Forwarded-Host header, so an attacker could poison the password-reset
    # link to point at their own domain and capture the token. Use a configured,
    # server-authoritative canonical host instead.
    if not domain:
        domain = _canonical_brand_host()

    if domain.endswith(".localhost") or domain == "localhost":
        return f"http://{domain}:5173"
    return f"https://{domain}"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ActivationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ActivationThrottle]

    def post(self, request):
        serializer = ActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response({"detail": "Account activated", "user": serialize_user_session(user)}, status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginBurstThrottle, LoginSustainedThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response({"detail": "Signed in", "user": serialize_user_session(user)}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Signed out"}, status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"authenticated": False, "user": None}, status=status.HTTP_200_OK)
        tenant = getattr(request.user, "tenant", None)
        if tenant is not None and not getattr(tenant, "is_active", True):
            logout(request)
            return Response(
                {
                    "authenticated": False,
                    "user": None,
                    "detail": f"Tenant is {getattr(tenant, 'lifecycle_status', 'suspended')}. Contact support.",
                },
                status=status.HTTP_200_OK,
            )
        return Response({"authenticated": True, "user": serialize_user_session(request.user)}, status=status.HTTP_200_OK)


class RepairTenantLinkView(APIView):
    """POST /api/repair-tenant-link/

    Self-service endpoint for a tenant_owner whose tenant FK was NULLed by a
    cascade delete (tenant row deleted then recreated → new PK → old FK gone).

    Safe because:
      1. Requires the user to already be authenticated.
      2. Only works when the user's role is tenant_owner AND tenant FK is NULL.
      3. Only links to the tenant that owns the domain the request arrived on.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != user.Roles.TENANT_OWNER:
            return Response(
                {"detail": "Only tenant owners can use this endpoint.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.tenant_id is not None:
            # Already linked — just return current session so frontend can refresh
            return Response(
                {"detail": "Already linked.", "user": serialize_user_session(user)},
                status=status.HTTP_200_OK,
            )
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Could not resolve tenant from request domain.", "code": "no_tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Check no other owner is already linked to this tenant
        from .models import User as _User
        existing_owner = _User.objects.filter(
            tenant=tenant, role=_User.Roles.TENANT_OWNER
        ).exclude(id=user.id).first()
        if existing_owner:
            return Response(
                {
                    "detail": "Another tenant owner is already linked to this tenant. Contact support.",
                    "code": "conflict",
                },
                status=status.HTTP_409_CONFLICT,
            )
        user.tenant = tenant
        user.save(update_fields=["tenant"])
        logger.info(
            "repair_tenant_link: user %s (id=%s) re-linked to tenant %s (id=%s)",
            user.email, user.id, tenant.schema_name, tenant.id,
        )
        return Response(
            {"detail": "Tenant link repaired.", "user": serialize_user_session(user)},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset = serializer.save()

        if reset is not None:
            base_url = build_frontend_base_url(request, reset.user)
            reset_url = f"{base_url}/reset-password?token={reset.token}"
            send_password_reset_email(reset.user.email, reset_url, reset.token)

            # Helpful for local/dev testing; avoid in production responses.
            if settings.DEBUG:
                return Response(
                    {
                        "detail": "If the account exists, a reset link has been sent.",
                        "debug_reset_url": reset_url,
                    },
                    status=status.HTTP_200_OK,
                )

        return Response({"detail": "If the account exists, a reset link has been sent."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password reset successful. You can now sign in."}, status=status.HTTP_200_OK)


# ── Customer auth helpers ──────────────────────────────────────────────────────


def _serialize_customer(customer: Customer) -> dict:
    return {
        "id": customer.pk,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone or "",
        "phone_verified": customer.phone_verified,
        "email_verified": customer.email_verified,
        "has_google": bool(customer.google_sub),
        "wallet_balance": str(customer.wallet_balance),
        "loyalty_points": customer.loyalty_points or 0,
        "locale": customer.locale or "en",
        "is_driver": bool(customer.is_driver),
        "is_driver_online": bool(customer.is_driver_online),
        "notify_order_updates": bool(customer.notify_order_updates),
        "notify_review_prompts": bool(customer.notify_review_prompts),
        "notify_promotions": bool(customer.notify_promotions),
    }


def _staff_session_conflict(request):
    """Return a 403 Response if a staff/owner User is authenticated on this session.

    Customer-login finalize paths write ``customer_id`` into the Django session. Real
    customers are NOT User rows, so their ``request.user`` is AnonymousUser and this
    returns None for them. But a staff/owner authenticated via SessionAuthentication
    would otherwise layer a customer identity onto their privileged session — refuse it.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return Response(
            {"detail": "Sign out of your staff account first to use a customer login.",
             "code": "staff_session_conflict"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _verify_google_token(credential: str, client_id: str) -> dict | None:
    """Verify a Google ID token using Google's tokeninfo endpoint.

    Returns the decoded payload dict on success, None on failure.
    """
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(credential)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, Exception):
        return None
    # Validate audience when client_id is configured
    if client_id and data.get("aud") != client_id:
        return None
    # Require a sub claim
    if not data.get("sub"):
        return None
    # Require a VERIFIED email. CRITICAL nuance: Google's tokeninfo HTTP endpoint
    # returns email_verified as the STRING "true"/"false" (the library-verified path
    # would return a real bool), so we must accept both forms. Without this an
    # unverified-email Google account could be linked to an existing customer by
    # email and take it over.
    if str(data.get("email_verified")).lower() != "true":
        return None
    return data


def _send_otp_sms(phone: str, code: str) -> bool:
    """Send OTP via Twilio SMS. Returns True on success, False if not configured."""
    try:
        import base64
        import urllib.request as _urlreq
        import urllib.parse as _urlparse

        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")
        if not sid or not token or not from_number:
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        body = f"Your verification code is {code}. Valid for 5 minutes. Do not share it."
        data = _urlparse.urlencode({"To": phone, "From": from_number, "Body": body}).encode()
        creds = base64.b64encode(f"{sid}:{token}".encode()).decode()
        req = _urlreq.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Basic {creds}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with _urlreq.urlopen(req, timeout=10):
            pass
        return True
    except Exception:  # noqa: BLE001
        return False


def _send_otp(phone: str, code: str) -> None:
    """Deliver OTP to the customer's phone via Twilio SMS.

    In DEBUG mode the code is logged to the console so developers can test
    without real credentials. In production a warning is logged if Twilio
    is not yet configured.
    """
    if getattr(settings, "DEBUG", False):
        logger.info("Customer OTP for %s: %s", phone, code)
        return

    sent = _send_otp_sms(phone, code)
    if not sent:
        logger.warning(
            "OTP delivery failed: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / "
            "TWILIO_FROM_NUMBER not configured. Phone ...%s did not receive a code.",
            phone[-4:] if len(phone) >= 4 else "****",
        )


_OTP_CACHE_KEY = "customer_otp:{phone}"
_OTP_TTL = 300  # 5 minutes
_OTP_MAX_ATTEMPTS = 5

# OPS-5h: per-recipient SMS/email toll-fraud guards, independent of the IP throttle.
# A re-request resets the verify attempt counter to 0, so an IP-only throttle leaves a
# single victim phone/email open to a paid-message flood. These cap sends per *recipient*.
_OTP_RESEND_COOLDOWN = 60      # seconds — refuse a re-send within this window
_OTP_RECIPIENT_MAX_PER_HOUR = 5  # hard cap on sends to one recipient per hour
_OTP_RECIPIENT_WINDOW = 3600   # seconds — the per-recipient cap window


def _otp_recipient_guard(recipient: str):
    """Toll-fraud guard for a single OTP recipient (normalized phone / lowercased email).

    Returns a 429 ``Response`` if the recipient is within the resend cooldown or over the
    hourly cap, in which case the caller MUST NOT send and MUST NOT touch the verify-attempt
    counter. Returns ``None`` when a send is allowed; the caller then calls
    :func:`_otp_recipient_mark_sent` after a successful send.

    Independent of the IP-keyed DRF throttle: the throttle limits one *source*, this limits
    one *target*. ``cache.add`` is atomic set-if-absent — it both tests the cooldown and
    arms it in one hop, so two concurrent requests can't both pass.
    """
    cooldown_key = f"otp_cooldown:{recipient}"
    count_key = f"otp_count:{recipient}"
    if (cache.get(count_key) or 0) >= _OTP_RECIPIENT_MAX_PER_HOUR:
        return Response(
            {"detail": "Too many codes requested for this recipient. Please try again later.",
             "code": "otp_rate_limited"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    # cache.add returns False when the key already exists → still inside the cooldown.
    if not cache.add(cooldown_key, "1", _OTP_RESEND_COOLDOWN):
        return Response(
            {"detail": "A code was just sent — please wait a moment before requesting another.",
             "code": "otp_cooldown"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


def _otp_recipient_mark_sent(recipient: str) -> None:
    """Record a successful send for the per-recipient hourly cap. Best-effort."""
    count_key = f"otp_count:{recipient}"
    try:
        cache.set(count_key, (cache.get(count_key) or 0) + 1, _OTP_RECIPIENT_WINDOW)
    except Exception:  # noqa: BLE001 - cap accounting must never break a legit send
        pass


def _rotate_customer_session(request) -> None:
    """Issue a fresh session key right before a customer login finalizes.

    OPS-5h session fixation: staff ``login()`` rotates the session id for us, but the
    customer-login finalizers write ``customer_id`` straight into the existing session.
    With SESSION_COOKIE_DOMAIN shared across all tenant subdomains, a pre-auth / planted
    session id would otherwise survive the privilege jump. ``cycle_key()`` preserves
    session data but reissues the key, so an attacker-known id is invalidated. Guarded so
    it's a no-op when there is no session object.
    """
    session = getattr(request, "session", None)
    if session is not None:
        session.cycle_key()


# ── Customer session ──────────────────────────────────────────────────────────


class CustomerSessionView(APIView):
    """GET: return the current customer session. DELETE: sign out."""

    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"customer": None})
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            request.session.pop("customer_id", None)
            return Response({"customer": None})
        return Response({"customer": _serialize_customer(customer)})

    def delete(self, request):
        request.session.pop("customer_id", None)
        return Response({"ok": True})


# ── Customer phone OTP ────────────────────────────────────────────────────────


class CustomerPhoneRequestView(APIView):
    """Request an OTP for the given phone number."""

    permission_classes = [AllowAny]
    throttle_classes = [CustomerOtpRequestThrottle]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        if not phone:
            return Response({"detail": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(phone) > 30:
            return Response({"detail": "Phone number too long."}, status=status.HTTP_400_BAD_REQUEST)
        import re as _re
        if not _re.match(r'^\+\d{6,}$', phone):
            return Response(
                {"detail": "Phone number must be in E.164 format (e.g. +212612345678).", "code": "invalid_phone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OPS-5h: per-recipient toll-fraud guard (cooldown + hourly cap), independent of
        # the IP throttle. Refuse BEFORE generating/storing a code so a cooled-down or
        # over-cap re-request can't reset the verify attempt counter to 0.
        guard = _otp_recipient_guard(phone)
        if guard is not None:
            return guard

        code = f"{secrets.randbelow(900000) + 100000}"
        cache_key = _OTP_CACHE_KEY.format(phone=phone)
        cache.set(cache_key, {"code": code, "attempts": 0, "expires_at": time.time() + _OTP_TTL}, timeout=_OTP_TTL)
        _send_otp(phone, code)
        _otp_recipient_mark_sent(phone)

        resp = {"ok": True, "detail": "OTP sent. Check your phone."}
        # In DEBUG, include the code in the response so developers can test without SMS
        if getattr(settings, "DEBUG", False):
            resp["debug_code"] = code
        return Response(resp)


class CustomerPhoneVerifyView(APIView):
    """Verify the OTP and create or retrieve the matching Customer, then start a session."""

    permission_classes = [AllowAny]
    throttle_classes = [CustomerOtpVerifyThrottle]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        code = (request.data.get("code") or "").strip()
        name = (request.data.get("name") or "").strip()[:80]

        if not phone or not code:
            return Response(
                {"detail": "Phone and code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conflict = _staff_session_conflict(request)
        if conflict is not None:
            return conflict

        cache_key = _OTP_CACHE_KEY.format(phone=phone)
        data = cache.get(cache_key)
        if data is None:
            return Response(
                {"detail": "OTP expired or not requested. Please request a new code.", "code": "otp_expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data["attempts"] >= _OTP_MAX_ATTEMPTS:
            cache.delete(cache_key)
            return Response(
                {"detail": "Too many incorrect attempts. Please request a new code.", "code": "too_many_attempts"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if data["code"] != code:
            data["attempts"] += 1
            remaining = max(1, int(data.get("expires_at", time.time() + _OTP_TTL) - time.time()))
            cache.set(cache_key, data, timeout=remaining)
            return Response(
                {"detail": "Incorrect code.", "code": "invalid_code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache.delete(cache_key)

        # If the customer is already signed in (e.g. via Google or email), add
        # the verified phone to their existing account rather than creating a new one.
        existing_id = request.session.get("customer_id")
        if existing_id:
            try:
                existing = Customer.objects.get(pk=existing_id)
                # Block if this phone is already owned by a *different* account
                conflict = Customer.objects.filter(phone=phone).exclude(pk=existing_id).first()
                if conflict:
                    return Response(
                        {"detail": "This phone number is already linked to another account.", "code": "phone_taken"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                update_fields = ["phone", "phone_verified", "updated_at"]
                existing.phone = phone
                existing.phone_verified = True
                if not existing.name and name:
                    existing.name = name
                    update_fields.append("name")
                existing.save(update_fields=update_fields)
                return Response({"customer": _serialize_customer(existing)})
            except Customer.DoesNotExist:
                request.session.pop("customer_id", None)  # stale session — fall through

        # No existing session: get or create customer by phone number
        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={"name": name, "phone_verified": True},
        )
        update_fields = ["phone_verified", "updated_at"]
        if not customer.phone_verified:
            customer.phone_verified = True
        if not customer.name and name:
            customer.name = name
            update_fields.append("name")
        if not created:
            customer.save(update_fields=update_fields)

        # OPS-5h: rotate the session id before the privilege jump (session fixation).
        _rotate_customer_session(request)
        request.session["customer_id"] = customer.pk
        return Response({"customer": _serialize_customer(customer)})


# ── Customer Google auth ──────────────────────────────────────────────────────



class CustomerGoogleAuthView(APIView):
    """Verify a Google One-Tap credential and create or retrieve the matching Customer."""

    permission_classes = [AllowAny]
    throttle_classes = [CustomerGoogleAuthThrottle]

    def post(self, request):
        credential = (request.data.get("credential") or "").strip()
        if not credential:
            return Response({"detail": "Google credential is required."}, status=status.HTTP_400_BAD_REQUEST)

        conflict = _staff_session_conflict(request)
        if conflict is not None:
            return conflict

        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "").strip()
        if not client_id:
            return Response(
                {"detail": "Google sign-in is not configured.", "code": "not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        payload = _verify_google_token(credential, client_id)
        if payload is None:
            return Response(
                {"detail": "Invalid or expired Google credential. Please try again.", "code": "invalid_credential"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        google_sub = payload["sub"]
        email = payload.get("email", "").strip()
        name = payload.get("name", "").strip()[:80]

        # 1. Find by google_sub (returning user)
        customer = Customer.objects.filter(google_sub=google_sub).first()

        if customer is None:
            # 2. Find by email (link to phone-authed account)
            if email:
                customer = Customer.objects.filter(email=email).exclude(google_sub__isnull=False).first()

            if customer is not None:
                customer.google_sub = google_sub
                update_fields = ["google_sub", "updated_at"]
                if not customer.name and name:
                    customer.name = name
                    update_fields.append("name")
                customer.save(update_fields=update_fields)
            else:
                # 3. Create new customer
                customer = Customer.objects.create(
                    google_sub=google_sub,
                    email=email,
                    name=name,
                )

        # OPS-5h: rotate the session id before the privilege jump (session fixation).
        _rotate_customer_session(request)
        request.session["customer_id"] = customer.pk
        return Response({"customer": _serialize_customer(customer)})


# ── Customer orders ───────────────────────────────────────────────────────────


class CustomerOrdersView(APIView):
    """Return a paginated list of orders for the current customer session.

    Only runs when a tenant schema is active (i.e. the request is from a
    tenant domain). Returns an empty list when called from the public schema
    because Order lives in tenant schemas, not the public schema.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        # Guard: Order only exists in tenant schemas.
        from django.db import connection
        if connection.schema_name == "public":
            return Response({"orders": [], "count": 0})

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"orders": [], "count": 0})
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            request.session.pop("customer_id", None)
            return Response({"orders": [], "count": 0})

        # Import Order + OrderItem from menu app — cross-app import is intentional here.
        from menu.models import Order, OrderItem

        PAGE_SIZE = 20
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        offset = (page - 1) * PAGE_SIZE
        # Fetch one extra to detect whether a further page exists.
        orders = list(
            Order.objects
            .filter(customer=customer)
            .prefetch_related("items")
            .select_related("rating")   # Rating is a OneToOneField on Order
            .order_by("-created_at")[offset:offset + PAGE_SIZE + 1]
        )
        has_more = len(orders) > PAGE_SIZE
        orders = orders[:PAGE_SIZE]

        result = []
        for order in orders:
            items = [
                {
                    "dish_slug": item.dish_slug,
                    "dish_name": item.dish_name,
                    "unit_price": str(item.unit_price),
                    "qty": item.qty,
                    "note": item.note,
                    "subtotal": str(item.subtotal),
                    "options": item.options or [],
                }
                for item in order.items.all()
            ]
            # Rating is a OneToOneField; accessing it raises RelatedObjectDoesNotExist
            # when absent, so we use getattr with a None default.
            rating = getattr(order, "rating", None)
            result.append({
                "order_number": order.order_number,
                "status": order.status,
                "fulfillment_type": order.fulfillment_type,
                "table_label": order.table_label,
                "total": str(order.total),
                "currency": order.currency,
                "created_at": order.created_at,
                "customer_name": order.customer_name,
                "has_rating": rating is not None,
                "rating_score": rating.score if rating else None,
                "rating": {
                    "score": rating.score,
                    "comment": rating.comment,
                    "created_at": rating.created_at,
                    "owner_reply": rating.owner_reply or "",
                    "owner_reply_at": rating.owner_reply_at.isoformat() if rating.owner_reply_at else None,
                } if rating else None,
                "items": items,
            })

        return Response({"orders": result, "count": len(result), "has_more": has_more, "page": page})


class CustomerMarketplaceOrdersView(APIView):
    """GET /api/customer/orders/all/ — the customer's orders across ALL restaurants.

    Reads the public-schema order index (CustomerOrderRef), so it works from any domain
    (the marketplace or a single restaurant) and returns the full cross-restaurant
    history — unlike CustomerOrdersView which only sees the active tenant's orders.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"orders": [], "count": 0})

        from .models import CustomerOrderRef
        PAGE_SIZE = 20
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        offset = (page - 1) * PAGE_SIZE
        refs = list(
            CustomerOrderRef.objects
            .filter(customer_id=customer_id)
            .order_by("-order_created_at")[offset:offset + PAGE_SIZE + 1]
        )
        has_more = len(refs) > PAGE_SIZE
        refs = refs[:PAGE_SIZE]
        return Response({
            "orders": [
                {
                    "order_number": r.order_number,
                    "restaurant_name": r.restaurant_name,
                    "restaurant_slug": r.restaurant_slug,
                    "status": r.status,
                    "fulfillment_type": r.fulfillment_type,
                    "total": str(r.total),
                    "currency": r.currency,
                    "created_at": r.order_created_at.isoformat() if r.order_created_at else None,
                    "items_snapshot": r.items_snapshot or [],
                }
                for r in refs
            ],
            "count": len(refs),
            "has_more": has_more,
            "page": page,
        })


class CustomerReservationsView(APIView):
    """GET /api/customer/reservations/ — the customer's reservations across all restaurants.

    Matches by email (+ phone fallback) against the Lead table which lives in the
    public schema (sales is a SHARED_APP). Returns only actual booking-type leads
    (booked_for set, excluding provisioning/live/paid tenant-signup leads).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [CustomerReservationsThrottle]

    def get(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"reservations": [], "count": 0})

        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"reservations": [], "count": 0})

        from sales.models import Lead
        from django.db.models import Q as _Q

        q = _Q()
        if customer.email:
            q |= _Q(email=customer.email)
        if customer.phone:
            q |= _Q(phone=customer.phone)
        if not q:
            return Response({"reservations": [], "count": 0})

        qs = list(
            Lead.objects
            .filter(q, booked_for__isnull=False)
            .exclude(status__in=[Lead.Status.PROVISIONING, Lead.Status.LIVE, Lead.Status.PAID])
            .select_related("tenant")
            .order_by("-booked_for")[:50]
        )

        return Response({
            "reservations": [
                {
                    "id": lead.pk,
                    "restaurant_name": lead.tenant.name if lead.tenant_id else "",
                    "restaurant_slug": lead.tenant.slug if lead.tenant_id else "",
                    "booked_for": lead.booked_for.isoformat() if lead.booked_for else None,
                    "party_size": lead.party_size,
                    "status": lead.status,
                    "notes": lead.notes or "",
                    # OPS-5d: cancel_token is intentionally NOT returned — a session holder
                    # could otherwise bulk-harvest cancel UUIDs. Customers cancel via the
                    # emailed link, which carries the token.
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                }
                for lead in qs
            ],
            "count": len(qs),
        })


# ── Customer email OTP ────────────────────────────────────────────────────────


class CustomerEmailRequestView(APIView):
    """Request an OTP sent to the given email address."""
    permission_classes = [AllowAny]
    throttle_classes = [CustomerEmailOtpRequestThrottle]

    def post(self, request):
        from .messaging import send_otp_email
        email = (request.data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return Response({"detail": "A valid email address is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(email) > 254:
            return Response({"detail": "Email too long."}, status=status.HTTP_400_BAD_REQUEST)

        # OPS-5h: per-recipient toll-fraud guard (cooldown + hourly cap), independent of
        # the IP throttle. Refuse BEFORE generating/storing a code so a cooled-down or
        # over-cap re-request can't reset the verify attempt counter to 0.
        guard = _otp_recipient_guard(email)
        if guard is not None:
            return guard

        code = f"{secrets.randbelow(900000) + 100000}"
        cache_key = f"customer_email_otp:{email}"
        cache.set(cache_key, {"code": code, "attempts": 0, "expires_at": time.time() + _OTP_TTL}, timeout=_OTP_TTL)
        send_otp_email(email, code)
        _otp_recipient_mark_sent(email)

        resp = {"ok": True, "detail": "OTP sent. Check your email."}
        if getattr(settings, "DEBUG", False):
            resp["debug_code"] = code
        return Response(resp)


class CustomerEmailVerifyView(APIView):
    """Verify the email OTP and create or retrieve a Customer, then start a session."""
    permission_classes = [AllowAny]
    throttle_classes = [CustomerEmailOtpVerifyThrottle]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        code = (request.data.get("code") or "").strip()
        name = (request.data.get("name") or "").strip()[:80]

        if not email or not code:
            return Response({"detail": "Email and code are required."}, status=status.HTTP_400_BAD_REQUEST)

        conflict = _staff_session_conflict(request)
        if conflict is not None:
            return conflict

        cache_key = f"customer_email_otp:{email}"
        data = cache.get(cache_key)
        if data is None:
            return Response({"detail": "OTP expired or not requested.", "code": "otp_expired"}, status=status.HTTP_400_BAD_REQUEST)
        if data["attempts"] >= _OTP_MAX_ATTEMPTS:
            cache.delete(cache_key)
            return Response({"detail": "Too many incorrect attempts.", "code": "too_many_attempts"}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if data["code"] != code:
            data["attempts"] += 1
            remaining = max(1, int(data.get("expires_at", time.time() + _OTP_TTL) - time.time()))
            cache.set(cache_key, data, timeout=remaining)
            return Response({"detail": "Incorrect code.", "code": "invalid_code"}, status=status.HTTP_400_BAD_REQUEST)

        cache.delete(cache_key)

        # Find by email, or create. Do NOT match google_sub rows (those are already linked).
        customer = Customer.objects.filter(email=email).first()
        if customer is None:
            customer = Customer.objects.create(email=email, name=name, email_verified=True)
        else:
            update_fields = ["email_verified", "updated_at"]
            customer.email_verified = True
            if not customer.name and name:
                customer.name = name
                update_fields.append("name")
            customer.save(update_fields=update_fields)

        # OPS-5h: rotate the session id before the privilege jump (session fixation).
        _rotate_customer_session(request)
        request.session["customer_id"] = customer.pk
        return Response({"customer": _serialize_customer(customer)})


# ── Customer profile update ───────────────────────────────────────────────────


class CustomerProfileUpdateView(APIView):
    """PATCH /api/customer/profile/ — update name, locale, or email for the current customer session."""

    permission_classes = [AllowAny]
    throttle_classes = [CustomerProfileUpdateThrottle]

    def patch(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            request.session.pop("customer_id", None)
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        update_fields = ["updated_at"]

        name = (request.data.get("name") or "").strip()[:80]
        if name:
            customer.name = name
            update_fields.append("name")

        locale = (request.data.get("locale") or "").strip()[:10]
        if locale in ("en", "fr", "ar"):
            customer.locale = locale
            update_fields.append("locale")

        # Notification preferences (customer opt-outs).
        for _pref in ("notify_order_updates", "notify_review_prompts", "notify_promotions"):
            if _pref in request.data:
                setattr(customer, _pref, bool(request.data.get(_pref)))
                update_fields.append(_pref)

        if "email" in request.data:
            email = (request.data.get("email") or "").strip().lower()[:254]
            if email and "@" in email and email != customer.email:
                if Customer.objects.filter(email=email).exclude(pk=customer.pk).exists():
                    return Response(
                        {"detail": "This email is already linked to another account.", "code": "email_taken"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                customer.email = email
                customer.email_verified = False
                update_fields.extend(["email", "email_verified"])
            elif email == "" and customer.email:
                customer.email = ""
                customer.email_verified = False
                update_fields.extend(["email", "email_verified"])

        if len(update_fields) > 1:
            customer.save(update_fields=update_fields)

        return Response({"customer": _serialize_customer(customer)})


# ── Staff management (owner only) ─────────────────────────────────────────────

import re as _re
import secrets as _secrets
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash as _update_session_auth_hash


def _is_tenant_owner(request, tenant) -> bool:
    """Return True if the request user is the owner of the given tenant."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    # OPS-5d: is_staff (Django /admin/ flag) dropped — it is not a business-admin role
    # and let a staff-only account act as owner on ANY tenant (cross-tenant priv-esc).
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    return user.role == user.Roles.TENANT_OWNER


class OwnerStaffListCreateView(APIView):
    """GET /api/owner/staff/ — list staff accounts for this tenant.
       POST /api/owner/staff/ — create a new staff (waiter) account."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from .models import User
        staff = list(
            User.objects.filter(tenant=tenant, role=User.Roles.TENANT_STAFF)
            .order_by("date_joined")
            .values(
                "id", "email", "first_name", "last_name", "username", "date_joined",
                "perm_manage_orders", "perm_view_revenue", "perm_edit_menu",
            )
        )
        staff_ids = [s["id"] for s in staff]

        # Per-staff work stats over a recent window (default 7 days). Orders live in the
        # tenant schema; this owner endpoint runs in tenant context, so Order resolves to
        # this restaurant. Best-effort — never break the staff list over stats.
        try:
            stats_days = max(1, min(90, int(request.query_params.get("stats_days") or 7)))
        except (TypeError, ValueError):
            stats_days = 7
        stats_map = {}
        currency = "MAD"
        if staff_ids:
            try:
                from datetime import timedelta as _td
                from django.utils import timezone as _tz
                from django.db.models import Count as _Count, Sum as _Sum, Max as _Max
                from menu.models import Order as _Order

                since = _tz.now() - _td(days=stats_days)
                rows = (
                    _Order.objects.filter(
                        status=_Order.Status.COMPLETED,
                        status_updated_at__gte=since,
                        handled_by_user_id__in=staff_ids,
                    )
                    .values("handled_by_user_id")
                    .annotate(orders=_Count("id"), revenue=_Sum("total"), last_active=_Max("status_updated_at"))
                )
                for r in rows:
                    stats_map[r["handled_by_user_id"]] = {
                        "orders_handled": r["orders"] or 0,
                        "revenue": str(r["revenue"]) if r["revenue"] is not None else "0.00",
                        "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                    }
                _c = _Order.objects.filter(status=_Order.Status.COMPLETED).values_list("currency", flat=True).first()
                if _c:
                    currency = _c
            except Exception:
                stats_map = {}

        results = [
            {
                "id": s["id"],
                "email": s["email"],
                "name": f"{s['first_name']} {s['last_name']}".strip() or s["username"],
                "username": s["username"],
                "date_joined": s["date_joined"].isoformat() if s["date_joined"] else None,
                "permissions": {
                    "manage_orders": s["perm_manage_orders"],
                    "view_revenue": s["perm_view_revenue"],
                    "edit_menu": s["perm_edit_menu"],
                },
                "stats": stats_map.get(s["id"], {"orders_handled": 0, "revenue": "0.00", "last_active": None}),
            }
            for s in staff
        ]
        return Response({"results": results, "count": len(results), "stats_days": stats_days, "currency": currency})

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        name = (request.data.get("name") or "").strip()
        email = (request.data.get("email") or "").strip().lower()

        if not name or len(name) < 2:
            return Response({"detail": "Name must be at least 2 characters.", "code": "name_required"}, status=status.HTTP_400_BAD_REQUEST)
        if not email or "@" not in email:
            return Response({"detail": "A valid email address is required.", "code": "email_required"}, status=status.HTTP_400_BAD_REQUEST)
        if not _re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            return Response({"detail": "A valid email address is required.", "code": "email_invalid"}, status=status.HTTP_400_BAD_REQUEST)

        from .models import User
        if User.objects.filter(email=email).exists():
            return Response({"detail": "A user with this email already exists.", "code": "email_taken"}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce the per-plan staff-account limit (mirrors the dish limit). 0 = unlimited.
        # Concurrency note: when a limit is set, wrap the count AND create in
        # transaction.atomic() + select_for_update() so concurrent creates queue on the
        # lock and each re-counts before proceeding — preventing two simultaneous requests
        # from both reading the same count and overshooting the cap.
        from django.db import transaction as _tx
        max_staff = int(getattr(getattr(tenant, "plan", None), "max_staff_accounts", 0) or 0)
        _limit_error_response = None
        if max_staff > 0:
            with _tx.atomic():
                # select_for_update() locks the matching rows so the next create cannot
                # start until this transaction commits (i.e. after create_user below).
                current_staff = User.objects.select_for_update().filter(
                    tenant=tenant, role=User.Roles.TENANT_STAFF
                ).count()
                if current_staff >= max_staff:
                    _limit_error_response = Response(
                        {
                            "detail": f"Your plan allows a maximum of {max_staff} staff accounts. "
                                      f"You have {current_staff}. Upgrade to add more.",
                            "code": "staff_limit_reached",
                            "limit": max_staff,
                            "current": current_staff,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if _limit_error_response is None:
                    # Still inside the lock — create the user atomically.
                    # Derive username inside the lock to avoid duplicate-username races too.
                    _base_u = _re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower())[:28] or "staff"
                    _u = _base_u; _c = 1
                    while User.objects.filter(username=_u).exists():
                        _u = f"{_base_u}{_c}"; _c += 1
                    _np = name.split(" ", 1)
                    _fn = _np[0][:30]; _ln = (_np[1] if len(_np) > 1 else "")[:150]
                    _pw = _secrets.token_urlsafe(12)
                    user = User.objects.create_user(
                        username=_u, email=email, password=_pw,
                        first_name=_fn, last_name=_ln,
                        role=User.Roles.TENANT_STAFF, tenant=tenant,
                    )
                    first_name, last_name, temp_password, username = _fn, _ln, _pw, _u
        if _limit_error_response is not None:
            return _limit_error_response
        if max_staff > 0:
            # User was created inside the atomic block above; skip to email + return.
            pass
        else:
            # Unlimited plan: no lock needed.
            # Derive username from email local-part; deduplicate
            base_username = _re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower())[:28] or "staff"
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            # Split name into first / last
            name_parts = name.split(" ", 1)
            first_name = name_parts[0][:30]
            last_name = (name_parts[1] if len(name_parts) > 1 else "")[:150]

            # Generate a temporary password (12 URL-safe chars ≈ 72 bits entropy)
            temp_password = _secrets.token_urlsafe(12)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
                role=User.Roles.TENANT_STAFF,
                tenant=tenant,
            )

        # Email invite
        try:
            from django.core.mail import send_mail as _send_mail
            from django.conf import settings as _cfg

            # Best-effort: find the primary domain for the tenant sign-in URL
            primary_domain = tenant.domains.filter(is_primary=True).values_list("domain", flat=True).first() if tenant else None
            if primary_domain and not primary_domain.startswith("http"):
                if primary_domain.endswith(".localhost") or primary_domain == "localhost":
                    base_url = f"http://{primary_domain}:5173"
                else:
                    base_url = f"https://{primary_domain}"
            else:
                base_url = primary_domain or ""
            join_url = f"{base_url}/waiter/join" if base_url else "/waiter/join"

            _send_mail(
                subject=f"You're invited to the {tenant.name} waiter app",
                message=(
                    f"Hi {first_name},\n\n"
                    f"You've been added as a waiter at {tenant.name}.\n\n"
                    f"Open the link below on your phone to install the app and sign in:\n"
                    f"{join_url}\n\n"
                    f"Your credentials:\n"
                    f"  Email:    {email}\n"
                    f"  Password: {temp_password}\n\n"
                    f"Tip: tap the link in Safari (iOS) or Chrome (Android) for the best install experience.\n\n"
                    f"— {tenant.name}"
                ),
                from_email=_cfg.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception:
            pass

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "name": f"{first_name} {last_name}".strip(),
                "username": user.username,
                "temp_password": temp_password,  # Displayed once so owner can share it
            },
            status=status.HTTP_201_CREATED,
        )


class OwnerStaffDeleteView(APIView):
    """DELETE /api/owner/staff/<staff_id>/ — remove a staff account from this tenant.
       PATCH  /api/owner/staff/<staff_id>/ — update staff permissions."""

    permission_classes = [IsAuthenticated]

    def _get_staff(self, request, staff_id):
        """Return (tenant, staff_user) or raise a Response on error."""
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return None, Response({"detail": "Owner access required.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        from .models import User
        staff_user = User.objects.filter(id=staff_id, tenant=tenant, role=User.Roles.TENANT_STAFF).first()
        if staff_user is None:
            return None, Response({"detail": "Staff member not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        return staff_user, None

    def patch(self, request, staff_id, *args, **kwargs):
        staff_user, err = self._get_staff(request, staff_id)
        if err is not None:
            return err

        permissions = request.data.get("permissions", {})
        if not isinstance(permissions, dict):
            return Response({"detail": "Invalid permissions payload.", "code": "invalid"}, status=status.HTTP_400_BAD_REQUEST)

        allowed = {"manage_orders", "view_revenue", "edit_menu"}
        update_fields = []
        for key, val in permissions.items():
            if key in allowed and isinstance(val, bool):
                setattr(staff_user, f"perm_{key}", val)
                update_fields.append(f"perm_{key}")

        if update_fields:
            staff_user.save(update_fields=update_fields)

        return Response({
            "id": staff_user.id,
            "permissions": {
                "manage_orders": staff_user.perm_manage_orders,
                "view_revenue": staff_user.perm_view_revenue,
                "edit_menu": staff_user.perm_edit_menu,
            },
        })

    def delete(self, request, staff_id, *args, **kwargs):
        staff_user, err = self._get_staff(request, staff_id)
        if err is not None:
            return err

        staff_user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffChangePasswordView(APIView):
    """POST /api/staff/change-password/ — let an authenticated staff (or owner) change
    their own password after verifying the current one.

    Body: { "current_password": "...", "new_password": "..." }

    Rules:
    - Requires a valid session (IsAuthenticated).
    - current_password must match the stored hash.
    - new_password must pass Django's AUTH_PASSWORD_VALIDATORS.
    - On success the session is NOT terminated so the staff member stays logged in
      on the device they just changed their password from (UX choice: they are already
      holding the phone / tablet).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [StaffChangePasswordThrottle]

    def post(self, request, *args, **kwargs):
        user = request.user

        current_password = (request.data.get("current_password") or "").strip()
        new_password = (request.data.get("new_password") or "").strip()

        if not current_password:
            return Response(
                {"detail": "Current password is required.", "code": "current_password_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new_password:
            return Response(
                {"detail": "New password is required.", "code": "new_password_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify current password
        if not user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect.", "code": "wrong_current_password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run Django's AUTH_PASSWORD_VALIDATORS
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages, "code": "password_too_weak"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Keep the session alive after a password change so the staff member
        # stays logged in on this device.
        _update_session_auth_hash(request, user)

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


# ── Customer wallet ────────────────────────────────────────────────────────────

_WALLET_PAY_SALT = "wallet-pay-code"
_WALLET_PAY_TTL = 300  # seconds — the QR rotates every few minutes


class CustomerWalletPayTokenView(APIView):
    """GET /api/customer/wallet/pay-token/ — a short-lived signed token identifying the
    customer, rendered as a QR ("pay code") so a restaurant can scan it to top up the
    customer's wallet without searching by phone. Expires in 5 minutes."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from django.core import signing

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        token = signing.dumps({"cid": customer_id}, salt=_WALLET_PAY_SALT)
        return Response({"token": token, "expires_in": _WALLET_PAY_TTL})


class CustomerWalletChargeRequestsView(APIView):
    """GET /api/customer/wallet/charge-requests/ — pending wallet charges awaiting this
    customer's approval (above-threshold charges a restaurant initiated)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        from .models import WalletChargeRequest
        from django.utils import timezone as _tz
        now = _tz.now()
        # Lazy-expire stale pendings so the customer never sees a dead request.
        WalletChargeRequest.objects.filter(
            customer_id=customer_id,
            status=WalletChargeRequest.Status.PENDING,
            expires_at__lte=now,
        ).update(status=WalletChargeRequest.Status.EXPIRED, resolved_at=now)
        pendings = WalletChargeRequest.objects.filter(
            customer_id=customer_id, status=WalletChargeRequest.Status.PENDING
        ).order_by("created_at")
        return Response({"requests": [
            {
                "id": r.id,
                "amount": str(r.amount),
                "currency": r.currency,
                "restaurant_name": r.restaurant_name,
                "order_number": r.order_number,
                "note": r.note,
                "expires_at": r.expires_at.isoformat(),
            }
            for r in pendings
        ]})


class CustomerWalletChargeApproveView(APIView):
    """POST /api/customer/wallet/charge-requests/<id>/approve/ — approve a pending charge,
    debiting the wallet. Idempotent: the request carries the debit key, and a re-approve
    of an already-charged request replays the result instead of charging again."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, request_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)

        from .models import WalletChargeRequest
        from .wallet_service import debit_wallet, InsufficientFunds, WalletError
        from django.db import transaction as _dbtx
        from django.utils import timezone as _tz

        try:
            with _dbtx.atomic():
                cr = WalletChargeRequest.objects.select_for_update().get(
                    pk=request_id, customer_id=customer_id
                )
                if cr.status == WalletChargeRequest.Status.CHARGED:
                    return Response({"status": "charged", "amount": str(cr.amount), "duplicate": True})
                if cr.status != WalletChargeRequest.Status.PENDING:
                    return Response(
                        {"detail": "This request is no longer pending.", "code": cr.status},
                        status=status.HTTP_409_CONFLICT,
                    )
                if cr.expires_at <= _tz.now():
                    cr.status = WalletChargeRequest.Status.EXPIRED
                    cr.resolved_at = _tz.now()
                    cr.save(update_fields=["status", "resolved_at"])
                    return Response(
                        {"detail": "This charge request has expired.", "code": "expired"},
                        status=status.HTTP_410_GONE,
                    )
                tx = debit_wallet(
                    customer_id, cr.amount,
                    reference=cr.order_number, tenant_id=cr.tenant_id, note=cr.note,
                    idempotency_key=cr.idempotency_key,
                )
                cr.status = WalletChargeRequest.Status.CHARGED
                cr.resolved_at = _tz.now()
                cr.wallet_tx_id = tx.id
                cr.save(update_fields=["status", "resolved_at", "wallet_tx_id"])
        except WalletChargeRequest.DoesNotExist:
            return Response({"detail": "Charge request not found."}, status=status.HTTP_404_NOT_FOUND)
        except InsufficientFunds:
            # Leave it PENDING so the customer can top up and approve again.
            cust = Customer.objects.filter(pk=customer_id).first()
            return Response(
                {"detail": "Insufficient wallet balance.", "code": "insufficient",
                 "balance": str(cust.wallet_balance) if cust else "0.00"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "charged", "amount": str(tx.amount), "new_balance": str(tx.balance_after)})


class CustomerWalletChargeDeclineView(APIView):
    """POST /api/customer/wallet/charge-requests/<id>/decline/ — decline a pending charge."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, request_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        from .models import WalletChargeRequest
        from django.utils import timezone as _tz
        cr = WalletChargeRequest.objects.filter(pk=request_id, customer_id=customer_id).first()
        if cr is None:
            return Response({"detail": "Charge request not found."}, status=status.HTTP_404_NOT_FOUND)
        if cr.status == WalletChargeRequest.Status.PENDING:
            cr.status = WalletChargeRequest.Status.DECLINED
            cr.resolved_at = _tz.now()
            cr.save(update_fields=["status", "resolved_at"])
        return Response({"status": cr.status})


class CustomerPushVapidKeyView(APIView):
    """GET /api/customer/push-vapid-key/ — VAPID public key so a customer can subscribe to
    Web Push (used to nudge them to approve a pending wallet charge). Public; no auth."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from django.conf import settings
        key = (getattr(settings, "VAPID_PUBLIC_KEY", "") or "").strip()
        return Response({"enabled": bool(key), "public_key": key or None})


class CustomerPushSubscribeView(APIView):
    """POST/DELETE /api/customer/push-subscribe/ — register or remove a customer's browser
    Web Push subscription (session-authenticated customer)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        endpoint = (request.data.get("endpoint") or "").strip()
        p256dh = (request.data.get("p256dh") or "").strip()
        auth = (request.data.get("auth") or "").strip()
        if not (endpoint and p256dh and auth):
            return Response({"detail": "Incomplete subscription."}, status=status.HTTP_400_BAD_REQUEST)
        from .models import CustomerPushSubscription
        # Scope the upsert lookup on (customer_id, endpoint). With endpoint=...
        # ALONE, update_or_create would silently REASSIGN a row owned by another
        # customer to this session — a push hijack (this customer would then
        # receive the other customer's notifications). Including customer_id in
        # the lookup means a foreign-owned endpoint row is never matched/stolen;
        # the only row this session can update is its own.
        CustomerPushSubscription.objects.update_or_create(
            customer_id=customer_id,
            endpoint=endpoint,
            defaults={"customer_id": customer_id, "p256dh": p256dh, "auth": auth},
        )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        endpoint = (request.data.get("endpoint") or "").strip()
        if endpoint:
            from .models import CustomerPushSubscription
            CustomerPushSubscription.objects.filter(endpoint=endpoint, customer_id=customer_id).delete()
        return Response({"unsubscribed": True})


class CustomerWalletView(APIView):
    """GET /api/customer/wallet/ — return balance + transaction history (last 50)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            request.session.pop("customer_id", None)
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        from django.conf import settings
        from .models import WalletTransaction
        txs = WalletTransaction.objects.filter(customer=customer).order_by("-created_at")[:50]
        return Response({
            "balance": str(customer.wallet_balance),
            "phone_verified": bool(customer.phone_verified),
            "p2p_enabled": bool(getattr(settings, "WALLET_P2P_ENABLED", False)),
            "transactions": [
                {
                    "id": tx.id,
                    "type": tx.type,
                    "amount": str(tx.amount),
                    "reference": tx.reference,
                    "note": tx.note,
                    "created_at": tx.created_at.isoformat(),
                }
                for tx in txs
            ],
        })


class CustomerWalletTransferView(APIView):
    """POST /api/customer/wallet/transfer/ — send wallet credit to another customer.

    Body: { "recipient_phone": "+212...", "amount": "10.00", "note": "Thanks!" }

    In-app gifting only (funds never leave the platform). GATED behind
    settings.WALLET_P2P_ENABLED — returns 403 while disabled. This is regulated money
    transmission; do not enable without a license and KYC/AML controls in place.
    Rate-limited per customer (WalletTransferThrottle) so a burst can't drain a wallet.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [WalletTransferThrottle]

    def post(self, request, *args, **kwargs):
        from django.conf import settings
        if not getattr(settings, "WALLET_P2P_ENABLED", False):
            return Response(
                {"detail": "Peer transfers are not enabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)

        from accounts.wallet_service import (
            transfer_between_customers,
            InsufficientFunds,
            WalletError,
        )

        from accounts.phone import normalize_e164

        recipient_phone = str(request.data.get("recipient_phone") or "").strip()
        if not recipient_phone:
            return Response({"detail": "recipient_phone is required."}, status=status.HTTP_400_BAD_REQUEST)

        normalized = normalize_e164(recipient_phone, getattr(settings, "WALLET_DEFAULT_DIAL_CODE", ""))
        if not normalized:
            return Response(
                {"detail": "Enter the recipient's phone in international format (e.g. +212612345678).",
                 "code": "invalid_phone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Only verified phones can receive — never credit an unverified/typo'd number.
            recipient = Customer.objects.get(phone=normalized, phone_verified=True)
        except Customer.DoesNotExist:
            return Response({"detail": "No verified wallet found for that number."}, status=status.HTTP_404_NOT_FOUND)
        except Customer.MultipleObjectsReturned:
            return Response({"detail": "Ambiguous recipient."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "").strip()[:200]
        idempotency_key = str(request.data.get("idempotency_key") or "").strip()[:120] or None

        try:
            out_tx, _in_tx = transfer_between_customers(
                customer_id,
                recipient.id,
                request.data.get("amount"),
                note=note,
                idempotency_key=idempotency_key,
            )
        except InsufficientFunds:
            return Response({"detail": "Insufficient wallet balance."}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "amount": str(out_tx.amount),
            "new_balance": str(out_tx.balance_after),
            "recipient_phone": normalized,
            "note": note,
        })


# ── Admin bonus campaigns ──────────────────────────────────────────────────────


class AdminWalletBonusView(APIView):
    """POST /api/admin/wallet/bonus/ — issue bonus credits to customers.

    Body: { "amount": "10.00", "note": "Welcome bonus", "customer_ids": [1, 2] }
    Omit customer_ids (or set all_customers=true) to credit every customer.
    Requires platform_superadmin role.
    """

    permission_classes = [IsPlatformAdmin]

    def post(self, request, *args, **kwargs):
        from decimal import Decimal as _Dec, InvalidOperation
        from django.db.models import F
        from .models import WalletTransaction

        raw_amount = request.data.get("amount")
        try:
            amount = _Dec(str(raw_amount)).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= _Dec("0"):
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)
        if amount > _Dec("100000"):
            return Response({"detail": "Amount exceeds the maximum allowed per bonus (100000)."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "Bonus credits").strip()[:200]
        idempotency_key = str(request.data.get("idempotency_key") or "").strip()[:100] or None
        customer_ids = request.data.get("customer_ids")
        all_customers = bool(request.data.get("all_customers"))

        # No verified phone → no wallet: bonus credits only ever land in verified wallets.
        if customer_ids:
            qs = Customer.objects.filter(pk__in=customer_ids, phone_verified=True)
        elif all_customers:
            qs = Customer.objects.filter(phone_verified=True)
        else:
            return Response(
                {"detail": "Provide customer_ids or set all_customers=true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import transaction as _dbtx
        with _dbtx.atomic():
            ids = list(qs.values_list("id", flat=True))
            if not ids:
                return Response({"detail": "No matching customers found."}, status=status.HTTP_400_BAD_REQUEST)
            # Concurrency mutex (mirrors the campaign-cap lock in menu/views.py): the
            # exists() pre-check + balance UPDATE(F+1) are not atomic against each other,
            # so two concurrent POSTs with the same key could both clear exists() and both
            # inflate balances (the unique WalletTransaction.idempotency_key only blocks the
            # 2nd ledger INSERT). cache.add() is atomic — only the first concurrent caller
            # wins. Acquired AFTER the empty-batch check (OPS-5d review) so a no-op 400 never
            # holds the lock and a corrected retry isn't falsely deduped; NOT released on
            # success — it expires, and the DB unique key is the permanent durable guard.
            if idempotency_key:
                _lock_key = f"walletbonus:{idempotency_key}"
                if not cache.add(_lock_key, "1", 60):
                    return Response({"issued_to": 0, "amount": str(amount), "note": note, "duplicate": True})
            # Idempotency: a repeated submit with the same key (double-click, retry) must
            # not credit real money twice. Per-customer keys are derived from the batch key.
            if idempotency_key and WalletTransaction.objects.filter(
                idempotency_key__startswith=f"{idempotency_key}:"
            ).exists():
                return Response({"issued_to": 0, "amount": str(amount), "note": note, "duplicate": True})
            # OPS-5b: populate balance_after for ledger reconcilability.
            # Bulk-update the balances first (single SQL UPDATE — fast), then read the
            # new per-customer balances back to record in the transaction log.
            # The idempotency key format {idempotency_key}:{cid} is preserved.
            Customer.objects.filter(pk__in=ids).update(
                wallet_balance=F("wallet_balance") + amount
            )
            # Read new balances in a single query keyed by customer id.
            new_balances = dict(
                Customer.objects.filter(pk__in=ids).values_list("id", "wallet_balance")
            )
            WalletTransaction.objects.bulk_create([
                WalletTransaction(
                    customer_id=cid,
                    type=WalletTransaction.Type.BONUS,
                    amount=amount,
                    balance_after=new_balances.get(cid),
                    note=note,
                    idempotency_key=(f"{idempotency_key}:{cid}" if idempotency_key else None),
                )
                for cid in ids
            ])

        log_admin_action(
            action=AdminAuditLog.Actions.WALLET_BONUS_ISSUED,
            request=request,
            target_repr=(f"{len(ids)} customers" if not customer_ids else f"customers:{ids}"[:255]),
            metadata={"amount": str(amount), "issued_to": len(ids), "note": note,
                      "all_customers": all_customers},
        )
        return Response({"issued_to": len(ids), "amount": str(amount), "note": note})


class AdminFundTenantView(APIView):
    """POST /api/admin/wallet/fund-tenant/ — platform funds a restaurant's float.

    Body: { "tenant_id": 3, "amount": "500.00", "note": "Cash collected 2026-06-01" }
    The float is what the owner can hand out to customers; cash is reconciled offline.
    Requires platform_superadmin (or staff/superuser).
    """

    permission_classes = [IsPlatformAdmin]

    def post(self, request, *args, **kwargs):
        user = getattr(request, "user", None)

        from accounts.wallet_service import credit_tenant_float, WalletError
        from tenancy.models import Tenant

        tenant_id = request.data.get("tenant_id")
        if not tenant_id:
            return Response({"detail": "tenant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "Platform funding").strip()[:200]
        reference = str(request.data.get("reference") or "").strip()[:120]
        raw_idem = str(request.data.get("idempotency_key") or "").strip()[:120]
        # Server-namespace the caller-supplied key so a chosen value can't collide
        # with another tenant's funding (idempotency is global on the key). Prefix
        # with a server-controlled string scoped to this tenant.
        idempotency_key = f"adminfund:{tenant_id}:{raw_idem}" if raw_idem else None

        try:
            tx = credit_tenant_float(
                tenant_id,
                request.data.get("amount"),
                actor_user_id=getattr(user, "id", None),
                note=note,
                reference=reference,
                idempotency_key=idempotency_key,
            )
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found."}, status=status.HTTP_404_NOT_FOUND)
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_admin_action(
            action=AdminAuditLog.Actions.TENANT_FLOAT_FUNDED,
            request=request,
            target_repr=f"tenant:{tenant_id}",
            metadata={"amount": str(tx.amount), "balance_after": str(tx.balance_after), "note": note},
        )
        return Response({
            "tenant_id": int(tenant_id),
            "amount": str(tx.amount),
            "float_balance": str(tx.balance_after),
            "note": note,
        })


class AdminPlatformSettingsView(APIView):
    """GET/PATCH /api/admin/settings/ — platform-wide, admin-editable settings.

    Exposes the wallet charge approval threshold and ride-hailing fare config.
    Platform admin only.

    OPS-5b: consolidated onto IsPlatformAdmin (drops is_staff inline check).
    """

    permission_classes = [IsPlatformAdmin]

    # {field_name: (min_value, max_value_or_None)}
    FIELD_RULES = {
        "wallet_charge_approval_threshold": (0, None),
        "ride_base_fare": (0, None),
        "ride_per_km": (0, None),
        "ride_per_minute": (0, None),
        "ride_minimum_fare": (0, None),
        "ride_commission_pct": (0, 100),
    }

    def _serialize(self, cfg):
        return {
            "wallet_charge_approval_threshold": str(cfg.wallet_charge_approval_threshold),
            "ride_base_fare": str(cfg.ride_base_fare),
            "ride_per_km": str(cfg.ride_per_km),
            "ride_per_minute": str(cfg.ride_per_minute),
            "ride_minimum_fare": str(cfg.ride_minimum_fare),
            "ride_commission_pct": str(cfg.ride_commission_pct),
        }

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import PlatformConfig
        return Response(self._serialize(PlatformConfig.get_solo()))

    def patch(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from decimal import Decimal as _Dec, InvalidOperation
        from .models import PlatformConfig

        cfg = PlatformConfig.get_solo()
        changed = []

        for field, (min_val, max_val) in self.FIELD_RULES.items():
            raw = request.data.get(field)
            if raw is None:
                continue
            try:
                val = _Dec(str(raw)).quantize(_Dec("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {"detail": f"Invalid value for {field}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if val < min_val:
                return Response(
                    {"detail": f"{field} must be at least {min_val}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if max_val is not None and val > max_val:
                return Response(
                    {"detail": f"{field} cannot exceed {max_val}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            setattr(cfg, field, val)
            changed.append(field)

        if changed:
            cfg.save(update_fields=changed + ["updated_at"])
            log_admin_action(
                action=AdminAuditLog.Actions.PLATFORM_SETTINGS_UPDATED,
                request=request,
                target_repr="platform_config",
                metadata={"changed_fields": changed},
            )

        return Response(self._serialize(cfg))


class AdminCustomerListView(APIView):
    """GET /api/admin/customers/ — the platform customer directory (marketplace clients).

    Customers are platform-level identities (public schema), NOT owned by any restaurant —
    the platform sits between restaurants and clients. This is the admin's view of every
    customer: identity, verification, wallet, loyalty, driver status. Paginated +
    searchable by name / phone / email, with optional driver/verified filters.

    OPS-5b: IsPlatformAdmin gate (drops is_staff), per-admin throttle, PII read audit.
    """

    permission_classes = [IsPlatformAdmin]
    throttle_classes = [AdminPIIThrottle]

    def get(self, request, *args, **kwargs):
        from django.db.models import Q

        qs = Customer.objects.all().order_by("-created_at")
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
            )
        if str(request.query_params.get("drivers_only") or "").lower() in ("1", "true"):
            qs = qs.filter(is_driver=True)
        if str(request.query_params.get("verified_only") or "").lower() in ("1", "true"):
            qs = qs.filter(phone_verified=True)

        try:
            page = max(1, int(request.query_params.get("page") or 1))
            page_size = min(100, max(1, int(request.query_params.get("page_size") or 25)))
        except (ValueError, TypeError):
            page, page_size = 1, 25

        total = qs.count()
        start = (page - 1) * page_size
        rows = qs[start: start + page_size]
        results = [
            {
                "id": c.id,
                "name": c.name or "",
                "phone": c.phone or "",
                "phone_verified": c.phone_verified,
                "email": c.email or "",
                "email_verified": c.email_verified,
                "has_google": bool(c.google_sub),
                "wallet_balance": str(c.wallet_balance),
                "loyalty_points": c.loyalty_points or 0,
                "is_driver": c.is_driver,
                "created_at": c.created_at.isoformat(),
            }
            for c in rows
        ]
        log_admin_action(
            action=AdminAuditLog.Actions.CUSTOMER_PII_VIEWED,
            request=request,
            target_repr="customer_list",
            metadata={"query": search or "", "count": total, "page": page},
        )
        return Response({"total": total, "page": page, "page_size": page_size, "results": results})


class AdminCustomerDetailView(APIView):
    """GET/PATCH /api/admin/customers/<id>/ — a single platform customer.

    GET returns the full profile + cross-restaurant wallet ledger (each payment shows
    which restaurant it was at), trust score, loyalty and driver status. PATCH toggles
    is_driver (admin can register/unregister a delivery driver).

    OPS-5b: IsPlatformAdmin gate (drops is_staff), per-admin throttle, PII read + write audits.
    """

    permission_classes = [IsPlatformAdmin]
    throttle_classes = [AdminPIIThrottle]

    def get(self, request, customer_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        try:
            c = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        from django.db.models import Avg, Count
        from .models import CustomerRating, DeliveryJob, WalletTransaction

        txs = list(WalletTransaction.objects.filter(customer=c).order_by("-created_at")[:50])
        tenant_ids = {t.tenant_id for t in txs if t.tenant_id}
        tenant_names = {}
        if tenant_ids:
            from tenancy.models import Tenant
            tenant_names = dict(Tenant.objects.filter(id__in=tenant_ids).values_list("id", "name"))

        ratings = CustomerRating.objects.filter(customer=c).aggregate(avg=Avg("score"), count=Count("id"))
        delivery_jobs = DeliveryJob.objects.filter(driver=c).count() if c.is_driver else 0

        log_admin_action(
            action=AdminAuditLog.Actions.CUSTOMER_PII_VIEWED,
            request=request,
            target_repr=f"customer:{customer_id}",
            metadata={"customer_id": customer_id},
        )
        return Response({
            "id": c.id,
            "name": c.name or "",
            "phone": c.phone or "",
            "phone_verified": c.phone_verified,
            "email": c.email or "",
            "email_verified": c.email_verified,
            "has_google": bool(c.google_sub),
            "wallet_balance": str(c.wallet_balance),
            "loyalty_points": c.loyalty_points or 0,
            "is_driver": c.is_driver,
            "is_driver_online": c.is_driver_online,
            "created_at": c.created_at.isoformat(),
            "trust": {
                "avg_score": round(float(ratings["avg"]), 2) if ratings["avg"] is not None else None,
                "count": ratings["count"] or 0,
            },
            "delivery_jobs": delivery_jobs,
            "transactions": [
                {
                    "id": t.id,
                    "type": t.type,
                    "amount": str(t.amount),
                    "balance_after": (str(t.balance_after) if t.balance_after is not None else None),
                    "tenant_id": t.tenant_id,
                    "tenant_name": tenant_names.get(t.tenant_id, ""),
                    "reference": t.reference,
                    "note": t.note,
                    "created_at": t.created_at.isoformat(),
                }
                for t in txs
            ],
        })

    def patch(self, request, customer_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        try:
            c = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        if "is_driver" in request.data:
            new_value = bool(request.data["is_driver"])
            c.is_driver = new_value
            fields = ["is_driver", "updated_at"]
            if not c.is_driver and c.is_driver_online:
                c.is_driver_online = False
                fields.append("is_driver_online")
            c.save(update_fields=fields)
            log_admin_action(
                action=AdminAuditLog.Actions.CUSTOMER_DRIVER_TOGGLED,
                request=request,
                target_repr=f"customer:{customer_id}",
                metadata={"customer_id": customer_id, "is_driver": new_value},
            )
        return Response({"id": c.id, "is_driver": c.is_driver, "is_driver_online": c.is_driver_online})


class AdminCustomerCreditView(APIView):
    """POST /api/admin/customers/<id>/credit/ — admin tops up / adjusts a customer wallet.

    Goes through the central credit_wallet service: atomic, idempotent, and subject to
    the platform rule (a verified phone is required to hold wallet funds).
    """

    permission_classes = [IsPlatformAdmin]

    def post(self, request, customer_id, *args, **kwargs):
        from decimal import Decimal as _Dec, InvalidOperation

        from accounts.wallet_service import credit_wallet, WalletError, UnverifiedWallet
        from accounts.models import WalletTransaction

        try:
            amount = _Dec(str(request.data.get("amount"))).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= _Dec("0") or amount > _Dec("100000"):
            return Response({"detail": "Amount must be between 0 and 100000."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "Admin adjustment").strip()[:200]
        idem = str(request.data.get("idempotency_key") or "").strip()[:120] or None
        try:
            tx = credit_wallet(
                customer_id, amount,
                tx_type=WalletTransaction.Type.ADJUSTMENT, note=note, idempotency_key=idem,
            )
        except UnverifiedWallet:
            return Response(
                {"detail": "Customer must verify their phone before holding wallet funds.", "code": "unverified"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_admin_action(
            action=AdminAuditLog.Actions.CUSTOMER_WALLET_CREDITED,
            request=request,
            target_repr=f"customer:{customer_id}",
            metadata={"amount": str(tx.amount), "balance_after": str(tx.balance_after), "note": note},
        )
        return Response({"new_balance": str(tx.balance_after), "amount": str(tx.amount)})


class AdminCustomerOrdersView(APIView):
    """GET /api/admin/customers/<id>/orders/ — the customer's orders across ALL restaurants.

    Reads the public-schema CustomerOrderRef index (one indexed query) instead of
    scanning every tenant schema — the same source the customer's own cross-restaurant
    history uses (CustomerMarketplaceOrdersView), so it's consistent and O(1) in the
    number of tenants.
    """

    permission_classes = [IsPlatformAdmin]
    RESULT_LIMIT = 50

    def get(self, request, customer_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        if not Customer.objects.filter(pk=customer_id).exists():
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        from .models import CustomerOrderRef

        # Cross-restaurant history from the public-schema index — one indexed query
        # instead of up to 500 per-schema scans. Same source the customer sees.
        base = CustomerOrderRef.objects.filter(customer_id=customer_id)
        refs = list(base.order_by("-order_created_at")[: self.RESULT_LIMIT])
        orders = [
            {
                "order_number": r.order_number,
                "restaurant": r.restaurant_name,
                "status": r.status,
                "fulfillment_type": r.fulfillment_type or "",
                "total": str(r.total),
                "currency": r.currency,
                "created_at": r.order_created_at.isoformat() if r.order_created_at else None,
            }
            for r in refs
        ]
        return Response({
            "results": orders,
            "count": base.count(),
            "scanned_restaurants": len({r.restaurant_slug for r in refs}),
        })


# ── Wallet vouchers (admin create, customer redeem) ───────────────────────────


class AdminWalletVoucherView(APIView):
    """
    GET  /api/admin/wallet/vouchers/          — list recent vouchers (last 100)
    POST /api/admin/wallet/vouchers/          — create one or more vouchers
      Body: { "amount": "20.00", "note": "Welcome", "count": 5, "expires_days": 30 }
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import WalletVoucher
        qs = WalletVoucher.objects.select_related("used_by")[:100]
        data = []
        for v in qs:
            data.append({
                "id": v.id,
                "code": v.code,
                "amount": str(v.amount),
                "note": v.note,
                "is_used": v.is_used,
                "used_by_name": str(v.used_by) if v.used_by else None,
                "used_at": v.used_at.isoformat() if v.used_at else None,
                "expires_at": v.expires_at.isoformat() if v.expires_at else None,
                "created_at": v.created_at.isoformat(),
            })
        return Response(data)

    def post(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from decimal import Decimal as _Dec, InvalidOperation
        from django.utils import timezone as _tz
        import datetime
        from .models import WalletVoucher

        raw_amount = request.data.get("amount")
        try:
            amount = _Dec(str(raw_amount)).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= _Dec("0"):
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)
        if amount > _Dec("100000"):
            return Response({"detail": "Amount exceeds the maximum allowed per voucher (100000)."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "").strip()[:200]

        try:
            count = max(1, min(50, int(request.data.get("count") or 1)))
        except (ValueError, TypeError):
            count = 1

        expires_at = None
        # Accept either an ISO datetime string (expires_at) or a day count (expires_days)
        expires_at_raw = request.data.get("expires_at")
        expires_days = request.data.get("expires_days")
        if expires_at_raw:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(str(expires_at_raw))
            # An expiry was requested but couldn't be parsed — fail loudly rather than
            # silently create a never-expiring voucher the admin didn't intend.
            if expires_at is None:
                return Response(
                    {"detail": "expires_at is not a valid datetime."}, status=status.HTTP_400_BAD_REQUEST
                )
            if _tz.is_naive(expires_at):
                expires_at = _tz.make_aware(expires_at)
        elif expires_days:
            try:
                expires_at = _tz.now() + datetime.timedelta(days=int(expires_days))
            except (ValueError, TypeError):
                pass

        vouchers = WalletVoucher.objects.bulk_create([
            WalletVoucher(
                code=WalletVoucher.generate_code(),
                amount=amount,
                note=note,
                expires_at=expires_at,
            )
            for _ in range(count)
        ])

        log_admin_action(
            action=AdminAuditLog.Actions.VOUCHER_ISSUED,
            request=request,
            target_repr=f"{len(vouchers)} voucher(s)",
            metadata={"amount": str(amount), "count": len(vouchers),
                      "expires_at": expires_at.isoformat() if expires_at else None},
        )
        return Response({
            "created": len(vouchers),
            "codes": [v.code for v in vouchers],
            "amount": str(amount),
            "expires_at": expires_at.isoformat() if expires_at else None,
        }, status=status.HTTP_201_CREATED)


# OPS-5g: per-actor failed-attempt lockout for voucher redemption. A voucher code is a
# bearer money-token (redeem → wallet credit), so an attacker can iterate codes against a
# session. The dedicated throttle caps overall request rate; this lockout adds a tighter
# brute-force cap that trips on CONSECUTIVE INVALID (nonexistent) codes — mirroring the
# driver_cashout_confirm lockout in accounts/driver_service.py. A legit redeem never
# increments the counter (right code first try), and a successful redeem clears it, so this
# is transparent to honest callers.
VOUCHER_REDEEM_MAX_FAILURES = 5      # consecutive invalid codes before the actor is locked
VOUCHER_REDEEM_LOCK_SECONDS = 900    # lockout / counting window (15 min)


def _voucher_redeem_fail_cache_key(request, customer) -> str:
    """Per-actor key for failed voucher redemptions (prefer session customer id, fall
    back to the resolved customer id, then the request IP)."""
    cid = None
    try:
        cid = request.session.get("customer_id")
    except Exception:
        cid = None
    if not cid:
        cid = getattr(customer, "id", None)
    if cid:
        ident = f"c{cid}"
    else:
        from sales.audit import get_request_ip
        ident = get_request_ip(request) or "anon"
    return f"voucher_redeem_fail:{ident}"


class CustomerWalletRedeemVoucherView(APIView):
    """
    POST /api/customer/wallet/redeem-voucher/
    Body: { "code": "ABCD1234EF" }

    Redeems a single-use voucher code for the authenticated customer.
    """

    permission_classes = [IsAuthenticated]
    # OPS-5g: a redeemed code maps straight to wallet credit → brute-force-to-money
    # target. The throttle is the rate backstop; the per-actor invalid-code lockout
    # below is the primary brute-force defense.
    throttle_classes = [VoucherRedeemThrottle]

    def post(self, request, *args, **kwargs):
        from django.core.cache import cache as _cache
        from django.utils import timezone as _tz
        from .models import WalletVoucher, WalletTransaction

        # Resolve customer
        customer = getattr(request, "customer", None)
        if customer is None:
            try:
                customer = Customer.objects.get(user=request.user)
            except Customer.DoesNotExist:
                customer = None
        if customer is None:
            return Response({"detail": "Customer account not found."}, status=status.HTTP_404_NOT_FOUND)
        if not customer.phone_verified:
            return Response(
                {"detail": "Verify your phone number to use your wallet.", "code": "phone_unverified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        code = str(request.data.get("code") or "").strip().upper()
        if not code:
            return Response({"detail": "Voucher code is required."}, status=status.HTTP_400_BAD_REQUEST)

        # OPS-5g: per-actor invalid-code lockout. A scanner iterating codes racks up
        # failures fast and is locked out; a legit redeem (right code first try) never
        # increments the counter and clears it on success.
        fail_key = _voucher_redeem_fail_cache_key(request, customer)
        if (_cache.get(fail_key) or 0) >= VOUCHER_REDEEM_MAX_FAILURES:
            return Response(
                {"detail": "Too many invalid voucher codes — try again shortly.",
                 "code": "voucher_locked"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        def _record_failure():
            try:
                _cache.set(fail_key, (_cache.get(fail_key) or 0) + 1, VOUCHER_REDEEM_LOCK_SECONDS)
            except Exception:
                pass

        from django.db import transaction as _dbtx
        with _dbtx.atomic():
            try:
                voucher = WalletVoucher.objects.select_for_update().get(code=code)
            except WalletVoucher.DoesNotExist:
                # An invalid (nonexistent) code is the brute-force signal — count it.
                _record_failure()
                return Response({"detail": "Invalid voucher code."}, status=status.HTTP_400_BAD_REQUEST)

            if voucher.is_used:
                # Idempotent replay: if THIS customer already redeemed it (e.g. a
                # lost-response retry), return success with their current balance
                # instead of a false "already used" error. The credit happened once.
                if voucher.used_by_id == customer.id:
                    return Response({
                        "credited": str(voucher.amount),
                        "new_balance": str(customer.wallet_balance),
                        "note": voucher.note,
                        "duplicate": True,
                    })
                return Response({"detail": "This voucher has already been used."}, status=status.HTTP_400_BAD_REQUEST)

            now = _tz.now()
            if voucher.expires_at and voucher.expires_at < now:
                return Response({"detail": "This voucher has expired."}, status=status.HTTP_400_BAD_REQUEST)

            voucher.is_used = True
            voucher.used_by = customer
            voucher.used_at = now
            voucher.save(update_fields=["is_used", "used_by", "used_at"])

            # OPS-5f: funnel the credit through wallet_service.credit_wallet instead of a
            # manual read-modify-write of wallet_balance. credit_wallet re-fetches the
            # Customer with select_for_update (the manual path did NOT lock the customer
            # row → lost-update race vs concurrent wallet credits/debits), writes the
            # ledger row with balance_after, and is idempotent on the key. The voucher row
            # lock above still guarantees single-redeem; the stable key makes a lost-response
            # retry a no-op rather than a double credit.
            from accounts.wallet_service import credit_wallet as _credit_wallet
            _tx = _credit_wallet(
                customer.id, voucher.amount,
                tx_type=WalletTransaction.Type.TOPUP,
                idempotency_key=f"voucher:{voucher.id}",
                reference=voucher.code,
                note=voucher.note or f"Voucher {voucher.code}",
            )
            _new_balance = _tx.balance_after

        # A successful redeem clears the actor's failed-attempt counter.
        try:
            _cache.delete(fail_key)
        except Exception:
            pass

        return Response({
            "credited": str(voucher.amount),
            "new_balance": str(_new_balance),
            "note": voucher.note,
        })


# ── Restaurant directory & marketplace ────────────────────────────────────────


def _compute_is_open_now(profile) -> bool:
    """Evaluate open/closed for a Profile using manual toggle + schedule only.

    Intentionally skips the ClosureDate check because that table lives in the
    tenant schema and this function runs in the public-schema context.
    """
    if not profile.is_open:
        return False
    if getattr(profile, "is_menu_temporarily_disabled", False):
        return False
    # The window rule (tenant-local weekday + [open, close) HH:MM) is the SINGLE source of
    # truth in tenancy.openstate.schedule_open_now — shared with the menu-page serializer and
    # the order-acceptance gate. None means "no schedule configured" → fall back to is_open.
    schedule = getattr(profile, "business_hours_schedule", None)
    result = schedule_open_now(schedule, tenant_local_now(profile))
    return bool(profile.is_open) if result is None else result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres (Haversine formula)."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# The promo field reader / date coercer / windowing rule now live in menu.promos —
# the SINGLE source of truth shared with the checkout discount path. These names are
# re-exported here as thin aliases for any in-app reference; promo_is_active is the
# one rule (it imports only stdlib, so this top-level import has no cross-app cycle).
from menu.promos import (
    promo_field as _promo_field,
    coerce_date as _coerce_date,
    promo_is_active as _promo_is_active,
)


def _is_promo_active_now(promo, now_local=None) -> bool:
    """Return True if a promo is currently active (schedule + date range).

    THIN WRAPPER over menu.promos.promo_is_active — the single source of truth for
    the promo window. Accepts EITHER a Promotion model instance OR a denormalized
    dict (the entries in Profile.marketplace_promos). Holds NO date/time rules of
    its own; it only picks the clock and delegates.

    ``now_local`` is the tenant-local tz-aware "now"; the badge callers pass a
    per-tenant ZoneInfo(profile.timezone) now so the window is evaluated in the
    tenant's wall-clock time (intentional, correct behavior change; safe pre-launch).
    When omitted it defaults to a SINGLE consistent UTC clock, which already removes
    the old today()/utcnow() mismatch for callers that don't supply a tenant now.
    """
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    if now_local is None:
        now_local = _dt.now(ZoneInfo("UTC"))
    return _promo_is_active(promo, now_local=now_local)


def _promo_badge_from_denorm(promos, now_local=None):
    """Build the marketplace promo badge from a tenant's denormalized promo list.

    `promos` is Profile.marketplace_promos — a list of dicts already ordered the SAME
    way the old per-tenant query selected (highest discount_value first; see
    menu/promos_denorm.recompute_tenant_promos). We pick the FIRST entry that is live
    now (in-memory windowing via _is_promo_active_now) and emit the SAME badge string
    the old in-loop code did. Returns None if nothing is live (matching old default).

    ``now_local`` is the tenant-local tz-aware "now" the window is evaluated from; the
    listing loop passes a per-tenant ZoneInfo(profile.timezone) now so "live now" is
    tenant wall-clock. When omitted the wrapper falls back to a consistent UTC clock.
    """
    if not promos or not isinstance(promos, (list, tuple)):
        return None
    for _p in promos:
        if not isinstance(_p, dict):
            continue
        if not _is_promo_active_now(_p, now_local=now_local):
            continue
        promo_type = _p.get("promo_type")
        discount_value = _p.get("discount_value")
        if promo_type == "percentage":
            return f"{int(float(discount_value))}% off"
        elif promo_type == "fixed":
            return f"-{discount_value} off"
        else:
            return "Free delivery"
    return None


# ── Public listing response cache ─────────────────────────────────────────────
# The marketplace + directory endpoints are public, param-only, cross-tenant reads
# (no per-user/per-tenant data in the response), so the whole computed response can
# be cached by query-param hash — turning the O(N_tenants) per-request work into a
# single cache GET for everyone with the same params. A short TTL keeps it fresh
# without explicit invalidation (opt-in/out or a new rating shows within the window),
# but a GLOBAL version counter also lets writes bust it immediately: a denormalized
# rating change (B8) bumps the version so the directory/marketplace listing refreshes
# right away instead of waiting out the TTL. The listing is cross-tenant, so the
# version is GLOBAL (one counter for all tenants), mirroring menu/views._bust_menu_cache.
_PUBLIC_LIST_TTL = 90  # seconds
_PUBLIC_LIST_VER_KEY = "public_list_ver"


def _public_list_cache_key(prefix, request):
    ver = cache.get(_PUBLIC_LIST_VER_KEY) or 1
    parts = sorted(request.query_params.urlencode().split("&"))
    return f"{prefix}:v{ver}:{hashlib.md5('&'.join(parts).encode()).hexdigest()}"


def _bust_public_list_cache() -> None:
    """Increment the global version counter, orphaning all existing list-cache entries.

    Best-effort: a bust failure must never break the caller (e.g. a rating save).
    """
    try:
        cache.incr(_PUBLIC_LIST_VER_KEY)
    except ValueError:
        # Key missing (LocMemCache raises ValueError; Redis raises ResponseError).
        cache.set(_PUBLIC_LIST_VER_KEY, 2, timeout=None)


class DirectoryView(APIView):
    """GET /api/directory/ — public list of restaurants that opted in.

    Query params:
      city=        filter by city (case-insensitive contains)
      cuisine=     filter by cuisine_type (case-insensitive contains)
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [MarketplaceBrowseThrottle]

    def get(self, request, *args, **kwargs):
        from tenancy.models import Profile

        city_q = (request.query_params.get("city") or "").strip()
        cuisine_q = (request.query_params.get("cuisine") or "").strip()

        qs = (
            Profile.objects
            # Only ACTIVE tenants are discoverable — suspended / past-grace (and canceled)
            # restaurants drop out of the marketplace but keep serving their own subdomain.
            .filter(directory_opt_in=True, is_menu_published=True, tenant__lifecycle_status="active")
            .select_related("tenant")
            .order_by("tenant__name")
        )
        if city_q:
            qs = qs.filter(city__icontains=city_q)
        if cuisine_q:
            qs = qs.filter(cuisine_type__icontains=cuisine_q)

        _ck = _public_list_cache_key("directory", request)
        _hit = cache.get(_ck)
        if _hit is not None:
            return Response(_hit)

        # Materialise the (up-to-100) profile rows once so we can build filter
        # lists from the same data without a second full-table scan.
        profiles_page = list(qs[:100])

        results = []
        cities_set: set = set()
        cuisines_set: set = set()

        # B8: ratings are denormalized onto the public Profile (rating_avg /
        # rating_count), kept in sync by the menu.Rating signals. This loop is now
        # pure in-memory — no per-tenant schema_context switch for the rating.
        for profile in profiles_page:
            tenant = profile.tenant
            # Derive is_open identically to MarketplaceView (schedule-aware, tenant-local)
            # so the SAME restaurant reads the same open/closed state on both listings.
            is_currently_open = _compute_is_open_now(profile)

            rating_average = float(profile.rating_avg) if profile.rating_avg is not None else None
            rating_count = profile.rating_count or 0

            if profile.city:
                cities_set.add(profile.city)
            if profile.cuisine_type:
                cuisines_set.add(profile.cuisine_type)

            results.append({
                "slug": tenant.slug,
                "name": tenant.name,
                "tagline": profile.tagline or "",
                "logo_url": profile.logo_url or "",
                "cuisine_type": profile.cuisine_type or "",
                "business_type": getattr(profile, "business_type", "") or "restaurant",
                "city": profile.city or "",
                "is_open": is_currently_open,
                "rating_average": rating_average,
                "rating_count": rating_count,
                "delivery_enabled": bool(profile.delivery_enabled),
            })

        cities = sorted(cities_set)
        cuisines = sorted(cuisines_set)

        _payload = {"restaurants": results, "filters": {"cities": cities, "cuisines": cuisines}}
        cache.set(_ck, _payload, _PUBLIC_LIST_TTL)
        return Response(_payload)


class MarketplaceView(APIView):
    """GET /api/marketplace/ — public marketplace listing with advanced filters.

    Extends DirectoryView with:
      ?q=           full-text search across name / tagline / cuisine
      ?city=        city filter
      ?cuisine=     cuisine filter
      ?fulfillment= delivery | pickup | any  (default: any)
      ?open=        1 → only open restaurants
      ?min_rating=  minimum avg rating (float, e.g. 3.5)
      ?price_tier=  1 | 2 | 3
      ?tags=        comma-separated tags (e.g. vegetarian,halal) — ALL must match
      ?lat=&lng=    customer coordinates → sorts by distance, adds distance_km
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [MarketplaceBrowseThrottle]

    def get(self, request, *args, **kwargs):
        from tenancy.models import Profile

        q = (request.query_params.get("q") or "").strip().lower()
        city_q = (request.query_params.get("city") or "").strip()
        cuisine_q = (request.query_params.get("cuisine") or "").strip()
        fulfillment = (request.query_params.get("fulfillment") or "any").strip().lower()
        open_only = request.query_params.get("open") == "1"
        _ck = _public_list_cache_key("marketplace", request)
        _hit = cache.get(_ck)
        if _hit is not None:
            return Response(_hit)

        min_rating_raw = (request.query_params.get("min_rating") or "").strip()
        price_tier_raw = (request.query_params.get("price_tier") or "").strip()
        tags_raw = (request.query_params.get("tags") or "").strip()
        lat_raw = (request.query_params.get("lat") or "").strip()
        lng_raw = (request.query_params.get("lng") or "").strip()

        min_rating = None
        if min_rating_raw:
            try:
                min_rating = float(min_rating_raw)
            except ValueError:
                pass

        price_tier_filter = None
        if price_tier_raw:
            try:
                price_tier_filter = int(price_tier_raw)
            except ValueError:
                pass

        user_lat = None
        user_lng = None
        if lat_raw and lng_raw:
            try:
                user_lat = float(lat_raw)
                user_lng = float(lng_raw)
            except ValueError:
                pass

        required_tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        qs = (
            Profile.objects
            # Only ACTIVE tenants are discoverable — suspended / past-grace (and canceled)
            # restaurants drop out of the marketplace but keep serving their own subdomain.
            .filter(directory_opt_in=True, is_menu_published=True, tenant__lifecycle_status="active")
            .select_related("tenant")
            .order_by("tenant__name")
        )
        if city_q:
            qs = qs.filter(city__icontains=city_q)
        if cuisine_q:
            qs = qs.filter(cuisine_type__icontains=cuisine_q)
        if fulfillment == "delivery":
            qs = qs.filter(delivery_enabled=True)
        if price_tier_filter:
            qs = qs.filter(price_tier=price_tier_filter)
        # B8: min_rating now filters in SQL on the denormalized Profile.rating_avg
        # instead of a per-tenant post-filter. rating_avg__gte drops NULLs (unrated
        # tenants), matching the OLD behaviour: the in-loop filter dropped a tenant
        # when rating_avg was None or < min_rating.
        if min_rating is not None:
            qs = qs.filter(rating_avg__gte=min_rating)

        # ── Batch flash-sale data (one query each, before the per-tenant loop) ──
        # Build a mapping: tenant_id → set of flash_sale_ids they opted into.
        # Then fetch all currently-active+live flash sales once, as a set of ids.
        opted_map: dict = {}   # tenant_id → set[flash_sale_id]
        live_flash_sale_ids: set = set()
        try:
            from .models import PlatformFlashSale, PlatformFlashSaleOptIn
            for row in PlatformFlashSaleOptIn.objects.values("tenant_id", "flash_sale_id"):
                opted_map.setdefault(row["tenant_id"], set()).add(row["flash_sale_id"])
            # Only keep flash sales that are is_active=True AND pass the is_live() check.
            for _fs in PlatformFlashSale.objects.filter(is_active=True):
                if _fs.is_live():
                    live_flash_sale_ids.add(_fs.id)
        except Exception:
            pass

        # Materialise the page so we can derive filter lists without an extra query.
        profiles_page = list(qs[:200])

        results = []
        cities_set: set = set()
        cuisines_set: set = set()
        all_tags: set = set()

        for profile in profiles_page:
            tenant = profile.tenant

            # Accumulate filter values from rows already in memory.
            if profile.city:
                cities_set.add(profile.city)
            if profile.cuisine_type:
                cuisines_set.add(profile.cuisine_type)
            if isinstance(profile.tags, list):
                all_tags.update(str(t).lower() for t in profile.tags)

            is_currently_open = _compute_is_open_now(profile)

            if open_only and not is_currently_open:
                continue

            if q:
                haystack = " ".join(filter(None, [
                    (tenant.name or "").lower(),
                    (profile.tagline or "").lower(),
                    (profile.cuisine_type or "").lower(),
                    (profile.city or "").lower(),
                ])).lower()
                if q not in haystack:
                    continue

            profile_tags = [str(t).lower() for t in (profile.tags or [])]
            if required_tags and not all(rt in profile_tags for rt in required_tags):
                continue

            # B8: ratings are read from the denormalized public Profile (kept in
            # sync by the menu.Rating signals) — NO per-tenant schema_context /
            # Rating aggregate. min_rating is already applied in SQL above.
            rating_avg = float(profile.rating_avg) if profile.rating_avg is not None else None
            rating_count = profile.rating_count or 0

            # B8-followup: promo badge is read from the denormalized public
            # Profile.marketplace_promos (kept in sync by the menu.Promotion
            # signals) — NO per-tenant schema_context / Promotion query. The
            # time-window ("live now") is evaluated in-memory at request time on
            # the denormalized schedule, mirroring the flash-sale path. This was the
            # LAST per-tenant schema switch in the listing loop (rating already
            # denormalized in B8); the loop is now fully in-memory.
            try:
                # Evaluate "live now" in the TENANT's local wall-clock time (a promo
                # "Tue 14:00–16:00" is tenant-local), not the server's. Per-tenant and
                # cheap (no DB) — just a ZoneInfo from the denormalized timezone.
                from datetime import datetime as _dt
                from zoneinfo import ZoneInfo
                try:
                    _badge_now = _dt.now(ZoneInfo((getattr(profile, "timezone", "") or "UTC")))
                except Exception:
                    _badge_now = _dt.now(ZoneInfo("UTC"))
                promo_badge = _promo_badge_from_denorm(
                    getattr(profile, "marketplace_promos", None), now_local=_badge_now
                )
            except Exception:
                promo_badge = None

            # Check flash-sale membership using the pre-fetched maps (no per-tenant DB hit).
            tenant_opted_ids = opted_map.get(tenant.id, set())
            flash_sale_active = bool(tenant_opted_ids & live_flash_sale_ids)

            distance_km = None
            if user_lat is not None and profile.lat and profile.lng:
                distance_km = round(_haversine_km(user_lat, user_lng, profile.lat, profile.lng), 1)

            results.append({
                "slug": tenant.slug,
                "name": tenant.name,
                "tagline": profile.tagline or "",
                "logo_url": profile.logo_url or "",
                "cuisine_type": profile.cuisine_type or "",
                "business_type": getattr(profile, "business_type", "") or "restaurant",
                "city": profile.city or "",
                "address": profile.address or "",
                "is_open": is_currently_open,
                "delivery_enabled": bool(profile.delivery_enabled),
                "delivery_fee": str(profile.delivery_fee) if profile.delivery_fee else "0",
                "delivery_minimum_order": str(profile.delivery_minimum_order) if profile.delivery_minimum_order else "0",
                "price_tier": profile.price_tier,
                "tags": profile.tags or [],
                "lat": profile.lat,
                "lng": profile.lng,
                "rating_average": rating_avg,
                "rating_count": rating_count,
                "distance_km": distance_km,
                "promo_badge": promo_badge,
                "flash_sale_active": flash_sale_active,
                # Exposes schedule so the customer UI can compute "Opens at HH:MM"
                "business_hours_schedule": profile.business_hours_schedule or {},
            })

        if user_lat is not None:
            results.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 9999))
        else:
            results.sort(key=lambda r: (not r["is_open"], r["name"].lower()))

        _payload = {
            "restaurants": results[:100],
            "filters": {
                "cities": sorted(cities_set),
                "cuisines": sorted(cuisines_set),
                "tags": sorted(all_tags),
            },
        }
        cache.set(_ck, _payload, _PUBLIC_LIST_TTL)
        return Response(_payload)


class MarketplaceMenuView(APIView):
    """GET /api/marketplace/menu/<slug>/ — fetch a restaurant's public menu from the platform.

    Returns profile info + super-categories → categories → dishes (with option groups).
    Only published, available items are included.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug, *args, **kwargs):
        from tenancy.models import Tenant
        from django_tenants.utils import schema_context as _sc

        slug = (slug or "").strip().lower()
        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        # Suspended/canceled tenants are not reachable via the marketplace.
        if tenant.lifecycle_status != Tenant.LifecycleStatus.ACTIVE:
            return Response({"detail": "Restaurant is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

        try:
            with _sc(tenant.schema_name):
                from menu.models import (
                    SuperCategory as _SC,
                    Category as _Cat,
                    Dish as _Dish,
                    OptionGroup as _OG,
                )
                # Profile lives in tenancy.models, NOT menu.models — importing it from
                # menu.models raised ImportError that the outer try/except swallowed into
                # a 500 on every request hitting this path.
                from tenancy.models import Profile as _Profile

                profile = _Profile.objects.filter(tenant=tenant).first()
                if not profile or not profile.is_menu_published:
                    return Response({"detail": "Restaurant menu is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

                # Loyalty config (so the marketplace checkout can offer points redemption).
                from menu.models import LoyaltyConfig as _LCfgM
                _lc = _LCfgM.objects.filter(enabled=True).first()
                loyalty_cfg_data = {
                    "enabled": True,
                    "points_value": str(_lc.points_value),
                    "redeem_threshold": _lc.redeem_threshold,
                    "points_per_unit": _lc.points_per_unit,
                } if _lc else None

                dishes_qs = (
                    _Dish.objects.filter(
                        is_published=True,
                        category__is_published=True,
                        category__is_temporarily_disabled=False,
                        category__super_category__is_temporarily_disabled=False,
                    )
                    .select_related("category__super_category")
                    .prefetch_related("option_groups__options")
                    .order_by("position", "name")
                )

                # Happy-hour pricing — compute active rules ONCE per menu request.
                from menu.pricing import (
                    get_active_happy_hours as _mkt_get_hh,
                    effective_unit_price as _mkt_eff_price,
                    happy_hour_payload as _mkt_hh_payload,
                )
                from menu.views import _profile_now as _mkt_profile_now
                _mkt_menu_now = _mkt_profile_now(profile)
                _mkt_menu_active_hh = _mkt_get_hh(_mkt_menu_now)

                sc_map: dict = {}
                for dish in dishes_qs:
                    cat = dish.category
                    sc = cat.super_category
                    if sc.id not in sc_map:
                        sc_map[sc.id] = {
                            "id": sc.id,
                            "name": sc.name,
                            "name_i18n": sc.name_i18n or {},
                            "position": sc.position,
                            "categories": {},
                        }
                    if cat.id not in sc_map[sc.id]["categories"]:
                        sc_map[sc.id]["categories"][cat.id] = {
                            "id": cat.id,
                            "name": cat.name,
                            "name_i18n": cat.name_i18n or {},
                            "slug": cat.slug,
                            "image_url": cat.image_url or "",
                            "position": cat.position,
                            "dishes": [],
                        }

                    option_groups = []
                    for og in dish.option_groups.all():
                        option_groups.append({
                            "id": og.id,
                            "name": og.name,
                            "name_i18n": getattr(og, "name_i18n", None) or {},
                            "required": og.required,
                            "multi_select": og.multi_select,
                            "max_selections": og.max_selections,
                            "options": [
                                {
                                    "id": opt.id,
                                    "name": opt.name,
                                    "price_delta": str(opt.price_delta),
                                    "is_available": opt.is_available,
                                }
                                for opt in og.options.filter(is_available=True)
                            ],
                        })

                    _mkt_eff, _mkt_rule = _mkt_eff_price(dish, _mkt_menu_active_hh)
                    sc_map[sc.id]["categories"][cat.id]["dishes"].append({
                        "id": dish.id,
                        "slug": dish.slug,
                        "name": dish.name,
                        "name_i18n": dish.name_i18n or {},
                        "description": dish.description or "",
                        "description_i18n": dish.description_i18n or {},
                        "price": str(dish.price),
                        "effective_price": str(_mkt_eff),
                        "happy_hour": _mkt_hh_payload(_mkt_rule),
                        "currency": dish.currency or "USD",
                        "image_url": dish.image_url or "",
                        "tags": dish.tags or [],
                        "allergens": dish.allergens or [],
                        "is_available": dish.is_available,
                        "option_groups": option_groups,
                    })

                super_categories = sorted(sc_map.values(), key=lambda s: (s["position"], s["name"]))
                for sc_entry in super_categories:
                    sc_entry["categories"] = sorted(
                        sc_entry["categories"].values(),
                        key=lambda c: (c["position"], c["name"]),
                    )

                # Rating summary + recent reviews for social proof on the menu page.
                from django.db.models import Avg as _Avg, Count as _Cnt
                from menu.models import Rating as _Rating
                _ragg = _Rating.objects.aggregate(avg=_Avg("score"), cnt=_Cnt("id"))
                rating_average = round(float(_ragg["avg"]), 1) if _ragg["avg"] else None
                rating_count = _ragg["cnt"]
                recent_reviews = [
                    {
                        "score": r.score,
                        "comment": r.comment[:200],
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in _Rating.objects.filter(comment__gt="").order_by("-created_at")[:6]
                ]

                # Trusted-customer cash-on-handover eligibility for the marketplace cart —
                # mirrors menu.views.OrderEligibilityView. The Order count lives in this
                # tenant schema, so compute it inside schema_context. The customer id comes
                # from the marketplace session (authentication_classes is empty, but the
                # session cookie still resolves so request.session is available).
                from menu.views import _cod_eligible as _mkt_menu_cod_eligible
                _mkt_menu_cust_id = request.session.get("customer_id")
                cod_enabled = bool(getattr(profile, "cod_enabled", False))
                cod_eligible = bool(_mkt_menu_cod_eligible(profile, _mkt_menu_cust_id))

        except Exception as exc:
            logger.exception("MarketplaceMenuView error for slug=%s: %s", slug, exc)
            return Response({"detail": "Could not load menu.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        is_open = _compute_is_open_now(profile)

        # ── Flash sale (public schema — no schema_context needed) ─────────────
        flash_sale_info = None
        try:
            from .models import PlatformFlashSale as _PFS, PlatformFlashSaleOptIn as _PFSOI
            _opted_ids = set(
                _PFSOI.objects.filter(tenant_id=tenant.id).values_list("flash_sale_id", flat=True)
            )
            if _opted_ids:
                _best_disc = None
                for _fs in _PFS.objects.filter(id__in=_opted_ids, is_active=True).order_by("-discount_value"):
                    if _fs.is_live():
                        if _best_disc is None or _fs.discount_value > _best_disc:
                            _best_disc = _fs.discount_value
                            flash_sale_info = {
                                "name": _fs.name,
                                "discount_pct": str(_fs.discount_value),
                                "active_until": _fs.active_until.isoformat(),
                            }
        except Exception:
            flash_sale_info = None

        return Response({
            "slug": tenant.slug,
            "name": tenant.name,
            "tagline": profile.tagline or "",
            "logo_url": profile.logo_url or "",
            "cuisine_type": profile.cuisine_type or "",
            "city": profile.city or "",
            "address": profile.address or "",
            "phone": profile.phone or "",
            "currency": getattr(profile, "currency", "USD") or "USD",
            "delivery_enabled": bool(profile.delivery_enabled),
            "delivery_fee": str(profile.delivery_fee) if profile.delivery_fee else "0",
            "delivery_base_fee": str(profile.delivery_base_fee or "0"),
            "delivery_per_km": str(profile.delivery_per_km or "0"),
            "delivery_free_over": str(profile.delivery_free_over or "0"),
            "delivery_radius_km": profile.delivery_radius_km,
            "delivery_minimum_order": str(profile.delivery_minimum_order) if profile.delivery_minimum_order else "0",
            # Restaurant coordinates so the cart can preview a distance-based fee.
            "lat": profile.lat,
            "lng": profile.lng,
            "price_tier": profile.price_tier,
            "tags": profile.tags or [],
            "is_open": is_open,
            "is_menu_temporarily_disabled": bool(getattr(profile, "is_menu_temporarily_disabled", False)),
            "cod_enabled": cod_enabled,
            "cod_eligible": cod_eligible,
            "loyalty": loyalty_cfg_data,
            "flash_sale": flash_sale_info,
            "rating_average": rating_average,
            "rating_count": rating_count,
            "recent_reviews": recent_reviews,
            "super_categories": super_categories,
        })


class MarketplacePlaceOrderView(APIView):
    """POST /api/marketplace/order/ — place an order through the marketplace.

    Runs in the PUBLIC schema but uses schema_context to create the order
    inside the target restaurant's tenant schema.

    Body:
      restaurant  (str)   — tenant slug
      items       (list)  — [{slug, qty, note?, option_ids?}]
      fulfillment_type    — "pickup" | "delivery"
      customer_name (str)
      customer_phone (str)
      customer_note (str)
      delivery_address (str)
      delivery_location_url (str)
      delivery_lat / delivery_lng (float)
      use_wallet (bool)
    """

    permission_classes = [AllowAny]
    throttle_classes = [MarketplaceOrderThrottle]

    def post(self, request, *args, **kwargs):
        from decimal import Decimal, InvalidOperation
        from tenancy.models import Tenant
        from django_tenants.utils import schema_context as _sc
        import secrets as _sec

        # OPS-3: read the client-minted idempotency key before ANY work. If a
        # prior Order with this key already exists inside the tenant schema we
        # return it immediately without re-decrementing stock or re-charging the
        # wallet. This closes the timeout+retry double-order / double-charge gap.
        _mkt_idem_key = str(request.data.get("idempotency_key") or "").strip()[:64] or None

        restaurant_slug = (request.data.get("restaurant") or "").strip().lower()
        if not restaurant_slug:
            return Response({"detail": "restaurant is required.", "code": "missing_restaurant"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(slug=restaurant_slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        # Refuse marketplace orders to suspended/canceled tenants.
        if tenant.lifecycle_status != Tenant.LifecycleStatus.ACTIVE:
            return Response({"detail": "Restaurant is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

        _customer_id = request.session.get("customer_id")
        _linked_customer = None
        if _customer_id:
            try:
                _linked_customer = Customer.objects.get(pk=_customer_id)
            except Customer.DoesNotExist:
                request.session.pop("customer_id", None)

        items_raw = request.data.get("items") or []
        if not items_raw or not isinstance(items_raw, list):
            return Response({"detail": "items is required.", "code": "missing_items"}, status=status.HTTP_400_BAD_REQUEST)

        fulfillment_type = (request.data.get("fulfillment_type") or "pickup").strip().lower()
        if fulfillment_type not in ("pickup", "delivery"):
            fulfillment_type = "pickup"

        customer_name = (request.data.get("customer_name") or "").strip()[:80]
        customer_phone = (request.data.get("customer_phone") or "").strip()[:30]
        customer_note = (request.data.get("customer_note") or "").strip()[:300]
        delivery_address = (request.data.get("delivery_address") or "").strip()[:180]
        _raw_loc_url = (request.data.get("delivery_location_url") or "").strip()[:500]
        # Only allow http/https schemes — reject javascript:, data:, etc.
        delivery_location_url = (
            _raw_loc_url
            if _raw_loc_url.startswith(("http://", "https://"))
            else ""
        )
        use_wallet = bool(request.data.get("use_wallet")) and _linked_customer is not None

        delivery_lat = _parse_coord(request.data.get("delivery_lat"), -90, 90)
        delivery_lng = _parse_coord(request.data.get("delivery_lng"), -180, 180)

        if fulfillment_type == "delivery" and _linked_customer is None:
            return Response(
                {"detail": "Delivery orders require a signed-in account.", "code": "auth_required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with _sc(tenant.schema_name):
                from menu.models import (
                    Dish as _Dish,
                    DishOption as _DO,
                    Order as _Order,
                    OrderItem as _OI,
                    Promotion as _Promo,
                )
                # Profile lives in tenancy.models, NOT menu.models — importing it from
                # menu.models raised ImportError that the outer try/except swallowed into
                # a 500 on every marketplace order placement.
                from tenancy.models import Profile as _Profile
                from django.db import transaction as _dbtx, IntegrityError as _IE

                # OPS-3: idempotency pre-check inside the tenant schema.
                # If a prior Order with this key exists, return it without
                # any stock decrement or wallet charge.
                if _mkt_idem_key:
                    try:
                        _existing = _Order.objects.filter(idempotency_key=_mkt_idem_key).first()
                        if _existing is not None:
                            return Response({
                                "order_number": _existing.order_number,
                                "status": _existing.status,
                                "total": str(_existing.total),
                                "delivery_fee": str(_existing.delivery_fee),
                                "wallet_amount_paid": str(_existing.wallet_amount_paid),
                                "commission_amount": str(_existing.commission_amount),
                                "promotion_discount": str(_existing.promotion_discount),
                                "applied_promotion_name": _existing.applied_promotion_name,
                                "loyalty_discount": str(_existing.loyalty_discount),
                                "redeemed_loyalty_points": _existing.redeemed_loyalty_points,
                                "points_earned": _existing.points_earned,
                                "scheduled_for": _existing.scheduled_for.isoformat() if _existing.scheduled_for else None,
                                "currency": _existing.currency,
                                "restaurant_slug": tenant.slug,
                                "restaurant_name": tenant.name,
                                "idempotent_replay": True,
                            }, status=status.HTTP_201_CREATED)
                    except Exception:
                        pass  # If the lookup fails, continue with normal placement

                profile = _Profile.objects.filter(tenant=tenant).first()
                if not profile or not profile.is_menu_published:
                    return Response({"detail": "Restaurant is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

                # Advance/scheduled order — may be placed while currently closed (it's for a
                # future open slot); the time is validated against business hours below.
                _wants_schedule = bool(request.data.get("scheduled_for"))
                if not _wants_schedule and not _compute_is_open_now(profile):
                    return Response(
                        {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Validate the requested advance-fulfilment time (pickup/delivery only,
                # future within the lead window, inside opening hours). Reuses the same
                # helpers as the direct checkout for identical behaviour.
                _scheduled_for = None
                _sched_raw = request.data.get("scheduled_for")
                if _sched_raw:
                    from menu.views import _validate_scheduled_for as _vsf
                    from datetime import datetime as _dt
                    try:
                        _parsed_dt = _dt.fromisoformat(str(_sched_raw).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        return Response({"detail": "Invalid scheduled time.", "code": "schedule_invalid"},
                                        status=status.HTTP_400_BAD_REQUEST)
                    _scheduled_for, _sched_err = _vsf(profile, fulfillment_type, _parsed_dt)
                    if _sched_err:
                        _sched_msgs = {
                            "schedule_not_supported": "Only pickup and delivery orders can be scheduled in advance.",
                            "schedule_too_soon": "Please choose a time at least 30 minutes from now.",
                            "schedule_too_far": "Scheduled orders can be placed up to 14 days ahead.",
                            "schedule_closed": "The restaurant is closed at that time. Please pick a time within opening hours.",
                        }
                        return Response({"detail": _sched_msgs.get(_sched_err, "That scheduled time isn't available."),
                                         "code": _sched_err}, status=status.HTTP_400_BAD_REQUEST)
                _is_scheduled = _scheduled_for is not None

                slugs = []
                for it in items_raw:
                    if not isinstance(it, dict) or not it.get("slug"):
                        return Response({"detail": "Each item must have a slug.", "code": "invalid_items"}, status=status.HTTP_400_BAD_REQUEST)
                    slugs.append(str(it["slug"]))

                dishes_map = {
                    d.slug: d
                    for d in _Dish.objects.filter(
                        slug__in=slugs, is_published=True, is_available=True,
                        category__is_published=True, category__is_temporarily_disabled=False,
                    ).select_related("category").prefetch_related("combo_components__component")
                }
                missing = [s for s in slugs if s not in dishes_map]
                if missing:
                    return Response({"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing}, status=status.HTTP_400_BAD_REQUEST)

                all_option_ids = [int(oid) for it in items_raw for oid in (it.get("option_ids") or []) if str(oid).isdigit()]
                # OPS-5f: select_related("dish") so we can bind each option to its dish
                # and reject foreign / cross-dish option ids (mirrors menu/views.py:1647).
                # Without this, a customer could attach a foreign or negative-price_delta
                # option to a cheap dish and drive the wallet-PREPAID total DOWN.
                options_map = (
                    {o.id: o for o in _DO.objects.filter(id__in=all_option_ids).select_related("dish")}
                    if all_option_ids
                    else {}
                )

                # Compute active happy-hour rules ONCE (placement-time price lock —
                # for scheduled orders price is locked at submission, not scheduled_for;
                # the customer is prepaid at placement so this is defensible).
                from menu.pricing import (
                    get_active_happy_hours as _get_hh,
                    effective_unit_price as _eff_price,
                )
                from menu.views import _profile_now as _pnow
                _mkt_now_local = _pnow(profile)
                _mkt_active_hh = _get_hh(_mkt_now_local)

                order_items_data = []
                food_subtotal = Decimal("0")
                currency = "USD"
                # combo component stock updates: (component_pk, total_qty, name)
                _mkt_component_stock_updates = []

                for it in items_raw:
                    dish = dishes_map[it["slug"]]
                    currency = dish.currency or "USD"
                    # Apply happy-hour discount; option price_delta added below unchanged.
                    unit_price, _ = _eff_price(dish, _mkt_active_hh)
                    # OPS-5f: validate each option is bound to THIS dish before pricing.
                    # An option whose dish != this dish (foreign id, cross-dish id, or an
                    # unknown id) is rejected — exactly like the other order paths
                    # (menu/views.py:1647-1664) — so price_delta can't be smuggled in.
                    _invalid_option_ids = []
                    _bound_options = []
                    for oid in (it.get("option_ids") or []):
                        opt = options_map.get(int(oid)) if str(oid).isdigit() else None
                        opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
                        if opt is None or opt_dish_slug != dish.slug:
                            _invalid_option_ids.append(oid)
                            continue
                        _bound_options.append(opt)
                    if _invalid_option_ids:
                        return Response(
                            {
                                "detail": f"Some selected options are no longer valid for '{dish.name}'.",
                                "code": "stale_options",
                                "dish_slug": dish.slug,
                                "invalid_option_ids": _invalid_option_ids,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    option_snapshots = []
                    for opt in _bound_options:
                        unit_price += Decimal(str(opt.price_delta))
                        option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})
                    qty = max(1, min(99, int(it.get("qty", 1))))
                    subtotal = unit_price * qty
                    food_subtotal += subtotal
                    # Build combo snapshot (per-unit qty, not pre-multiplied)
                    _mkt_combo_snapshot = [
                        {"dish_id": cc.component_id, "name": cc.component.name, "qty": cc.qty}
                        for cc in dish.combo_components.all()
                    ]
                    # Snapshot course from category at placement time (0 when category missing)
                    _mkt_course_snap = int(getattr(getattr(dish, "category", None), "course", 0) or 0)
                    order_items_data.append({
                        "dish_slug": dish.slug,
                        "dish_name": dish.name,
                        "unit_price": unit_price,
                        "qty": qty,
                        "note": str(it.get("note") or "")[:120],
                        "options": option_snapshots,
                        "subtotal": subtotal,
                        "combo_components": _mkt_combo_snapshot,
                        "course": _mkt_course_snap,
                    })
                    for _cc_snap in _mkt_combo_snapshot:
                        _mkt_component_stock_updates.append(
                            (_cc_snap["dish_id"], _cc_snap["qty"] * qty, _cc_snap["name"])
                        )

                # Delivery fee — distance-based (base + per-km) when configured,
                # else the flat fallback fee. Driver keeps 100% of it.
                _delivery_fee = Decimal("0")
                _delivery_distance_km = None
                if fulfillment_type == "delivery":
                    from tenancy.delivery_pricing import compute_delivery_fee, valid_coord
                    from tenancy.routing import road_distance_km
                    _plat = getattr(profile, "lat", None)
                    _plng = getattr(profile, "lng", None)
                    # Only compute distance when BOTH points are valid real coords;
                    # missing / (0,0) / out-of-range → flat fee, never a false reject.
                    if valid_coord(_plat, _plng) and valid_coord(delivery_lat, delivery_lng):
                        # Road distance (haversine × factor, or a real OSRM route when
                        # DELIVERY_OSRM_URL is set) — closer to what the driver drives.
                        _delivery_distance_km = road_distance_km(
                            _plat, _plng, delivery_lat, delivery_lng
                        )
                    _pricing = compute_delivery_fee(
                        profile, distance_km=_delivery_distance_km, food_subtotal=food_subtotal
                    )
                    if _pricing["out_of_range"]:
                        return Response(
                            {
                                "detail": "This address is outside the restaurant's delivery area.",
                                "code": "delivery_out_of_range",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    _delivery_fee = _pricing["fee"]

                # Best restaurant promo — evaluate the window in the TENANT's local
                # wall-clock time (a promo "Tue 14:00–16:00" is tenant-local), not the
                # server's. See menu.promos for the single windowing rule.
                from datetime import datetime as _promo_dt
                from zoneinfo import ZoneInfo as _PromoZI
                try:
                    _promo_now_local = _promo_dt.now(_PromoZI((getattr(profile, "timezone", "") or "UTC")))
                except Exception:
                    _promo_now_local = _promo_dt.now(_PromoZI("UTC"))
                _best_promo = None
                _promo_discount = Decimal("0")
                for _p in _Promo.objects.filter(is_active=True).order_by("-discount_value"):
                    if _p.max_uses is not None and _p.use_count >= _p.max_uses:
                        continue
                    if Decimal(str(_p.min_order_amount or "0")) > food_subtotal:
                        continue
                    if not _is_promo_active_now(_p, now_local=_promo_now_local):
                        continue
                    _d_amt = Decimal("0")
                    if _p.promo_type == "percentage":
                        _d_amt = (food_subtotal * min(Decimal("100"), Decimal(str(_p.discount_value))) / Decimal("100")).quantize(Decimal("0.01"))
                    elif _p.promo_type == "fixed":
                        _d_amt = min(food_subtotal, Decimal(str(_p.discount_value))).quantize(Decimal("0.01"))
                    elif _p.promo_type == "free_delivery":
                        _d_amt = _delivery_fee
                    if _d_amt > _promo_discount:
                        _promo_discount = _d_amt
                        _best_promo = _p

                # Check for opted-in platform flash sales
                _flash_sale_used = None
                _flash_discount = Decimal("0")
                try:
                    from .models import PlatformFlashSale as _PFS, PlatformFlashSaleOptIn as _PFSOI
                    _opted_sale_ids = set(
                        _PFSOI.objects.filter(tenant_id=tenant.id).values_list("flash_sale_id", flat=True)
                    )
                    if _opted_sale_ids:
                        for _fs in _PFS.objects.filter(id__in=_opted_sale_ids, is_active=True):
                            if _fs.is_live():
                                _fd = (
                                    food_subtotal
                                    * min(Decimal("100"), Decimal(str(_fs.discount_value)))
                                    / Decimal("100")
                                ).quantize(Decimal("0.01"))
                                if _fd > _flash_discount:
                                    _flash_discount = _fd
                                    _flash_sale_used = _fs
                except Exception:
                    _flash_discount = Decimal("0")

                # Use the better of restaurant promo vs platform flash sale (no stacking)
                _applied_promo_name = _best_promo.name if _best_promo else ""
                if _flash_discount > _promo_discount:
                    _promo_discount = _flash_discount
                    _best_promo = None
                    _applied_promo_name = f"Flash Sale: {_flash_sale_used.name}" if _flash_sale_used else "Flash Sale"

                total = max(Decimal("0"), food_subtotal + _delivery_fee - _promo_discount)

                # ── Loyalty redemption at checkout (mirrors the direct flow) ──────────
                _loyalty_discount = Decimal("0")
                _loyalty_points_spent = 0
                try:
                    _redeem_points = int(request.data.get("redeem_points", 0) or 0)
                except (TypeError, ValueError):
                    _redeem_points = 0
                if _redeem_points > 0:
                    if _linked_customer is None:
                        return Response({"detail": "Sign in to redeem points.", "code": "auth_required"},
                                        status=status.HTTP_403_FORBIDDEN)
                    from menu.models import LoyaltyConfig as _LCfg
                    from menu.views import _size_loyalty_redemption as _slr
                    _lc = _LCfg.objects.filter(enabled=True).first()
                    _loyalty_discount, _loyalty_points_spent, _loy_err = _slr(
                        _lc, getattr(_linked_customer, "loyalty_points", 0), _redeem_points, total,
                    )
                    if _loy_err:
                        _loy_msgs = {
                            "loyalty_disabled": "Loyalty isn't available right now.",
                            "loyalty_insufficient_points": "You don't have that many points.",
                            "loyalty_below_threshold": f"Redeem at least {getattr(_lc, 'redeem_threshold', 0)} points.",
                        }
                        return Response({"detail": _loy_msgs.get(_loy_err, "Couldn't redeem your points."),
                                         "code": _loy_err}, status=status.HTTP_400_BAD_REQUEST)
                    total = max(Decimal("0"), total - _loyalty_discount)

                # A5: the platform's take rate is per-tenant (Profile.marketplace_commission_pct,
                # a fraction — 0.10 = 10%), defaulting to 0.10 so behaviour is unchanged unless
                # the platform overrides it for this tenant. Fall back to 0.10 if the field is
                # null/missing/unparseable (a malformed rate must never 500 a checkout). The
                # BASIS is unchanged — still food_subtotal, the PRE-discount food total (switching
                # to post-discount food is an owner decision; see A5-followup).
                _mkt_rate_raw = getattr(profile, "marketplace_commission_pct", None)
                try:
                    commission_rate = (
                        Decimal(str(_mkt_rate_raw)) if _mkt_rate_raw is not None else Decimal("0.10")
                    )
                except (InvalidOperation, ValueError, TypeError):
                    commission_rate = Decimal("0.10")
                commission_amount = (food_subtotal * commission_rate).quantize(Decimal("0.01"))

                # Marketplace pickup & delivery are pay-now: the bill must be settled in
                # full from the customer's wallet at checkout (mirrors the restaurant
                # flow). There is no dine-in on the marketplace.
                #
                # Trusted-customer cash-on-handover (COD): a repeat customer (owner has
                # COD enabled + the customer has enough completed/paid orders here) may
                # choose to pay cash to the staff/driver instead of prepaying from the
                # wallet — exactly like the direct PlaceOrderView path. Such orders are
                # created UNPAID and settled at handover (driver collects for delivery).
                _mkt_cod_order = False
                _requires_prepay = fulfillment_type in ("pickup", "delivery")
                if _requires_prepay and total > Decimal("0"):
                    if _linked_customer is None:
                        return Response(
                            {"detail": "Sign in and top up your wallet to place this order.",
                             "code": "auth_required"},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    from menu.views import _cod_eligible as _mkt_cod_eligible
                    _mkt_pay_method = str(request.data.get("payment_method") or "").strip().lower()
                    # Advance/scheduled orders are prepaid at placement (no cash-on-handover)
                    # so the slot is genuinely committed and no-shows can't tie up stock unpaid.
                    if (
                        _mkt_pay_method == "cash"
                        and not _wants_schedule
                        and _mkt_cod_eligible(profile, _linked_customer.id)
                    ):
                        _mkt_cod_order = True
                        use_wallet = False  # cash on handover — do not require/deduct wallet
                    else:
                        _wallet_avail = Decimal(str(_linked_customer.wallet_balance or "0"))
                        if _wallet_avail < total:
                            return Response(
                                {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                                 "code": "wallet_insufficient",
                                 "balance": str(_wallet_avail), "amount_due": str(total)},
                                status=status.HTTP_402_PAYMENT_REQUIRED,
                            )
                        use_wallet = True  # pay-now: always settle from the wallet

                _stock_updates = []
                _pk_to_slug = {}
                for _item_d in order_items_data:
                    _d = dishes_map[_item_d["dish_slug"]]
                    _pk_to_slug[_d.pk] = _d.slug
                    if _d.stock_qty is not None:
                        _stock_updates.append((_d.pk, _item_d["qty"]))

                # Aggregate component stock updates from the snapshots
                _mkt_comp_pk_to_name: dict = {}
                _mkt_comp_stock_agg: dict = {}
                for _cpk, _cqty, _cname in _mkt_component_stock_updates:
                    _mkt_comp_stock_agg[_cpk] = _mkt_comp_stock_agg.get(_cpk, 0) + _cqty
                    _mkt_comp_pk_to_name[_cpk] = _cname
                _mkt_all_stock_pks = [pk for pk, _ in _stock_updates]
                _mkt_all_stock_pks += [pk for pk in _mkt_comp_stock_agg if pk not in _mkt_all_stock_pks]

                _wallet_deduction = Decimal("0")
                if use_wallet and _linked_customer:
                    _available = Decimal(str(_linked_customer.wallet_balance or "0"))
                    _wallet_deduction = min(_available, total)
                    if _wallet_deduction <= Decimal("0"):
                        _wallet_deduction = Decimal("0")

                class _OutOfStock(Exception):
                    def __init__(self, slug):
                        self.slug = slug

                class _PrepayUnpaid(Exception):
                    """Pay-now order couldn't be fully settled from the wallet — roll back."""

                class _LoyaltyShort(Exception):
                    """Loyalty balance no longer covers the redemption — roll the order back."""

                class _PromoCapped(Exception):
                    """OPS-4 F: Bounded promo counter returned 0 rows — cap reached concurrently.
                    Marketplace always auto-applies promos (no code input), so strip the discount
                    from this order: total is corrected and the order places without a discount.
                    This exception is never raised in the marketplace path — the inline handler
                    strips the discount and continues rather than aborting.  The class is retained
                    for symmetry with the direct checkout and for the PromoCapped re-raise path
                    (code-based promos on marketplace are not currently supported, but if added
                    later, raising _PromoCapped would propagate to the outer handler).
                    """

                if fulfillment_type == "delivery" and _linked_customer:
                    customer_name = _linked_customer.name or customer_name
                    customer_phone = _linked_customer.phone or customer_phone

                try:
                    with _dbtx.atomic():
                        if _mkt_all_stock_pks:
                            _locked = {
                                d.pk: d
                                for d in _Dish.objects.select_for_update().filter(pk__in=_mkt_all_stock_pks)
                            }
                        else:
                            _locked = {}

                        if _stock_updates:
                            for _dish_pk, _ordered_qty in _stock_updates:
                                _ld = _locked.get(_dish_pk)
                                if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered_qty:
                                    raise _OutOfStock(_pk_to_slug.get(_dish_pk, ""))
                            for _dish_pk, _ordered_qty in _stock_updates:
                                _ld = _locked.get(_dish_pk)
                                if _ld and _ld.stock_qty is not None:
                                    _new_qty = max(0, _ld.stock_qty - _ordered_qty)
                                    _update_fields = {"stock_qty": _new_qty}
                                    if _new_qty == 0:
                                        _update_fields["is_available"] = False
                                        _update_fields["stock_auto_zeroed"] = True
                                    _Dish.objects.filter(pk=_dish_pk).update(**_update_fields)

                        # Component stock: validate then decrement
                        if _mkt_comp_stock_agg:
                            for _cpk, _cqty in _mkt_comp_stock_agg.items():
                                _ld = _locked.get(_cpk)
                                if _ld and _ld.stock_qty is not None and _ld.stock_qty < _cqty:
                                    raise _OutOfStock(_mkt_comp_pk_to_name.get(_cpk, ""))
                            for _cpk, _cqty in _mkt_comp_stock_agg.items():
                                _ld = _locked.get(_cpk)
                                if _ld and _ld.stock_qty is not None:
                                    _cnew = max(0, _ld.stock_qty - _cqty)
                                    _cupdate_fields = {"stock_qty": _cnew}
                                    if _cnew == 0:
                                        _cupdate_fields["is_available"] = False
                                        _cupdate_fields["stock_auto_zeroed"] = True
                                    _Dish.objects.filter(pk=_cpk).update(**_cupdate_fields)

                        # OPS-4 F: Atomic bounded promo counter — must run BEFORE Order.create().
                        # Marketplace only auto-applies promos (no customer code input), so a
                        # concurrent cap hit strips the discount and the order places at full price.
                        # max_uses=None → unlimited → no cap to enforce, safe to increment.
                        from django.db.models import F as _F
                        if _best_promo is not None:
                            if _best_promo.max_uses is not None:
                                _mkt_promo_rows = _Promo.objects.filter(
                                    pk=_best_promo.pk,
                                    use_count__lt=_best_promo.max_uses,
                                ).update(use_count=_F("use_count") + 1)
                                if not _mkt_promo_rows:
                                    # Cap reached concurrently — strip discount, place at full price
                                    total = max(Decimal("0"), food_subtotal + _delivery_fee)
                                    _promo_discount = Decimal("0")
                                    _best_promo = None
                                    _applied_promo_name = ""
                                    # Re-check wallet balance for pay-now orders
                                    if use_wallet and _linked_customer and _requires_prepay:
                                        _wallet_avail_now = Decimal(str(_linked_customer.wallet_balance or "0"))
                                        if _wallet_avail_now < total:
                                            raise _PrepayUnpaid()
                                    # Recalculate wallet deduction cap
                                    if use_wallet and _linked_customer:
                                        _available_now = Decimal(str(_linked_customer.wallet_balance or "0"))
                                        _wallet_deduction = min(_available_now, total)
                            else:
                                # max_uses is None → unlimited → no cap to enforce
                                _Promo.objects.filter(pk=_best_promo.pk).update(use_count=_F("use_count") + 1)

                        for _attempt in range(10):
                            _candidate = f"ORD-{_sec.token_hex(3).upper()}"
                            if not _Order.objects.filter(order_number=_candidate).exists():
                                order_number = _candidate
                                break
                        else:
                            return Response({"detail": "Order could not be placed. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

                        from menu.views import _generate_delivery_code as _gen_delivery_code
                        order = _Order.objects.create(
                            order_number=order_number,
                            status=_Order.Status.SCHEDULED if _is_scheduled else _Order.Status.PENDING,
                            scheduled_for=_scheduled_for,
                            customer=_linked_customer,
                            customer_name=customer_name,
                            customer_phone=customer_phone,
                            customer_note=customer_note,
                            fulfillment_type=fulfillment_type,
                            delivery_address=delivery_address,
                            delivery_location_url=delivery_location_url,
                            delivery_lat=delivery_lat,
                            delivery_lng=delivery_lng,
                            delivery_code=(_gen_delivery_code() if fulfillment_type == "delivery" else ""),
                            total=total,
                            delivery_fee=_delivery_fee,
                            currency=currency,
                            source=_Order.Source.MARKETPLACE,
                            commission_amount=commission_amount,
                            commission_rate_applied=commission_rate,
                            promotion_discount=_promo_discount,
                            applied_promotion_name=_applied_promo_name,
                            loyalty_discount=_loyalty_discount,
                            redeemed_loyalty_points=(_loyalty_points_spent or None),
                            idempotency_key=_mkt_idem_key,
                        )
                        for item_data in order_items_data:
                            _OI.objects.create(order=order, **item_data)

                        # Debit redeemed loyalty points atomically (guarded UPDATE; rolls
                        # back if the balance changed under us).
                        if _loyalty_points_spent > 0 and _linked_customer:
                            from django.db.models import F as _Floy
                            _ok = Customer.objects.filter(
                                pk=_linked_customer.pk,
                                loyalty_points__gte=_loyalty_points_spent,
                            ).update(loyalty_points=_Floy("loyalty_points") - _loyalty_points_spent)
                            if not _ok:
                                raise _LoyaltyShort()

                        # (Restaurant promo use_count was incremented before Order.create() — see OPS-4 F.)

                        # Increment platform flash sale redemption_count atomically
                        if _flash_sale_used is not None:
                            from .models import PlatformFlashSale as _PFS2
                            from django.db.models import F as _F2
                            _PFS2.objects.filter(pk=_flash_sale_used.pk).update(redemption_count=_F2("redemption_count") + 1)

                        # Wallet deduction
                        _paid_by_wallet = Decimal("0")
                        if _wallet_deduction > Decimal("0") and _linked_customer:
                            from .models import WalletTransaction as _WTM
                            _cust_locked = Customer.objects.select_for_update().get(pk=_linked_customer.pk)
                            _actual = min(Decimal(str(_cust_locked.wallet_balance or "0")), _wallet_deduction)
                            if _actual > Decimal("0"):
                                _cust_locked.wallet_balance = _cust_locked.wallet_balance - _actual
                                _cust_locked.save(update_fields=["wallet_balance", "updated_at"])
                                _WTM.objects.create(
                                    customer=_cust_locked,
                                    type=_WTM.Type.PAYMENT,
                                    amount=_actual,
                                    reference=order.order_number,
                                    tenant_id=tenant.id,
                                    balance_after=_cust_locked.wallet_balance,
                                )
                                order.wallet_amount_paid = _actual
                                order.save(update_fields=["wallet_amount_paid"])
                                _paid_by_wallet = _actual

                        # Settle payment state — PAID once wallet credits (or a
                        # zero total) fully cover it; otherwise UNPAID and the
                        # balance is collected on delivery/pickup.
                        if total <= Decimal("0") or _paid_by_wallet >= total:
                            from django.utils import timezone as _tz
                            order.payment_status = _Order.PaymentStatus.PAID
                            order.paid_at = _tz.now()
                            order.save(update_fields=["payment_status", "paid_at"])

                        # Pay-now safety net: roll back if a pickup/delivery order wasn't
                        # fully settled (e.g. balance dropped under the lock). A trusted
                        # cash-on-handover order is DELIBERATELY left unpaid (settled at
                        # handover), so it must not trip this gate — use_wallet=False above
                        # already prevents any wallet deduction for it.
                        if (
                            _requires_prepay
                            and not _mkt_cod_order
                            and order.payment_status != _Order.PaymentStatus.PAID
                        ):
                            raise _PrepayUnpaid()

                        # Award loyalty points (parity with the direct checkout — the
                        # marketplace path previously skipped this). Best-effort.
                        try:
                            from menu.models import LoyaltyConfig as _LCfgEarn
                            _earn_cfg = _LCfgEarn.objects.filter(enabled=True).first()
                            if _earn_cfg and _linked_customer is not None:
                                _pts = int(float(food_subtotal) * int(_earn_cfg.points_per_unit))
                                if _pts > 0:
                                    from django.db.models import F as _Fearn
                                    Customer.objects.filter(pk=_linked_customer.pk).update(
                                        loyalty_points=_Fearn("loyalty_points") + _pts
                                    )
                                    _Order.objects.filter(pk=order.pk).update(points_earned=_pts)
                        except Exception:
                            pass  # never fail the order over loyalty accounting

                except _PrepayUnpaid:
                    return Response(
                        {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                         "code": "wallet_insufficient"},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                except _LoyaltyShort:
                    return Response(
                        {"detail": "Your loyalty points balance changed — please review and try again.",
                         "code": "loyalty_insufficient_points"},
                        status=status.HTTP_409_CONFLICT,
                    )
                except _OutOfStock as _e:
                    return Response(
                        {"detail": "Item sold out.", "code": "items_unavailable", "slugs": [_e.slug]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except _IE:
                    # OPS-3: the unique constraint on idempotency_key fired —
                    # a concurrent request already committed an identical order.
                    # Re-fetch the winner and return it as a successful replay
                    # so the client is not left with a 503 it would retry again.
                    if _mkt_idem_key:
                        try:
                            _winner = _Order.objects.filter(idempotency_key=_mkt_idem_key).first()
                            if _winner is not None:
                                return Response({
                                    "order_number": _winner.order_number,
                                    "status": _winner.status,
                                    "total": str(_winner.total),
                                    "delivery_fee": str(_winner.delivery_fee),
                                    "wallet_amount_paid": str(_winner.wallet_amount_paid),
                                    "commission_amount": str(_winner.commission_amount),
                                    "promotion_discount": str(_winner.promotion_discount),
                                    "applied_promotion_name": _winner.applied_promotion_name,
                                    "loyalty_discount": str(_winner.loyalty_discount),
                                    "redeemed_loyalty_points": _winner.redeemed_loyalty_points,
                                    "points_earned": _winner.points_earned,
                                    "scheduled_for": _winner.scheduled_for.isoformat() if _winner.scheduled_for else None,
                                    "currency": _winner.currency,
                                    "restaurant_slug": tenant.slug,
                                    "restaurant_name": tenant.name,
                                    "idempotent_replay": True,
                                }, status=status.HTTP_201_CREATED)
                        except Exception:
                            pass
                    return Response(
                        {"detail": "Order could not be placed due to a conflict. Please try again."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

                # Platform delivery: spawn a searching driver job and dispatch to online
                # drivers. Best-effort and post-commit — a hiccup must never affect the order.
                # Scheduled orders skip dispatch now — the release sweep fires it at the time.
                if not _is_scheduled and fulfillment_type == "delivery" and getattr(profile, "platform_delivery_enabled", False):
                    try:
                        from .models import DeliveryJob as _DJob
                        from tenancy.delivery_pricing import split_delivery_fee as _split_fee
                        # Split the fee into driver payout + platform cut (default 0% →
                        # driver keeps 100%); snapshot both on the job for audit.
                        _dsplit = _split_fee(profile, _delivery_fee)
                        _job = _DJob.objects.create(
                            tenant_id=tenant.id,
                            order_number=order.order_number,
                            status=_DJob.Status.SEARCHING,
                            pickup_address=(getattr(profile, "address", "") or "")[:200],
                            pickup_lat=getattr(profile, "lat", None),
                            pickup_lng=getattr(profile, "lng", None),
                            delivery_address=(delivery_address or "")[:200],
                            delivery_lat=delivery_lat,
                            delivery_lng=delivery_lng,
                            delivery_fee=_delivery_fee,
                            driver_payout=_dsplit["driver_payout"],
                            platform_commission=_dsplit["platform_commission"],
                        )
                        # Ranked dispatch: offer nearest free driver first, cascade,
                        # then fall back to the open pool.
                        from accounts.dispatch import start_dispatch
                        start_dispatch(_job)
                    except Exception:
                        pass

        except Exception as exc:
            logger.exception("MarketplacePlaceOrderView error for tenant=%s: %s", restaurant_slug, exc)
            return Response({"detail": "Could not place order.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "commission_amount": str(order.commission_amount),
            "promotion_discount": str(order.promotion_discount),
            "applied_promotion_name": order.applied_promotion_name,
            "loyalty_discount": str(order.loyalty_discount),
            "redeemed_loyalty_points": order.redeemed_loyalty_points,
            "points_earned": order.points_earned,
            "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
            "currency": order.currency,
            "restaurant_slug": tenant.slug,
            "restaurant_name": tenant.name,
        }, status=status.HTTP_201_CREATED)


class MarketplaceOrderStatusView(APIView):
    """GET /api/marketplace/order/<order_number>/?restaurant=<slug> — poll order status."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [MarketplaceOrderStatusThrottle]

    def get(self, request, order_number, *args, **kwargs):
        from tenancy.models import Tenant
        from django_tenants.utils import schema_context as _sc

        slug = (request.query_params.get("restaurant") or "").strip().lower()
        order_number = (order_number or "").strip().upper()

        if not slug:
            return Response({"detail": "restaurant query param is required.", "code": "missing_restaurant"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            with _sc(tenant.schema_name):
                from menu.models import Order as _Order
                order = (
                    _Order.objects
                    .filter(order_number=order_number)
                    .prefetch_related("items")
                    .first()
                )
                if order is None:
                    return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

                # Ownership gate — this endpoint is AllowAny and order numbers are
                # ORD-+token_hex(3) (24 bits → enumerable), so the financial body
                # (items, totals, payment_status, wallet/loyalty/promo, schedule)
                # MUST be confined to the session customer who owns the order.
                # A non-owner gets only a minimal, non-sensitive status. The items
                # query is built INSIDE the schema_context, so compute ownership
                # here before deciding whether to materialise it.
                _scid = getattr(request, "session", None) and request.session.get("customer_id")
                try:
                    _owns = bool(_scid and order.customer_id and int(_scid) == int(order.customer_id))
                except (TypeError, ValueError):
                    _owns = False

                items = []
                if _owns:
                    items = [
                        {
                            "dish_slug": item.dish_slug,
                            "dish_name": item.dish_name,
                            "qty": item.qty,
                            "unit_price": str(item.unit_price),
                            "subtotal": str(item.subtotal),
                            "options": item.options,
                            "note": item.note,
                            "is_voided": item.is_voided,
                            "combo_components": item.combo_components,
                        }
                        for item in order.items.all()
                    ]
        except Exception as exc:
            logger.exception("MarketplaceOrderStatusView error for order=%s tenant=%s: %s", order_number, slug, exc)
            return Response({"detail": "Could not load order.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Non-owner (or anonymous): minimal status only — no financial detail.
        if not _owns:
            return Response({
                "order_number": order.order_number,
                "status": order.status,
                "fulfillment_type": order.fulfillment_type,
                "restaurant_slug": slug,
                "restaurant_name": tenant.name,
            })

        # Owner-only from here down — full financial body + ownership affordances.
        can_cancel = False
        delivery_code = None
        try:
            from menu.views import _customer_can_cancel as _ccc
            can_cancel = bool(_ccc(order))
            # Proof-of-delivery code — active delivery orders.
            if (getattr(order, "delivery_code", "")
                    and order.fulfillment_type == "delivery"
                    and order.status not in ("completed", "cancelled")):
                delivery_code = order.delivery_code
        except Exception:
            can_cancel = False

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "can_cancel": can_cancel,
            "delivery_code": delivery_code,
            "payment_status": order.payment_status,
            "fulfillment_type": order.fulfillment_type,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "loyalty_discount": str(order.loyalty_discount),
            "redeemed_loyalty_points": order.redeemed_loyalty_points,
            "points_earned": order.points_earned,
            "promotion_discount": str(order.promotion_discount),
            "applied_promotion_name": order.applied_promotion_name or "",
            "currency": order.currency,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
            "items": items,
            "restaurant_slug": slug,
            "restaurant_name": tenant.name,
        })


class MarketplaceOrderCancelView(APIView):
    """POST /api/marketplace/order/<order_number>/cancel/ — a signed-in customer cancels
    their OWN early marketplace pickup/delivery order. Body/query: restaurant=<slug>.
    Refunds any wallet payment, reverses loyalty (claw back earned / restore spent), and
    restocks — reusing the same helpers as the direct flow. Session ownership required.
    """

    permission_classes = [AllowAny]
    throttle_classes = [MarketplaceOrderStatusThrottle]

    def post(self, request, order_number, *args, **kwargs):
        from tenancy.models import Tenant
        from django_tenants.utils import schema_context as _sc
        from django.utils import timezone as _tz

        slug = (request.data.get("restaurant") or request.query_params.get("restaurant") or "").strip().lower()
        order_number = (order_number or "").strip().upper()
        if not slug:
            return Response({"detail": "restaurant is required.", "code": "missing_restaurant"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        session_customer_id = request.session.get("customer_id")
        try:
            with _sc(tenant.schema_name):
                from menu.models import Order as _Order
                from menu.views import (
                    _customer_can_cancel as _ccc,
                    _refund_wallet_for_cancelled_order as _refund,
                    _reverse_loyalty_for_cancelled_order as _revloy,
                    _restock_cancelled_order as _restock,
                    _broadcast_order_change as _broadcast,
                )
                from django.db import transaction as _dbtx

                order = _Order.objects.filter(order_number=order_number).first()
                if order is None:
                    return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
                try:
                    owns = bool(session_customer_id) and bool(order.customer_id) and int(session_customer_id) == int(order.customer_id)
                except (TypeError, ValueError):
                    owns = False
                if not owns:
                    return Response({"detail": "Sign in to cancel this order.", "code": "not_owner"}, status=status.HTTP_403_FORBIDDEN)
                if order.status == _Order.Status.CANCELLED:
                    return Response({"detail": "Order already cancelled.", "status": order.status})  # idempotent
                if not _ccc(order):
                    return Response({"detail": "This order can no longer be cancelled.", "code": "cancel_too_late"},
                                    status=status.HTTP_409_CONFLICT)

                with _dbtx.atomic():
                    order.status = _Order.Status.CANCELLED
                    order.status_updated_at = _tz.now()
                    order.save(update_fields=["status", "status_updated_at", "updated_at"])
                    _refund(order)
                    _revloy(order)
                    _restock(order)
                try:
                    _broadcast(order)
                except Exception:
                    pass
                return Response({"detail": "Order cancelled.", "status": order.status})
        except Exception as exc:
            logger.exception("MarketplaceOrderCancelView error order=%s tenant=%s: %s", order_number, slug, exc)
            return Response({"detail": "Could not cancel order.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Platform Flash Sales ───────────────────────────────────────────────────────

def _serialize_flash_sale(fs, opted_in: bool = False):
    return {
        "id": fs.id,
        "name": fs.name,
        "description": fs.description,
        "discount_value": str(fs.discount_value),
        "active_from": fs.active_from.isoformat(),
        "active_until": fs.active_until.isoformat(),
        "is_active": fs.is_active,
        "is_live": fs.is_live(),
        "max_redemptions": fs.max_redemptions,
        "redemption_count": fs.redemption_count,
        "created_at": fs.created_at.isoformat(),
        "opted_in": opted_in,
    }


class AdminFlashSaleListCreateView(APIView):
    """
    GET /api/admin/flash-sales/          — list all flash sales (platform admin only)
    POST /api/admin/flash-sales/         — create a new flash sale

    OPS-5b: consolidated onto IsPlatformAdmin.
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            sales = list(PlatformFlashSale.objects.all())
            return Response([_serialize_flash_sale(fs) for fs in sales])

    def post(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        from decimal import Decimal

        data = request.data
        required = ("name", "discount_value", "active_from", "active_until")
        for field in required:
            if not data.get(field):
                return Response({"detail": f"{field} is required."}, status=400)

        try:
            discount = Decimal(str(data["discount_value"]))
            if not (0 < discount <= 100):
                raise ValueError
        except (ValueError, Exception):
            return Response({"detail": "discount_value must be a number between 0 and 100."}, status=400)

        from django.utils.dateparse import parse_datetime
        active_from = parse_datetime(data["active_from"])
        active_until = parse_datetime(data["active_until"])
        if not active_from or not active_until:
            return Response({"detail": "active_from and active_until must be valid ISO datetimes."}, status=400)
        if active_from >= active_until:
            return Response({"detail": "active_from must be before active_until."}, status=400)

        with schema_context("public"):
            fs = PlatformFlashSale.objects.create(
                name=data["name"],
                description=data.get("description", ""),
                discount_value=discount,
                active_from=active_from,
                active_until=active_until,
                is_active=bool(data.get("is_active", True)),
                max_redemptions=data.get("max_redemptions") or None,
            )
        # A flash-sale write changes flash_sale_active in the public listing; bust the
        # list cache so it shows immediately instead of waiting out the TTL. Best-effort.
        try:
            _bust_public_list_cache()
        except Exception:
            pass
        return Response(_serialize_flash_sale(fs), status=status.HTTP_201_CREATED)


class AdminFlashSaleDetailView(APIView):
    """
    GET/PATCH/DELETE /api/admin/flash-sales/<id>/  — platform admin only

    OPS-5b: consolidated onto IsPlatformAdmin.
    """

    permission_classes = [IsPlatformAdmin]

    def _get_fs(self, fs_id):
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                return PlatformFlashSale.objects.get(pk=fs_id)
            except PlatformFlashSale.DoesNotExist:
                return None

    def get(self, request, fs_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        fs = self._get_fs(fs_id)
        if fs is None:
            return Response({"detail": "Not found."}, status=404)
        from .models import PlatformFlashSaleOptIn
        from django_tenants.utils import schema_context
        with schema_context("public"):
            opt_in_count = PlatformFlashSaleOptIn.objects.filter(flash_sale=fs).count()
        data = _serialize_flash_sale(fs)
        data["opt_in_count"] = opt_in_count
        return Response(data)

    def patch(self, request, fs_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        from decimal import Decimal
        from django.utils.dateparse import parse_datetime

        with schema_context("public"):
            try:
                fs = PlatformFlashSale.objects.get(pk=fs_id)
            except PlatformFlashSale.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)

            data = request.data
            update_fields = []

            if "name" in data:
                fs.name = data["name"]
                update_fields.append("name")
            if "description" in data:
                fs.description = data["description"]
                update_fields.append("description")
            if "discount_value" in data:
                try:
                    fs.discount_value = Decimal(str(data["discount_value"]))
                    update_fields.append("discount_value")
                except Exception:
                    return Response({"detail": "Invalid discount_value."}, status=400)
            if "active_from" in data:
                dt = parse_datetime(data["active_from"])
                if not dt:
                    return Response({"detail": "Invalid active_from."}, status=400)
                fs.active_from = dt
                update_fields.append("active_from")
            if "active_until" in data:
                dt = parse_datetime(data["active_until"])
                if not dt:
                    return Response({"detail": "Invalid active_until."}, status=400)
                fs.active_until = dt
                update_fields.append("active_until")
            if "is_active" in data:
                fs.is_active = bool(data["is_active"])
                update_fields.append("is_active")
            if "max_redemptions" in data:
                fs.max_redemptions = data["max_redemptions"] or None
                update_fields.append("max_redemptions")

            if update_fields:
                fs.save(update_fields=update_fields)

        # A flash-sale edit changes flash_sale_active in the public listing; bust the
        # list cache so it shows immediately instead of waiting out the TTL. Best-effort.
        try:
            _bust_public_list_cache()
        except Exception:
            pass
        return Response(_serialize_flash_sale(fs))

    def delete(self, request, fs_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                PlatformFlashSale.objects.get(pk=fs_id).delete()
            except PlatformFlashSale.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
        # Ending a flash sale changes flash_sale_active in the public listing; bust the
        # list cache so it disappears immediately instead of waiting out the TTL.
        try:
            _bust_public_list_cache()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerFlashSaleListView(APIView):
    """
    GET /api/owner/flash-sales/

    Lists all currently active (live window) platform flash sales along with
    whether this tenant has opted in.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required."}, status=403)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=400)

        from .models import PlatformFlashSale, PlatformFlashSaleOptIn
        from django_tenants.utils import schema_context
        from django.utils import timezone

        with schema_context("public"):
            now = timezone.now()
            sales = list(PlatformFlashSale.objects.filter(
                is_active=True,
                active_until__gte=now,
            ))
            opted_in_ids = set(
                PlatformFlashSaleOptIn.objects
                .filter(tenant_id=tenant.id, flash_sale__in=sales)
                .values_list("flash_sale_id", flat=True)
            )

        return Response([
            _serialize_flash_sale(fs, opted_in=(fs.id in opted_in_ids))
            for fs in sales
        ])


class OwnerFlashSaleOptInView(APIView):
    """
    POST   /api/owner/flash-sales/<id>/opt-in/   — opt this restaurant into the flash sale
    DELETE /api/owner/flash-sales/<id>/opt-in/   — opt out
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, fs_id, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required."}, status=403)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=400)

        from .models import PlatformFlashSale, PlatformFlashSaleOptIn
        from django_tenants.utils import schema_context

        with schema_context("public"):
            try:
                fs = PlatformFlashSale.objects.get(pk=fs_id, is_active=True)
            except PlatformFlashSale.DoesNotExist:
                return Response({"detail": "Flash sale not found or not active."}, status=404)

            _, created = PlatformFlashSaleOptIn.objects.get_or_create(
                flash_sale=fs,
                tenant_id=tenant.id,
            )

        if created:
            # Opting in changes who shows the flash-sale badge in the public listing;
            # bust the list cache so it shows immediately. Best-effort.
            try:
                _bust_public_list_cache()
            except Exception:
                pass

        return Response(
            {"detail": "Opted in." if created else "Already opted in.", "opted_in": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, fs_id, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required."}, status=403)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=400)

        from .models import PlatformFlashSaleOptIn
        from django_tenants.utils import schema_context

        with schema_context("public"):
            deleted, _ = PlatformFlashSaleOptIn.objects.filter(
                flash_sale_id=fs_id,
                tenant_id=tenant.id,
            ).delete()

        if not deleted:
            return Response({"detail": "Not currently opted in."}, status=404)

        # Opting out changes who shows the flash-sale badge in the public listing;
        # bust the list cache so it disappears immediately. Best-effort.
        try:
            _bust_public_list_cache()
        except Exception:
            pass

        return Response({"detail": "Opted out.", "opted_in": False})


# ── Phase 4: Delivery Platform ────────────────────────────────────────────────

# Process-level cache of tenant id → (slug, name). Slugs are stable, so this
# avoids an N+1 Tenant lookup when serializing lists of delivery jobs.
_DELIVERY_TENANT_CACHE = {}


def _tenant_slug_name(tenant_id):
    if tenant_id in _DELIVERY_TENANT_CACHE:
        return _DELIVERY_TENANT_CACHE[tenant_id]
    try:
        from tenancy.models import Tenant as _T
        row = _T.objects.filter(id=tenant_id).values("slug", "name").first()
    except Exception:
        return ("", "")  # transient/unavailable — don't cache, retry next time
    result = (row["slug"], row["name"]) if row else ("", "")
    _DELIVERY_TENANT_CACHE[tenant_id] = result
    return result


def _job_distance_km(job):
    """Straight-line km from pickup (restaurant) → delivery (customer), or None."""
    if (
        job.pickup_lat is not None and job.pickup_lng is not None
        and job.delivery_lat is not None and job.delivery_lng is not None
    ):
        try:
            return round(
                _haversine_km(job.pickup_lat, job.pickup_lng, job.delivery_lat, job.delivery_lng),
                1,
            )
        except Exception:
            return None
    return None


def _order_summary_dict(o, include_contact: bool = False) -> dict:
    """Build the driver-facing order summary from an Order object (no schema switch)."""
    out = {}
    items = list(o.items.all())
    out["items_count"] = sum(int(getattr(i, "qty", 1) or 1) for i in items)
    out["items"] = [
        {"name": i.dish_name, "qty": int(getattr(i, "qty", 1) or 1)}
        for i in items[:25]
    ]
    out["order_total"] = str(o.total)
    out["currency"] = getattr(o, "currency", "") or ""
    _pay = getattr(o, "payment_status", "") or ""
    out["payment_status"] = _pay
    # COD: the driver collects the order total in cash unless it's prepaid.
    out["collect_cash"] = _pay != "paid"
    out["fulfillment_type"] = getattr(o, "fulfillment_type", "") or ""
    _note = getattr(o, "delivery_address", "") or ""
    if _note:
        out["delivery_address"] = _note
    if include_contact:
        out["customer_name"] = o.customer_name or ""
        out["customer_phone"] = o.customer_phone or ""
    return out


def _job_order_summaries(tenant_id, order_numbers, include_contact: bool = False) -> dict:
    """Batched order summaries — ONE schema switch per tenant, all orders fetched at
    once. Returns {order_number: summary_dict}. Best-effort (errors -> {})."""
    out = {}
    nums = [n for n in order_numbers if n]
    if not nums:
        return out
    try:
        from tenancy.models import Tenant as _T

        tnt = _T.objects.filter(id=tenant_id).first()
        if not tnt:
            return out
        from django_tenants.utils import schema_context

        with schema_context(tnt.schema_name):
            from menu.models import Order as _O

            for o in (
                _O.objects.filter(order_number__in=nums).prefetch_related("items")
            ):
                out[o.order_number] = _order_summary_dict(o, include_contact)
    except Exception:
        pass
    return out


def _job_order_summary(tenant_id, order_number, include_contact: bool = False) -> dict:
    """Single-order driver summary — thin wrapper over the batched helper.

    Returns the bits a driver needs on the job card: order size (``items_count`` +
    a short ``items`` list), ``total``/``currency``, and whether the driver must
    **collect cash** (``collect_cash`` — True unless the order is already paid).
    With ``include_contact`` (only the driver's OWN active job) it also returns the
    customer name/phone. Pending/unclaimed jobs never expose contact details.
    """
    return _job_order_summaries(tenant_id, [order_number], include_contact).get(order_number, {})


def _batch_business_types(tenant_ids) -> dict:
    """Return {tenant_id: business_type} for the given tenant ids.

    Single DB query — callers must pre-collect tenant_ids from the page of jobs
    and pass them here to avoid N+1 per-row lookups. Defaults to 'restaurant'
    for any tenant whose Profile row is missing.
    """
    if not tenant_ids:
        return {}
    try:
        from tenancy.models import Profile as _Profile
        rows = _Profile.objects.filter(
            tenant_id__in=tenant_ids
        ).values_list("tenant_id", "business_type")
        return {tid: bt for tid, bt in rows}
    except Exception:
        return {}


def _serialize_delivery_job(
    job,
    include_driver_position: bool = False,
    business_type: str = "restaurant",
) -> dict:
    _slug, _name = _tenant_slug_name(job.tenant_id)
    data = {
        "id": job.id,
        "order_number": job.order_number,
        "tenant_id": job.tenant_id,
        # Restaurant identity — the driver UI needs the slug to submit a rating
        # (the rate endpoint is keyed by ?restaurant=<slug>).
        "restaurant_slug": _slug,
        "restaurant_name": _name,
        # Vertical type — lets the driver app customise wording/UX per business
        # (e.g. "at the store" vs "at the restaurant" vs no merchant stop for courier).
        "business_type": business_type,
        "status": job.status,
        "pickup_address": job.pickup_address,
        "pickup_lat": job.pickup_lat,
        "pickup_lng": job.pickup_lng,
        "delivery_address": job.delivery_address,
        "delivery_lat": job.delivery_lat,
        "delivery_lng": job.delivery_lng,
        # Straight-line distance the driver covers (restaurant → customer), so the
        # job card can show "how far" before/after accepting.
        "distance_km": _job_distance_km(job),
        "delivery_fee": str(job.delivery_fee),
        "driver_payout": str(job.driver_payout),
        "assigned_at": job.assigned_at.isoformat() if job.assigned_at else None,
        "picked_up_at": job.picked_up_at.isoformat() if job.picked_up_at else None,
        "delivered_at": job.delivered_at.isoformat() if job.delivered_at else None,
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        # Owner-entered prep ETA (when the food is ready for pickup), so the driver
        # can time their arrival. Null until the owner confirms with an estimate.
        "food_ready_at": job.food_ready_at.isoformat() if job.food_ready_at else None,
        # Ranked-offer dispatch state: an exclusive offer (with a deadline) vs the
        # open pool. The list view adds a per-driver "offered_to_me" flag.
        "is_open_pool": bool(getattr(job, "is_open_pool", False)),
        "offer_expires_at": job.offer_expires_at.isoformat() if getattr(job, "offer_expires_at", None) else None,
        "created_at": job.created_at.isoformat(),
        "is_terminal": job.is_terminal,
        "failure_reason": job.failure_reason,
        "failure_note": job.failure_note,
        "resolution": job.resolution,
        "driver": None,
        "ratings": {
            "customer_driver_rating": job.customer_driver_rating,
            "customer_driver_note": job.customer_driver_note,
            "driver_customer_rating": job.driver_customer_rating,
            "driver_customer_note": job.driver_customer_note,
            "restaurant_driver_rating": job.restaurant_driver_rating,
            "restaurant_driver_note": job.restaurant_driver_note,
        },
    }
    if job.driver:
        driver_data = {
            "id": job.driver.id,
            "name": job.driver.name or "",
            "phone": job.driver.phone or "",
            "vehicle": getattr(job.driver, "driver_vehicle", "") or "",
        }
        if include_driver_position:
            driver_data["lat"] = job.driver.driver_lat
            driver_data["lng"] = job.driver.driver_lng
            driver_data["is_online"] = job.driver.is_driver_online
            driver_data["position_updated_at"] = (
                job.driver.driver_position_updated_at.isoformat()
                if job.driver.driver_position_updated_at else None
            )
            # Driver's average customer rating (best-effort; customer-facing tracking only).
            try:
                from django.db.models import Avg as _Avg, Count as _Count
                from .models import DeliveryJob as _DJ

                _agg = _DJ.objects.filter(
                    driver=job.driver, customer_driver_rating__isnull=False
                ).aggregate(avg=_Avg("customer_driver_rating"), n=_Count("id"))
                driver_data["rating"] = round(_agg["avg"], 1) if _agg["avg"] is not None else None
                driver_data["rating_count"] = _agg["n"] or 0
            except Exception:
                driver_data["rating"] = None
                driver_data["rating_count"] = 0
        data["driver"] = driver_data

    # Live route line + ETA for the tracking map (customer + owner): from the driver's
    # current position to the current leg's target — the restaurant before pickup, the
    # customer after. Real street route when DELIVERY_OSRM_URL is set, else a straight
    # line. Only on live-tracking calls for an active (non-terminal) job with a driver fix.
    if include_driver_position and job.driver and not job.is_terminal:
        from .models import DeliveryJob as _DJ
        _dlat = getattr(job.driver, "driver_lat", None)
        _dlng = getattr(job.driver, "driver_lng", None)
        if job.status == _DJ.Status.PICKED_UP:
            _tlat, _tlng, _target = job.delivery_lat, job.delivery_lng, "dropoff"
        else:
            _tlat, _tlng, _target = job.pickup_lat, job.pickup_lng, "pickup"
        if None not in (_dlat, _dlng, _tlat, _tlng):
            try:
                from tenancy.routing import road_route
                _r = road_route(_dlat, _dlng, _tlat, _tlng)
                data["route"] = _r["geometry"]
                data["eta_minutes"] = _r["duration_min"]
                data["route_target"] = _target
            except Exception:
                pass
    return data


def _valid_polygon(polygon) -> bool:
    """Each polygon point must be a {lat, lng} dict with numeric coordinates."""
    if not isinstance(polygon, list) or len(polygon) < 3:
        return False
    for pt in polygon:
        if not isinstance(pt, dict):
            return False
        try:
            float(pt.get("lat"))
            float(pt.get("lng"))
        except (TypeError, ValueError):
            return False
    return True


def _serialize_zone(zone) -> dict:
    return {
        "id": zone.id,
        "name": zone.name,
        "city": zone.city,
        "polygon": zone.polygon,
        "center_lat": zone.center_lat,
        "center_lng": zone.center_lng,
        "approx_radius_km": zone.approx_radius_km,
        "is_active": zone.is_active,
        "fee_tiers": zone.fee_tiers or [],
        "created_at": zone.created_at.isoformat(),
    }


# ── Driver registration & availability ────────────────────────────────────────


def _notify_admins_new_driver(customer):
    """Best-effort notify platform admins that a new rider applied. Never raises.

    Riders self-apply (is_driver=True) but can't go online until a platform admin
    vets them — so admins need to know an application is waiting in the console.
    """
    try:
        from django.db.models import Q
        from django.core.mail import send_mail as _send_mail
        from django.conf import settings as _cfg
        from .models import User
        from .notifications import record_notification

        admins = list(
            User.objects.filter(
                Q(is_platform_admin=True) | Q(is_superuser=True) | Q(is_staff=True)
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        name = (customer.name or customer.phone or customer.email or f"Customer #{customer.id}")
        vehicle = customer.driver_vehicle or "—"
        if admins:
            _send_mail(
                subject="New rider application on Kepoli",
                message=(
                    "A new rider has applied to join the Kepoli delivery network.\n\n"
                    f"Name: {name}\n"
                    f"Vehicle: {vehicle}\n\n"
                    "Review and approve them in the admin console under Drivers "
                    "(/admin-drivers).\n"
                ),
                from_email=_cfg.DEFAULT_FROM_EMAIL,
                recipient_list=admins,
                fail_silently=True,
            )
        record_notification(
            channel="email",
            event="driver_application",
            status="sent" if admins else "skipped",
            recipient=", ".join(admins)[:300],
            detail=f"Rider application: {name}"[:300],
            reference=f"driver_apply:{customer.id}",
        )
    except Exception:
        pass


class DriverRegisterView(APIView):
    """POST /api/driver/register/ — customer applies to become a delivery driver.

    Requires an active customer session. Records the application (is_driver=True,
    driver_approved=False) plus optional vehicle info. A platform admin must approve
    before the driver can go online. Body: { "vehicle"?: str }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        fields = []
        vehicle = str(request.data.get("vehicle") or "").strip()[:120]
        if vehicle and vehicle != (customer.driver_vehicle or ""):
            customer.driver_vehicle = vehicle
            fields.append("driver_vehicle")
        newly_applied = False
        if not customer.is_driver:
            customer.is_driver = True
            fields.append("is_driver")
            newly_applied = True
        if fields:
            fields.append("updated_at")
            customer.save(update_fields=fields)

        # Tell platform admins a fresh application is waiting to be vetted.
        if newly_applied:
            _notify_admins_new_driver(customer)

        return Response({
            "is_driver": True,
            "driver_approved": bool(customer.driver_approved),
            "driver_status": "approved" if customer.driver_approved else "pending",
            "is_driver_online": customer.is_driver_online,
            "message": "Approved." if customer.driver_approved else "Application received — pending approval.",
        })


class DriverStatusView(APIView):
    """GET   /api/driver/status/ — current driver state (is_driver, online).
       PATCH /api/driver/status/ — toggle driver online/offline. Body: { "online": bool }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "is_driver": bool(customer.is_driver),
            "driver_approved": bool(customer.driver_approved),
            "driver_status": ("approved" if customer.driver_approved else "pending") if customer.is_driver else "none",
            "driver_vehicle": customer.driver_vehicle or "",
            "is_driver_online": bool(customer.is_driver_online),
            "driver_car_approved": bool(customer.driver_car_approved),
            "driver_licence_url": customer.driver_licence_url or "",
            "driver_insurance_url": customer.driver_insurance_url or "",
            "driver_vehicle_type": customer.driver_vehicle_type or "",
        })

    def patch(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        online = bool(request.data.get("online", False))
        # Only vetted drivers may go online (and therefore receive/accept jobs).
        if online and not customer.driver_approved:
            return Response(
                {"detail": "Your driver application is pending approval.", "code": "pending_approval"},
                status=status.HTTP_403_FORBIDDEN,
            )
        update_fields = ["is_driver_online", "updated_at"]
        customer.is_driver_online = online

        # Optional: update the structured vehicle type for ride dispatch.
        raw_vtype = request.data.get("driver_vehicle_type")
        if raw_vtype is not None:
            valid_types = [v for v, _ in Customer.VEHICLE_TYPE_CHOICES]
            if raw_vtype not in valid_types:
                return Response(
                    {"detail": f"driver_vehicle_type must be one of {valid_types}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            customer.driver_vehicle_type = raw_vtype
            update_fields.append("driver_vehicle_type")

        customer.save(update_fields=update_fields)

        return Response({
            "is_driver_online": customer.is_driver_online,
            "driver_vehicle_type": customer.driver_vehicle_type,
        })


class DriverPositionUpdateView(APIView):
    """POST /api/driver/position/ — driver updates their current GPS position.

    Body: { "lat": 48.85, "lng": 2.35 }
    Also accepts optional job_id to update the specific job context.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverPositionThrottle]

    def post(self, request, *args, **kwargs):
        from django.utils import timezone as _tz

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.data.get("lat") is None or request.data.get("lng") is None:
            return Response({"detail": "lat and lng are required."}, status=status.HTTP_400_BAD_REQUEST)
        lat = _parse_coord(request.data.get("lat"), -90, 90)
        lng = _parse_coord(request.data.get("lng"), -180, 180)
        if lat is None:
            return Response({"detail": "lat must be a finite number between -90 and 90."}, status=status.HTTP_400_BAD_REQUEST)
        if lng is None:
            return Response({"detail": "lng must be a finite number between -180 and 180."}, status=status.HTTP_400_BAD_REQUEST)

        now = _tz.now()
        customer.driver_lat = lat
        customer.driver_lng = lng
        customer.driver_position_updated_at = now
        customer.save(update_fields=["driver_lat", "driver_lng", "driver_position_updated_at", "updated_at"])

        return Response({"lat": lat, "lng": lng, "updated_at": now.isoformat()})


# ── Delivery job management ────────────────────────────────────────────────────


class DriverJobListView(APIView):
    """GET /api/driver/jobs/ — list pending + active jobs available for the driver.

    Returns jobs in SEARCHING status (unassigned) for the driver to accept,
    plus any currently active job assigned to this driver.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        from .models import DeliveryJob
        from django_tenants.utils import schema_context

        # Active job assigned to this driver
        active_jobs = list(
            DeliveryJob.objects.filter(
                driver=customer,
                status__in=[
                    DeliveryJob.Status.ASSIGNED,
                    DeliveryJob.Status.AT_RESTAURANT,
                    DeliveryJob.Status.PICKED_UP,
                ],
            ).select_related("driver")
        )

        # Pending jobs (no driver yet): with ranked dispatch a SEARCHING job is only
        # visible to the driver it's exclusively offered to (until that offer lapses),
        # or to everyone once it falls back to the open pool. Expired offers stay
        # visible too (the sweep will cascade them) so a job is never hidden from all.
        from django.db.models import Q
        from django.utils import timezone as _tz
        _now = _tz.now()
        pending_jobs = list(
            DeliveryJob.objects.filter(
                driver__isnull=True,
                status=DeliveryJob.Status.SEARCHING,
            ).filter(
                Q(is_open_pool=True)
                | Q(offered_to=customer)
                | Q(offered_to__isnull=True)
                | Q(offer_expires_at__lte=_now)
            ).select_related("driver")[:20]
        )

        # Enrich jobs with the order summary, BATCHED by tenant — one schema switch
        # per tenant instead of one per job (a driver poll can carry ~20 pending jobs
        # spread across several restaurants). Output order is preserved.
        def _summaries_by_tenant(jobs, include_contact):
            by_tenant = {}
            for _j in jobs:
                by_tenant.setdefault(_j.tenant_id, []).append(_j.order_number)
            merged = {}  # (tenant_id, order_number) -> summary dict
            for _tid, _nums in by_tenant.items():
                for _onum, _summ in _job_order_summaries(_tid, _nums, include_contact).items():
                    merged[(_tid, _onum)] = _summ
            return merged

        # Batch-fetch business_type for all jobs in one query (no N+1).
        all_tenant_ids = {j.tenant_id for j in active_jobs + pending_jobs}
        _biz_types = _batch_business_types(all_tenant_ids)

        # Active job(s): include customer contact (the driver's own job).
        _active_sum = _summaries_by_tenant(active_jobs, True)
        active_serialized = []
        for j in active_jobs:
            _bt = _biz_types.get(j.tenant_id, "restaurant")
            d = _serialize_delivery_job(j, business_type=_bt)
            d.update(_active_sum.get((j.tenant_id, j.order_number), {}))
            active_serialized.append(d)

        # PENDING jobs: enough to decide (size, total, cash-or-prepaid, distance) but
        # never the customer's name/phone until the driver accepts.
        _pending_sum = _summaries_by_tenant(pending_jobs, False)
        pending_serialized = []
        for j in pending_jobs:
            _bt = _biz_types.get(j.tenant_id, "restaurant")
            d = _serialize_delivery_job(j, business_type=_bt)
            d.update(_pending_sum.get((j.tenant_id, j.order_number), {}))
            # Is this job exclusively offered to *this* driver right now? (drives the
            # "offered to you" badge + the decline button in the app).
            d["offered_to_me"] = bool(
                j.offered_to_id == customer.id
                and j.offer_expires_at and j.offer_expires_at > _now
            )
            pending_serialized.append(d)

        return Response({
            "active": active_serialized,
            "pending": pending_serialized,
        })


class DriverJobAcceptView(APIView):
    """POST /api/driver/jobs/<job_id>/accept/ — driver accepts a pending delivery job."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverJobAcceptThrottle]

    def post(self, request, job_id, *args, **kwargs):
        from django.utils import timezone as _tz
        from django.db import transaction as _tx
        from .models import DeliveryJob

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(
                pk=customer_id, is_driver=True, driver_approved=True, is_driver_online=True
            )
        except Customer.DoesNotExist:
            return Response({"detail": "Driver must be approved and online to accept jobs."}, status=status.HTTP_403_FORBIDDEN)

        # Check driver doesn't already have an active job
        if DeliveryJob.objects.filter(
            driver=customer,
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT, DeliveryJob.Status.PICKED_UP],
        ).exists():
            return Response({"detail": "Complete your current delivery before accepting a new one."}, status=status.HTTP_409_CONFLICT)

        with _tx.atomic():
            # Serialize this driver's concurrent accepts (double-tap / two tabs) on the
            # driver row, then re-check capacity under the lock — the pre-check above is
            # racy on its own and could otherwise let one driver hold two jobs at once.
            Customer.objects.select_for_update().filter(pk=customer.id).first()
            if DeliveryJob.objects.filter(
                driver=customer, status__in=DeliveryJob.ACTIVE_STATUSES,
            ).exists():
                return Response({"detail": "Complete your current delivery before accepting a new one."}, status=status.HTTP_409_CONFLICT)
            try:
                job = DeliveryJob.objects.select_for_update().get(
                    pk=job_id,
                    status=DeliveryJob.Status.SEARCHING,
                    driver__isnull=True,
                )
            except DeliveryJob.DoesNotExist:
                return Response({"detail": "Job not available."}, status=status.HTTP_404_NOT_FOUND)

            # Ranked-offer gate: while a job is exclusively offered to another driver
            # (offer still live), only that driver may claim it. Once it lapses or the
            # job opens to the pool, anyone free may take it.
            _now = _tz.now()
            if (
                not job.is_open_pool
                and job.offered_to_id is not None
                and job.offered_to_id != customer.id
                and job.offer_expires_at is not None
                and job.offer_expires_at > _now
            ):
                return Response(
                    {"detail": "This delivery is currently offered to another driver.", "code": "offered_elsewhere"},
                    status=status.HTTP_409_CONFLICT,
                )

            job.driver = customer
            job.status = DeliveryJob.Status.ASSIGNED
            job.assigned_at = _now
            job.offered_to = None
            job.offer_expires_at = None
            job.save(update_fields=["driver", "status", "assigned_at", "offered_to", "offer_expires_at"])

        # Tell the customer a driver is on it (best-effort, after commit).
        _notify_customer_milestone(job, "assigned")
        _bt = _batch_business_types({job.tenant_id}).get(job.tenant_id, "restaurant")
        return Response(_serialize_delivery_job(job, business_type=_bt), status=status.HTTP_200_OK)


class DriverJobDeclineView(APIView):
    """POST /api/driver/jobs/<job_id>/decline/ — driver passes on an exclusive offer.

    Records the decline and immediately cascades the job to the next-nearest driver
    (or the open pool). Only the driver currently holding the offer can decline it;
    for anyone else it's a harmless no-op success.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverJobAcceptThrottle]

    def post(self, request, job_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)
        from accounts.dispatch import decline_offer
        decline_offer(job_id, customer.id)
        return Response({"ok": True}, status=status.HTTP_200_OK)


def _mark_order_out_for_delivery(job) -> None:
    """When the driver picks the order up, advance the tenant order to
    OUT_FOR_DELIVERY so the customer's timeline reflects it. Best-effort."""
    try:
        from tenancy.models import Tenant as _T
        from django_tenants.utils import schema_context
        from django.utils import timezone as _tz
        from menu.models import Order as _O

        tenant = _T.objects.filter(id=job.tenant_id).first()
        if not tenant:
            return
        with schema_context(tenant.schema_name):
            order = _O.objects.filter(order_number=job.order_number).first()
            if order and order.status in (
                _O.Status.CONFIRMED, _O.Status.PREPARING, _O.Status.READY,
            ):
                order.status = _O.Status.OUT_FOR_DELIVERY
                order.status_updated_at = _tz.now()
                order.save(update_fields=["status", "status_updated_at", "updated_at"])
    except Exception:
        pass


def _order_delivery_code(job) -> str:
    """Read the proof-of-delivery code from the job's underlying order (tenant schema).
    Returns "" if none was issued (legacy orders) — caller then skips the code check."""
    try:
        from tenancy.models import Tenant as _T
        from django_tenants.utils import schema_context
        from menu.models import Order as _O
        tenant = _T.objects.filter(id=job.tenant_id).first()
        if not tenant:
            return ""
        with schema_context(tenant.schema_name):
            o = _O.objects.filter(order_number=job.order_number).only("delivery_code").first()
            return (o.delivery_code or "") if o else ""
    except Exception:
        return ""


def _credit_driver_earnings(job) -> None:
    """Credit the driver's wallet with this job's payout exactly once (idempotent on the
    job id). Best-effort — a hiccup here must never block completing the delivery; the
    earning can be reconciled. Bypasses the verified-phone gate (the driver clearly exists)."""
    try:
        from decimal import Decimal as _D
        from accounts.wallet_service import credit_wallet
        from accounts.models import WalletTransaction as _WT
        if not getattr(job, "driver_id", None):
            return
        payout = _D(str(job.driver_payout or "0"))
        if payout <= 0:
            return
        credit_wallet(
            job.driver_id, payout,
            tx_type=_WT.Type.EARNING,
            idempotency_key=f"earning:{job.id}",
            reference=f"delivery:{job.order_number}",
            tenant_id=job.tenant_id,
            note="Delivery earning",
            require_verified=False,
        )
    except Exception:
        logger.exception("Failed to credit driver earning for job %s", getattr(job, "id", "?"))


def _complete_delivered_order(job, proof_photo_url="") -> None:
    """When a delivery is completed, close out the underlying tenant order:
    mark it COMPLETED (delivery is the fulfilment) and PAID (delivery orders are
    prepaid by wallet or cash-collected on handover), store any proof photo, and
    credit the driver's wallet. Best-effort — never blocks the driver.
    """
    try:
        from tenancy.models import Tenant as _T
        from django_tenants.utils import schema_context
        from django.utils import timezone as _tz
        from menu.models import Order as _O

        tenant = _T.objects.filter(id=job.tenant_id).first()
        if not tenant:
            return
        with schema_context(tenant.schema_name):
            order = _O.objects.filter(order_number=job.order_number).first()
            if not order:
                return
            # Never resurrect a cancelled order: if it was cancelled (and refunded), a late
            # driver completion must not flip it back to completed/paid.
            if order.status == _O.Status.CANCELLED:
                return
            fields = []
            if order.status != _O.Status.COMPLETED:
                order.status = _O.Status.COMPLETED
                order.status_updated_at = _tz.now()
                fields += ["status", "status_updated_at"]
            if order.payment_status != _O.PaymentStatus.PAID:
                order.payment_status = _O.PaymentStatus.PAID
                order.paid_at = _tz.now()
                fields += ["payment_status", "paid_at"]
            if proof_photo_url and not order.delivery_proof_photo_url:
                order.delivery_proof_photo_url = proof_photo_url[:500]
                fields.append("delivery_proof_photo_url")
            if fields:
                fields.append("updated_at")
                order.save(update_fields=fields)
    except Exception:
        logger.exception("Failed to complete delivered order %s", getattr(job, "order_number", "?"))
    # Driver earnings live in the public schema — credit outside the tenant context.
    _credit_driver_earnings(job)


def _notify_customer_milestone(job, event) -> None:
    """Enqueue a delivery-milestone web-push to the order's customer (best-effort)."""
    try:
        from accounts.tasks import enqueue, customer_order_milestone
        enqueue(customer_order_milestone, job.order_number, job.tenant_id, event)
    except Exception:
        pass


def _on_job_failed(job) -> None:
    """A driver marked a delivery FAILED → alert the restaurant + the customer. The OWNER
    decides re-dispatch vs refund/cancel (and confirms any no-show payout). No money moves
    and the order is not mutated here."""
    try:
        from tenancy.models import Tenant as _T
        from accounts.tasks import enqueue, web_push_tenant
        tnt = _T.objects.filter(pk=job.tenant_id).first()
        if tnt:
            try:
                _reason = job.get_failure_reason_display()
            except Exception:
                _reason = job.failure_reason or "failed"
            enqueue(
                web_push_tenant, tnt.schema_name,
                "Delivery needs attention",
                f"Order #{job.order_number}: {_reason}. Re-dispatch or refund from Orders.",
                "/owner/orders",
            )
    except Exception:
        pass
    _notify_customer_milestone(job, "failed")
    try:
        from .notifications import record_notification
        record_notification(
            channel="push", event="delivery.failed", status="sent",
            recipient=f"tenant:{job.tenant_id}", reference=str(job.order_number),
            detail=(job.failure_reason or ""),
        )
    except Exception:
        pass


class DriverJobStatusUpdateView(APIView):
    """PATCH /api/driver/jobs/<job_id>/status/ — driver advances job status.

    Body: { "status": "at_restaurant" | "picked_up" | "delivered" | "failed",
            "code"?: str (delivered), "failure_reason"?: str (failed), "failure_note"?: str }
    """

    VALID_TRANSITIONS = {
        "assigned": ["at_restaurant", "failed"],
        "at_restaurant": ["picked_up", "failed"],
        "picked_up": ["delivered", "failed"],
    }

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DriverStatusUpdateThrottle]

    def patch(self, request, job_id, *args, **kwargs):
        from datetime import timedelta as _td
        from django.utils import timezone as _tz
        from django.db import transaction as _dbtx
        from .models import DeliveryJob

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status", "").strip()
        now = _tz.now()
        _proof_photo_url = ""

        # All state checks + the mutate happen UNDER a row lock so a concurrent cancel /
        # accept / re-dispatch can't be raced (TOCTOU). Side effects run after commit.
        with _dbtx.atomic():
            try:
                job = DeliveryJob.objects.select_for_update().get(pk=job_id, driver=customer)
            except DeliveryJob.DoesNotExist:
                return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

            allowed = self.VALID_TRANSITIONS.get(job.status, [])
            if new_status not in allowed:
                return Response(
                    {"detail": f"Cannot transition from '{job.status}' to '{new_status}'.",
                     "allowed": allowed, "code": "bad_transition"},
                    status=status.HTTP_409_CONFLICT,
                )

            if new_status == DeliveryJob.Status.DELIVERED:
                # OPS-5f: re-check driver approval at the money-emitting transition.
                # is_driver gates the endpoint, but a driver who was APPROVED, accepted a
                # job, then got driver_approved revoked must NOT still bank earnings on
                # DELIVERED (_complete_delivered_order → _credit_driver_earnings). Re-read
                # the flag from the DB (customer was fetched before the lock).
                _still_approved = (
                    Customer.objects.filter(pk=customer.pk, driver_approved=True).exists()
                )
                if not _still_approved:
                    return Response(
                        {"detail": "Your driver account is no longer approved. Contact support.",
                         "code": "driver_not_approved"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                # Proof-of-delivery code, with a brute-force lockout.
                if job.code_locked_until and job.code_locked_until > now:
                    return Response(
                        {"detail": "Too many incorrect codes — try again shortly.", "code": "code_locked"},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                _expected_code = _order_delivery_code(job)
                _provided_code = str(request.data.get("code") or "").strip()
                if _expected_code and _provided_code != _expected_code:
                    job.code_attempts = (job.code_attempts or 0) + 1
                    _f = ["code_attempts"]
                    if job.code_attempts >= 5:
                        job.code_locked_until = now + _td(minutes=5)
                        job.code_attempts = 0
                        _f.append("code_locked_until")
                    job.save(update_fields=_f)
                    return Response(
                        {"detail": "Incorrect delivery code. Ask the customer for the code on their order.",
                         "code": "bad_delivery_code"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                _proof_photo_url = str(request.data.get("proof_photo_url") or "").strip()

            if new_status == DeliveryJob.Status.FAILED:
                _reason = str(request.data.get("failure_reason") or "").strip()
                if _reason not in DeliveryJob.FailureReason.values:
                    return Response(
                        {"detail": "Select why the delivery failed.", "code": "failure_reason_required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                job.failure_reason = _reason
                job.failure_note = str(request.data.get("failure_note") or "")[:300]
                job.failed_at = now

            job.status = new_status
            update_fields = ["status"]
            if new_status == DeliveryJob.Status.PICKED_UP:
                job.picked_up_at = now
                update_fields.append("picked_up_at")
            elif new_status == DeliveryJob.Status.DELIVERED:
                job.delivered_at = now
                update_fields.append("delivered_at")
            elif new_status == DeliveryJob.Status.FAILED:
                update_fields += ["failure_reason", "failure_note", "failed_at"]
            job.save(update_fields=update_fields)

        # ── Side effects (after the lock is released) ──────────────────────────
        if new_status == DeliveryJob.Status.PICKED_UP:
            _mark_order_out_for_delivery(job)
            _notify_customer_milestone(job, "out_for_delivery")
        elif new_status == DeliveryJob.Status.DELIVERED:
            customer.is_driver_online = False  # free the driver after a completed run
            customer.save(update_fields=["is_driver_online", "updated_at"])
            _complete_delivered_order(job, proof_photo_url=_proof_photo_url)
            _notify_customer_milestone(job, "delivered")
        elif new_status == DeliveryJob.Status.FAILED:
            _on_job_failed(job)
        elif new_status == DeliveryJob.Status.AT_RESTAURANT:
            try:
                import threading as _threading
                from tenancy.models import Tenant as _Tenant
                from menu.push import _push_to_tenant as _push_restaurant
                _tenant = _Tenant.objects.filter(pk=job.tenant_id).first()
                if _tenant:
                    _driver_name = (customer.name or "Driver").strip()
                    _threading.Thread(
                        target=_push_restaurant,
                        args=(
                            _tenant.schema_name,
                            f"Driver arrived \U0001f6f5",
                            f"{_driver_name} is at your restaurant — order #{job.order_number}",
                            "/owner/orders",
                        ),
                        daemon=True,
                    ).start()
            except Exception:
                pass  # Never fail the driver status update due to push errors

        _bt = _batch_business_types({job.tenant_id}).get(job.tenant_id, "restaurant")
        return Response(_serialize_delivery_job(job, business_type=_bt))


# ── Order tracking SSE ────────────────────────────────────────────────────────


def _tracking_request_owns_order(request, tenant, order_number) -> bool:
    """True when the requesting session customer owns this order (tenant-schema lookup).

    Delivery orders always have a signed-in owner, so this never hides tracking from a
    legitimate customer — it just stops anyone who guesses an order number from reading the
    driver's phone + live position.
    """
    try:
        sid = request.session.get("customer_id")
    except Exception:
        sid = None
    if not sid:
        return False
    try:
        from django_tenants.utils import schema_context
        from menu.models import Order as _O
        with schema_context(tenant.schema_name):
            cid = (
                _O.objects.filter(order_number=order_number)
                .values_list("customer_id", flat=True)
                .first()
            )
        return bool(cid) and str(cid) == str(sid)
    except Exception:
        return False


class OrderTrackingView(APIView):
    """GET /api/marketplace/track/<order_number>/?restaurant=<slug>

    Returns current delivery job status + driver position (JSON, single shot).
    Clients can poll this every 5–10 seconds for driver tracking.

    For true real-time, call with ?stream=1 to get an SSE stream that pushes
    updates every 3 seconds until the job reaches a terminal state or 90 seconds
    have elapsed (to avoid holding Gunicorn workers indefinitely).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DeliveryTrackingThrottle]

    def get(self, request, order_number, *args, **kwargs):
        from tenancy.models import Tenant
        from .models import DeliveryJob

        slug = (request.query_params.get("restaurant") or "").strip().lower()
        order_number = (order_number or "").strip().upper()
        use_sse = request.query_params.get("stream") == "1"

        if not slug:
            return Response({"detail": "restaurant query param required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            job = DeliveryJob.objects.select_related("driver").get(
                tenant_id=tenant.id,
                order_number=order_number,
            )
        except DeliveryJob.DoesNotExist:
            return Response({"detail": "No delivery job found for this order.", "code": "no_job"}, status=status.HTTP_404_NOT_FOUND)

        # Privacy gate: this returns the driver's phone + live GPS, so only the order's
        # OWNER may read it (order numbers are guessable, and this endpoint is AllowAny).
        if not _tracking_request_owns_order(request, tenant, order_number):
            return Response({"detail": "Not your order.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        _tracking_bt = _batch_business_types({job.tenant_id}).get(job.tenant_id, "restaurant")

        if not use_sse:
            return Response(_serialize_delivery_job(
                job, include_driver_position=True, business_type=_tracking_bt
            ))

        # ── SSE stream ────────────────────────────────────────────────────────
        import time
        import json as _json
        from django.http import StreamingHttpResponse

        def event_stream():
            deadline = time.monotonic() + 90  # max 90 seconds
            while time.monotonic() < deadline:
                try:
                    fresh_job = DeliveryJob.objects.select_related("driver").get(pk=job.pk)
                except DeliveryJob.DoesNotExist:
                    break
                data = _json.dumps(_serialize_delivery_job(
                    fresh_job, include_driver_position=True, business_type=_tracking_bt
                ))
                yield f"data: {data}\n\n"
                if fresh_job.is_terminal:
                    # Send terminal event then close
                    yield "event: terminal\ndata: {}\n\n"
                    break
                time.sleep(3)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


# ── Three-way delivery ratings ─────────────────────────────────────────────────


class DeliveryRatingView(APIView):
    """POST /api/marketplace/track/<order_number>/rate/?restaurant=<slug>

    Submit a rating for a completed delivery. Who is rating whom depends on the
    session context (customer, driver, or owner).

    Body (customer rates driver):
      { "role": "customer", "score": 5, "note": "Very fast!" }

    Body (driver rates customer):
      { "role": "driver", "score": 4, "note": "Easy address" }

    Body (restaurant/owner rates driver):
      { "role": "restaurant", "score": 5, "note": "On time" }
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DeliveryRatingThrottle]

    def post(self, request, order_number, *args, **kwargs):
        from tenancy.models import Tenant
        from .models import DeliveryJob

        slug = (request.query_params.get("restaurant") or "").strip().lower()
        order_number = (order_number or "").strip().upper()

        if not slug:
            return Response({"detail": "restaurant query param required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(slug=slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            job = DeliveryJob.objects.get(
                tenant_id=tenant.id,
                order_number=order_number,
                status=DeliveryJob.Status.DELIVERED,
            )
        except DeliveryJob.DoesNotExist:
            return Response({"detail": "Delivery job not found or not yet delivered."}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role", "").strip()
        try:
            score = int(request.data.get("score", 0))
            if not 1 <= score <= 5:
                raise ValueError
        except (ValueError, TypeError):
            return Response({"detail": "score must be an integer 1–5."}, status=status.HTTP_400_BAD_REQUEST)
        note = str(request.data.get("note") or "").strip()[:200]

        update_fields = []
        if role == "customer":
            customer_id = request.session.get("customer_id")
            if not customer_id:
                return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
            # OPS-5f: ownership gate. Without this, any session holder who guesses a
            # delivered order number could write the customer→driver rating (review
            # fraud / driver-reputation tampering). The order's customer_id lives in the
            # tenant schema (the DeliveryJob is public-schema), so resolve it there and
            # require the session customer to OWN the order (mirrors CustomerOrderRate).
            from django_tenants.utils import schema_context as _sc
            from menu.models import Order as _O
            with _sc(tenant.schema_name):
                _order = _O.objects.filter(order_number=order_number).only("customer_id").first()
            _order_cid = getattr(_order, "customer_id", None) if _order else None
            if _order_cid is None or int(_order_cid) != int(customer_id):
                return Response(
                    {"detail": "You can only rate your own order.", "code": "not_order_owner"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            job.customer_driver_rating = score
            job.customer_driver_note = note
            update_fields = ["customer_driver_rating", "customer_driver_note"]
        elif role == "driver":
            customer_id = request.session.get("customer_id")
            driver = getattr(job, "driver", None)
            if not customer_id or not driver or driver.id != customer_id:
                return Response({"detail": "Driver session required."}, status=status.HTTP_403_FORBIDDEN)
            job.driver_customer_rating = score
            job.driver_customer_note = note
            update_fields = ["driver_customer_rating", "driver_customer_note"]
        elif role == "restaurant":
            user = getattr(request, "user", None)
            tenant_ctx = getattr(request, "tenant", None)
            if not user or not user.is_authenticated:
                return Response({"detail": "Owner session required."}, status=status.HTTP_401_UNAUTHORIZED)
            if not tenant_ctx or tenant_ctx.id != tenant.id:
                return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
            job.restaurant_driver_rating = score
            job.restaurant_driver_note = note
            update_fields = ["restaurant_driver_rating", "restaurant_driver_note"]
        else:
            return Response({"detail": "role must be customer, driver, or restaurant."}, status=status.HTTP_400_BAD_REQUEST)

        job.save(update_fields=update_fields)
        return Response({"detail": "Rating saved.", "score": score})


def _resolve_customer_from_request(request):
    """Return (Customer, error_response) from a customer-session request."""
    customer_id = request.session.get("customer_id") if hasattr(request, "session") else None
    if not customer_id:
        return None, Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return None, Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
    return customer, None


class CustomerSavedAddressListCreateView(APIView):
    """GET  /api/customer/addresses/  — list saved addresses (newest first, max 10).
       POST /api/customer/addresses/  — save a new address."""

    permission_classes = [AllowAny]

    def _get_customer(self, request):
        return _resolve_customer_from_request(request)

    def get(self, request, *args, **kwargs):
        from .models import SavedAddress
        customer, err = self._get_customer(request)
        if err:
            return err
        addresses = SavedAddress.objects.filter(customer=customer)[:10]
        return Response([_serialize_address(a) for a in addresses])

    def post(self, request, *args, **kwargs):
        from .models import SavedAddress
        customer, err = self._get_customer(request)
        if err:
            return err
        # Enforce max 10 saved addresses per customer
        if SavedAddress.objects.filter(customer=customer).count() >= 10:
            return Response(
                {"detail": "Maximum 10 saved addresses allowed.", "code": "address_limit"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        address_text = str(request.data.get("address") or "").strip()[:300]
        if not address_text:
            return Response({"detail": "address is required.", "code": "missing_address"}, status=status.HTTP_400_BAD_REQUEST)
        label = str(request.data.get("label") or "").strip()[:60]
        location_url = str(request.data.get("location_url") or "").strip()[:500]
        lat = _parse_coord(request.data.get("lat"), -90, 90)
        lng = _parse_coord(request.data.get("lng"), -180, 180)
        addr = SavedAddress.objects.create(
            customer=customer,
            label=label,
            address=address_text,
            location_url=location_url,
            lat=lat,
            lng=lng,
        )
        return Response(_serialize_address(addr), status=status.HTTP_201_CREATED)


class CustomerSavedAddressDeleteView(APIView):
    """DELETE /api/customer/addresses/<id>/ — remove a saved address."""

    permission_classes = [AllowAny]

    def delete(self, request, address_id, *args, **kwargs):
        from .models import SavedAddress
        customer, err = _resolve_customer_from_request(request)
        if err:
            return err
        try:
            addr = SavedAddress.objects.get(pk=address_id, customer=customer)
        except SavedAddress.DoesNotExist:
            return Response({"detail": "Address not found."}, status=status.HTTP_404_NOT_FOUND)
        addr.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _serialize_address(addr) -> dict:
    return {
        "id": addr.pk,
        "label": addr.label or "",
        "address": addr.address,
        "location_url": addr.location_url or "",
        "lat": addr.lat,
        "lng": addr.lng,
        "created_at": addr.created_at.isoformat(),
    }


# ── Admin: delivery zone management ───────────────────────────────────────────


class AdminDriverListView(APIView):
    """GET /api/admin/drivers/ — list all registered drivers with job stats (platform admin).

    OPS-5b: consolidated onto IsPlatformAdmin.
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.

        from .models import Customer, DeliveryJob
        from django.db.models import Avg, Count, Q

        drivers = list(
            Customer.objects.filter(is_driver=True)
            .order_by("-driver_position_updated_at", "-id")
        )

        # Batch job stats per driver
        stats_map = {}
        if drivers:
            driver_ids = [d.id for d in drivers]
            for s in (DeliveryJob.objects
                      .filter(driver_id__in=driver_ids)
                      .values("driver_id")
                      .annotate(
                          total_jobs=Count("id"),
                          completed_jobs=Count("id", filter=Q(status="delivered")),
                          avg_rating=Avg("customer_driver_rating"),
                      )):
                stats_map[s["driver_id"]] = s

        # Batch earnings (sum of delivered payouts) and payouts (sum of settlements).
        earned_map, paid_map = {}, {}
        if drivers:
            from .models import DriverPayout
            from django.db.models import Sum
            for row in (DeliveryJob.objects
                        .filter(driver_id__in=driver_ids, status="delivered")
                        .values("driver_id").annotate(e=Sum("driver_payout"))):
                earned_map[row["driver_id"]] = row["e"] or 0
            for row in (DriverPayout.objects
                        .filter(driver_id__in=driver_ids)
                        .values("driver_id").annotate(p=Sum("amount"))):
                paid_map[row["driver_id"]] = row["p"] or 0

        result = []
        for d in drivers:
            s = stats_map.get(d.id, {})
            avg = s.get("avg_rating")
            earned = earned_map.get(d.id, 0)
            paid = paid_map.get(d.id, 0)
            result.append({
                "id": d.id,
                "name": d.name or "",
                "phone": d.phone or "",
                "email": d.email or "",
                "approved": bool(d.driver_approved),
                "vehicle": d.driver_vehicle or "",
                "driver_vehicle_type": d.driver_vehicle_type or "",
                "driver_licence_url": d.driver_licence_url or "",
                "driver_insurance_url": d.driver_insurance_url or "",
                "driver_car_approved": bool(d.driver_car_approved),
                "is_online": d.is_driver_online,
                "driver_lat": d.driver_lat,
                "driver_lng": d.driver_lng,
                "position_updated_at": (
                    d.driver_position_updated_at.isoformat()
                    if d.driver_position_updated_at else None
                ),
                "total_jobs": s.get("total_jobs", 0),
                "completed_jobs": s.get("completed_jobs", 0),
                "avg_rating": round(float(avg), 1) if avg is not None else None,
                "earned": str(earned),
                "paid": str(paid),
                "owed": str(earned - paid),
                "created_at": d.created_at.isoformat(),
            })
        return Response(result)


class AdminDriverApprovalView(APIView):
    """POST /api/admin/drivers/<driver_id>/approve/  — vet & approve a driver application.
       POST /api/admin/drivers/<driver_id>/reject/   — decline it (revokes driver status).
    Platform admin only.
    """

    permission_classes = [IsPlatformAdmin]

    def post(self, request, driver_id, *args, **kwargs):
        from .models import Customer
        approve = request.path.rstrip("/").endswith("approve")
        try:
            driver = Customer.objects.get(pk=driver_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver not found.", "code": "not_found"}, status=404)

        if approve:
            driver.driver_approved = True
            driver.save(update_fields=["driver_approved", "updated_at"])
        else:
            # Decline: revoke the application and force offline.
            driver.driver_approved = False
            driver.is_driver = False
            driver.is_driver_online = False
            driver.save(update_fields=["driver_approved", "is_driver", "is_driver_online", "updated_at"])

        log_admin_action(
            action=(AdminAuditLog.Actions.DRIVER_APPROVED if approve
                    else AdminAuditLog.Actions.DRIVER_REJECTED),
            request=request,
            target_repr=f"driver:{driver.id}",
            metadata={"name": driver.name or "", "phone": driver.phone or ""},
        )
        return Response({
            "id": driver.id,
            "is_driver": bool(driver.is_driver),
            "approved": bool(driver.driver_approved),
        })


class AdminDriverEarningsView(APIView):
    """GET  /api/admin/drivers/<id>/earnings/ — earnings summary + recent deliveries/payouts.
       POST /api/admin/drivers/<id>/payout/   — record a settlement paid to the driver.
    """

    permission_classes = [IsPlatformAdmin]

    def _check(self, request):
        u = getattr(request, "user", None)
        from .models import User
        return isinstance(u, User) and u.is_platform_admin

    def get(self, request, driver_id, *args, **kwargs):
        if not self._check(request):
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            driver = Customer.objects.get(pk=driver_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)

        from .models import DeliveryJob, DriverPayout
        from .driver_service import driver_earnings_summary

        summary = driver_earnings_summary(driver_id)
        deliveries = list(
            DeliveryJob.objects.filter(driver_id=driver_id, status="delivered")
            .order_by("-delivered_at")[:20]
        )
        payouts = list(DriverPayout.objects.filter(driver_id=driver_id)[:20])
        return Response({
            "driver_id": driver.id,
            "name": driver.name or "",
            "phone": driver.phone or "",
            "earned": str(summary["earned"]),
            "paid": str(summary["paid"]),
            "owed": str(summary["owed"]),
            "deliveries": [
                {
                    "order_number": j.order_number,
                    "payout": str(j.driver_payout),
                    "delivered_at": j.delivered_at.isoformat() if j.delivered_at else None,
                }
                for j in deliveries
            ],
            "payouts": [
                {
                    "id": p.id,
                    "amount": str(p.amount),
                    "method": p.method,
                    "reference": p.reference,
                    "note": p.note,
                    "created_at": p.created_at.isoformat(),
                }
                for p in payouts
            ],
        })

    def post(self, request, driver_id, *args, **kwargs):
        if not self._check(request):
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        if not Customer.objects.filter(pk=driver_id, is_driver=True).exists():
            return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)

        from .driver_service import record_driver_payout
        from .wallet_service import WalletError

        method = str(request.data.get("method") or "cash").strip()
        note = str(request.data.get("note") or "").strip()[:200]
        reference = str(request.data.get("reference") or "").strip()[:120]
        idem = str(request.data.get("idempotency_key") or "").strip()[:120] or None
        try:
            payout = record_driver_payout(
                driver_id, request.data.get("amount"),
                method=method, note=note, reference=reference,
                actor_user_id=getattr(request.user, "id", None), idempotency_key=idem,
            )
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_admin_action(
            action=AdminAuditLog.Actions.DRIVER_PAYOUT_RECORDED,
            request=request,
            target_repr=f"driver:{driver_id}",
            metadata={"amount": str(payout.amount), "method": method, "reference": reference},
        )
        from .driver_service import driver_earnings_summary
        summary = driver_earnings_summary(driver_id)
        return Response({
            "payout_id": payout.id,
            "amount": str(payout.amount),
            "owed": str(summary["owed"]),
            "paid": str(summary["paid"]),
        })


class DriverEarningsView(APIView):
    """GET /api/driver/earnings/ — the signed-in driver's own earnings summary."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            cust = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        from .driver_service import driver_earnings_summary, CASHOUT_MIN
        s = driver_earnings_summary(customer_id)
        available = str(cust.wallet_balance or "0")
        return Response({
            "earned": str(s["earned"]), "paid": str(s["paid"]), "owed": str(s["owed"]),
            # Wallet-based available balance (the cashable amount) + cash-out eligibility.
            "available": available,
            "cashout_min": str(CASHOUT_MIN),
            "can_cash_out": (cust.wallet_balance or 0) >= CASHOUT_MIN,
            # Ride-hailing earnings.
            "ride_earned": str(s["ride_earned"]),
            "rides_completed": s["rides_completed"],
        })


class DriverCashoutView(APIView):
    """GET  /api/driver/cashout/  → the driver's current PENDING cash-out (or null).
    POST /api/driver/cashout/  → create a cash-out request {amount} (wallet ≥ min)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def _driver(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return None, Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        cust = Customer.objects.filter(pk=customer_id, is_driver=True).first()
        if cust is None:
            return None, Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)
        return cust, None

    def _serialize(self, req):
        from django.utils import timezone as _tz
        return {
            "id": req.id, "amount": str(req.amount), "code": req.code,
            "status": req.status, "expires_at": req.expires_at.isoformat(),
            "expired": req.expires_at <= _tz.now(),
        }

    def get(self, request, *args, **kwargs):
        cust, err = self._driver(request)
        if err:
            return err
        from django.utils import timezone as _tz
        from .models import DriverCashoutRequest
        req = (
            DriverCashoutRequest.objects
            .filter(driver_id=cust.id, status=DriverCashoutRequest.Status.PENDING, expires_at__gt=_tz.now())
            .order_by("-created_at").first()
        )
        return Response({"pending": self._serialize(req) if req else None})

    def post(self, request, *args, **kwargs):
        cust, err = self._driver(request)
        if err:
            return err
        from .driver_service import create_cashout_request, CashoutError
        from .wallet_service import WalletError
        try:
            req = create_cashout_request(cust.id, request.data.get("amount"))
        except CashoutError as e:
            return Response({"detail": str(e), "code": getattr(e, "code", "cashout_error")},
                            status=status.HTTP_400_BAD_REQUEST)
        except WalletError as e:
            return Response({"detail": str(e), "code": "cashout_error"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self._serialize(req), status=status.HTTP_201_CREATED)


class DriverCashoutCancelView(APIView):
    """POST /api/driver/cashout/<id>/cancel/ — driver cancels their own pending request."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, request_id, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        from django.utils import timezone as _tz
        from .models import DriverCashoutRequest
        req = DriverCashoutRequest.objects.filter(pk=request_id, driver_id=customer_id).first()
        if req is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if req.status == DriverCashoutRequest.Status.PENDING:
            req.status = DriverCashoutRequest.Status.CANCELLED
            req.resolved_at = _tz.now()
            req.save(update_fields=["status", "resolved_at"])
        return Response({"status": req.status})


class DriverDeliveriesView(APIView):
    """GET /api/driver/deliveries/ — the signed-in driver's recent finished jobs
    (delivered or failed), newest first, for an in-app history view."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        from .models import DeliveryJob
        jobs = list(
            DeliveryJob.objects.filter(
                driver_id=customer_id,
                status__in=[DeliveryJob.Status.DELIVERED, DeliveryJob.Status.FAILED],
            ).order_by("-created_at")[:50]
        )
        # Batch-resolve restaurant names (avoids N+1 via _tenant_slug_name cache).
        _names = {j.tenant_id: _tenant_slug_name(j.tenant_id)[1] for j in jobs}
        results = [{
            "id": j.id,
            "order_number": j.order_number,
            "status": j.status,
            "restaurant_name": _names.get(j.tenant_id, ""),
            "delivery_address": j.delivery_address,
            "driver_payout": str(j.driver_payout),
            "delivered_at": j.delivered_at.isoformat() if j.delivered_at else None,
            "failed_at": j.failed_at.isoformat() if j.failed_at else None,
            "created_at": j.created_at.isoformat(),
            "customer_driver_rating": j.customer_driver_rating,
        } for j in jobs]
        return Response({"results": results})


class AdminPlatformAnalyticsView(APIView):
    """GET /api/admin/platform-analytics/ — cross-platform aggregate stats (platform admin only)."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from django.db.models import Avg, Count, Q, Sum
        from django.utils import timezone
        from .models import Customer, DeliveryJob, DeliveryZone, PlatformFlashSale, RideRequest, WalletTransaction
        from tenancy.models import Tenant

        now = timezone.now()

        # ── Tenants ───────────────────────────────────────────────────────────
        tenant_qs = Tenant.objects.all()
        total_tenants = tenant_qs.count()
        active_tenants = tenant_qs.filter(lifecycle_status="active").count()
        suspended_tenants = tenant_qs.filter(lifecycle_status="suspended").count()
        canceled_tenants = tenant_qs.filter(lifecycle_status="canceled").count()

        # ── Customers & drivers ───────────────────────────────────────────────
        total_customers = Customer.objects.count()
        driver_stats = Customer.objects.filter(is_driver=True).aggregate(
            total=Count("id"),
            online=Count("id", filter=Q(is_driver_online=True)),
        )
        total_drivers = driver_stats["total"] or 0
        drivers_online = driver_stats["online"] or 0

        # ── Delivery jobs ─────────────────────────────────────────────────────
        job_agg = DeliveryJob.objects.aggregate(
            total=Count("id"),
            delivered=Count("id", filter=Q(status="delivered")),
            failed=Count("id", filter=Q(status="failed")),
            searching=Count("id", filter=Q(status="searching")),
            avg_rating=Avg("customer_driver_rating"),
            total_fees=Sum("delivery_fee"),
            total_payouts=Sum("driver_payout"),
        )
        active_jobs = (
            DeliveryJob.objects.exclude(status__in=["delivered", "failed"]).count()
        )

        # ── Delivery zones ────────────────────────────────────────────────────
        zone_agg = DeliveryZone.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
        )

        # ── Flash sales ───────────────────────────────────────────────────────
        fs_agg = PlatformFlashSale.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True, active_from__lte=now, active_until__gte=now)),
            total_redemptions=Sum("redemption_count"),
        )

        # ── Ride-hailing ──────────────────────────────────────────────────────
        ride_agg = RideRequest.objects.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            cancelled=Count("id", filter=Q(status="cancelled")),
            wallet_paid=Count("id", filter=Q(status="completed", paid_with_wallet=True)),
            fare_gmv=Sum("fare", filter=Q(status="completed")),
        )
        ride_active = RideRequest.objects.exclude(
            status__in=["completed", "cancelled"]
        ).count()

        # ── Wallet ────────────────────────────────────────────────────────────
        wallet_agg = Customer.objects.aggregate(
            total_balance=Sum("wallet_balance"),
        )
        txn_agg = WalletTransaction.objects.aggregate(
            total=Count("id"),
            total_bonus=Sum("amount", filter=Q(type="bonus")),
            total_payments=Sum("amount", filter=Q(type="payment")),
        )

        # ── Money model: outstanding liabilities ──────────────────────────────
        from decimal import Decimal as _Dec
        from .models import DriverPayout, TenantFloatTransaction  # noqa: F401
        from tenancy.models import Tenant as _Tenant

        total_float = _Tenant.objects.aggregate(s=Sum("float_balance"))["s"] or _Dec("0")
        driver_earned = (
            DeliveryJob.objects.filter(status="delivered").aggregate(s=Sum("driver_payout"))["s"] or _Dec("0")
        )
        driver_paid = DriverPayout.objects.aggregate(s=Sum("amount"))["s"] or _Dec("0")
        driver_owed = driver_earned - driver_paid

        def _f(val, decimals=2):
            """Safely convert decimal/float/None to rounded float."""
            if val is None:
                return None
            return round(float(val), decimals)

        return Response({
            "tenants": {
                "total": total_tenants,
                "active": active_tenants,
                "suspended": suspended_tenants,
                "canceled": canceled_tenants,
            },
            "customers": {
                "total": total_customers,
                "drivers_total": total_drivers,
                "drivers_online": drivers_online,
            },
            "deliveries": {
                "total_jobs": job_agg["total"] or 0,
                "delivered": job_agg["delivered"] or 0,
                "failed": job_agg["failed"] or 0,
                "active": active_jobs,
                "searching": job_agg["searching"] or 0,
                "avg_driver_rating": _f(job_agg["avg_rating"], 1),
                "total_fees": _f(job_agg["total_fees"]),
                "total_driver_payouts": _f(job_agg["total_payouts"]),
            },
            "zones": {
                "total": zone_agg["total"] or 0,
                "active": zone_agg["active"] or 0,
            },
            "flash_sales": {
                "total": fs_agg["total"] or 0,
                "live": fs_agg["active"] or 0,
                "total_redemptions": fs_agg["total_redemptions"] or 0,
            },
            "wallet": {
                "total_balance": _f(wallet_agg["total_balance"]),
                "total_transactions": txn_agg["total"] or 0,
                "total_bonus_issued": _f(txn_agg["total_bonus"]),
                "total_payments": _f(txn_agg["total_payments"]),
            },
            "financials": {
                "customer_wallet_liability": _f(wallet_agg["total_balance"]) or 0.0,
                "restaurant_float_outstanding": _f(total_float) or 0.0,
                "driver_owed": _f(driver_owed) or 0.0,
            },
            "rides": {
                "total": ride_agg["total"] or 0,
                "completed": ride_agg["completed"] or 0,
                "cancelled": ride_agg["cancelled"] or 0,
                "active": ride_active,
                "fare_gmv": str((_Dec(ride_agg["fare_gmv"] or 0)).quantize(_Dec("0.01"))),
                "wallet_paid": ride_agg["wallet_paid"] or 0,
                # Clamped: wallet_paid is bounded by completed under correct
                # data, but an admin data correction must not show a negative.
                "cash_paid": max(0, (ride_agg["completed"] or 0) - (ride_agg["wallet_paid"] or 0)),
            },
        })


class AdminDeliveryZoneListCreateView(APIView):
    """
    GET  /api/admin/delivery-zones/   — list all zones (platform admin only)
    POST /api/admin/delivery-zones/   — create a zone

    OPS-5b: consolidated onto IsPlatformAdmin (drops inline is_platform_admin check).
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import DeliveryZone
        from django_tenants.utils import schema_context
        with schema_context("public"):
            zones = list(DeliveryZone.objects.all())
        return Response([_serialize_zone(z) for z in zones])

    def post(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import DeliveryZone
        from django_tenants.utils import schema_context

        data = request.data
        name = str(data.get("name") or "").strip()
        city = str(data.get("city") or "").strip()
        polygon = data.get("polygon") or []

        if not name or not city:
            return Response({"detail": "name and city are required."}, status=400)
        if not _valid_polygon(polygon):
            return Response({"detail": "polygon must be a list of ≥ 3 {lat, lng} points."}, status=400)

        center_lat = data.get("center_lat")
        center_lng = data.get("center_lng")
        try:
            approx_radius_km = float(data.get("approx_radius_km", 5.0))
            center_lat = float(center_lat) if center_lat is not None else None
            center_lng = float(center_lng) if center_lng is not None else None
        except (TypeError, ValueError):
            return Response(
                {"detail": "center_lat, center_lng and approx_radius_km must be numbers."},
                status=400,
            )

        fee_tiers = data.get("fee_tiers") or []
        if not isinstance(fee_tiers, list):
            fee_tiers = []

        with schema_context("public"):
            zone = DeliveryZone.objects.create(
                name=name,
                city=city,
                polygon=polygon,
                center_lat=center_lat,
                center_lng=center_lng,
                approx_radius_km=approx_radius_km,
                is_active=bool(data.get("is_active", True)),
                fee_tiers=fee_tiers,
            )
        return Response(_serialize_zone(zone), status=status.HTTP_201_CREATED)


class AdminDeliveryZoneDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/delivery-zones/<zone_id>/ — platform admin only."""

    permission_classes = [IsPlatformAdmin]

    def _get_zone(self, zone_id):
        from .models import DeliveryZone
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                return DeliveryZone.objects.get(pk=zone_id)
            except DeliveryZone.DoesNotExist:
                return None

    def get(self, request, zone_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        zone = self._get_zone(zone_id)
        if zone is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(_serialize_zone(zone))

    def patch(self, request, zone_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import DeliveryZone
        from django_tenants.utils import schema_context

        with schema_context("public"):
            try:
                zone = DeliveryZone.objects.get(pk=zone_id)
            except DeliveryZone.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)

            data = request.data
            update_fields = []
            for field in ("name", "city"):
                if field in data and data[field]:
                    setattr(zone, field, str(data[field]).strip())
                    update_fields.append(field)
            if "polygon" in data:
                if not _valid_polygon(data["polygon"]):
                    return Response(
                        {"detail": "polygon must be a list of ≥ 3 {lat, lng} points."}, status=400
                    )
                zone.polygon = data["polygon"]
                update_fields.append("polygon")
            try:
                if "center_lat" in data:
                    zone.center_lat = float(data["center_lat"]) if data["center_lat"] is not None else None
                    update_fields.append("center_lat")
                if "center_lng" in data:
                    zone.center_lng = float(data["center_lng"]) if data["center_lng"] is not None else None
                    update_fields.append("center_lng")
                if "approx_radius_km" in data:
                    zone.approx_radius_km = float(data["approx_radius_km"])
                    update_fields.append("approx_radius_km")
            except (TypeError, ValueError):
                return Response(
                    {"detail": "center_lat, center_lng and approx_radius_km must be numbers."},
                    status=400,
                )
            if "is_active" in data:
                zone.is_active = bool(data["is_active"])
                update_fields.append("is_active")
            if "fee_tiers" in data:
                zone.fee_tiers = data["fee_tiers"] if isinstance(data["fee_tiers"], list) else []
                update_fields.append("fee_tiers")

            if update_fields:
                zone.save(update_fields=update_fields)

        return Response(_serialize_zone(zone))

    def delete(self, request, zone_id, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import DeliveryZone
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                DeliveryZone.objects.get(pk=zone_id).delete()
            except DeliveryZone.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerDeliveryZoneView(APIView):
    """GET /api/owner/delivery-zone/ — return the zone this restaurant is assigned to (if any)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required."}, status=403)

        from django_tenants.utils import schema_context
        from tenancy.models import Profile

        with schema_context(tenant.schema_name):
            profile = Profile.objects.filter(tenant=tenant).first()
            if not profile:
                return Response({"detail": "Profile not found."}, status=404)

            zone_id = profile.delivery_zone_id
            radius = profile.delivery_radius_km

        if not zone_id:
            return Response({"zone": None, "delivery_radius_km": radius})

        from .models import DeliveryZone
        with schema_context("public"):
            try:
                zone = DeliveryZone.objects.get(pk=zone_id)
                return Response({"zone": _serialize_zone(zone), "delivery_radius_km": radius})
            except DeliveryZone.DoesNotExist:
                return Response({"zone": None, "delivery_radius_km": radius})


class OwnerDeliveryRadiusUpdateView(APIView):
    """PATCH /api/owner/delivery-radius/ — update delivery radius for this restaurant."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required."}, status=403)

        try:
            radius = float(request.data.get("delivery_radius_km", 0))
            if radius < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "delivery_radius_km must be a positive number."}, status=400)

        from django_tenants.utils import schema_context
        from tenancy.models import Profile

        with schema_context(tenant.schema_name):
            Profile.objects.filter(tenant=tenant).update(delivery_radius_km=radius or None)

        return Response({"delivery_radius_km": radius or None})


# ── Admin: delivery job management ────────────────────────────────────────────


class AdminDeliveryJobListView(APIView):
    """GET /api/admin/delivery-jobs/ — list all delivery jobs (platform admin).

    ?status=  filter by status
    ?tenant_id= filter by tenant

    OPS-5b: consolidated onto IsPlatformAdmin (drops inline is_platform_admin check).
    """

    permission_classes = [IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.
        from .models import DeliveryJob
        qs = DeliveryJob.objects.select_related("driver", "zone").order_by("-created_at")
        status_filter = request.query_params.get("status")
        tenant_filter = request.query_params.get("tenant_id")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if tenant_filter:
            qs = qs.filter(tenant_id=tenant_filter)

        jobs = list(qs[:100])
        # Batch-fetch business_type for all jobs (one query — no N+1).
        all_tenant_ids = {j.tenant_id for j in jobs}
        _biz_types = _batch_business_types(all_tenant_ids)
        data = [
            _serialize_delivery_job(j, include_driver_position=True,
                                    business_type=_biz_types.get(j.tenant_id, "restaurant"))
            for j in jobs
        ]
        # Enrich with the restaurant name so the admin console can show it (the shared
        # job serializer only carries tenant_id).
        tenant_ids = {d["tenant_id"] for d in data if d.get("tenant_id")}
        if tenant_ids:
            from tenancy.models import Tenant
            names = dict(Tenant.objects.filter(id__in=tenant_ids).values_list("id", "name"))
            for d in data:
                d["tenant_name"] = names.get(d["tenant_id"], "")
        return Response(data)


class AdminCreateDeliveryJobView(APIView):
    """POST /api/admin/delivery-jobs/ — create a DeliveryJob for an order.

    Used to manually trigger a delivery (e.g. the restaurant marks an order as ready
    and the platform auto-dispatches). Normally this would be called automatically
    when a marketplace delivery order is placed.

    Body: {
      tenant_id, order_number, pickup_address, pickup_lat, pickup_lng,
      delivery_address, delivery_lat, delivery_lng, delivery_fee, driver_payout,
      zone_id (optional)
    }

    OPS-5b: consolidated onto IsPlatformAdmin + audit log on create.
    """

    permission_classes = [IsPlatformAdmin]

    def post(self, request, *args, **kwargs):
        # Permission gate is IsPlatformAdmin (class-level) — no inline check needed.

        from .models import DeliveryJob, DeliveryZone
        from decimal import Decimal, InvalidOperation

        data = request.data
        for field in ("tenant_id", "order_number"):
            if not data.get(field):
                return Response({"detail": f"{field} is required."}, status=400)

        try:
            tenant_id = int(data["tenant_id"])
            order_number = str(data["order_number"]).strip().upper()
        except (ValueError, TypeError):
            return Response({"detail": "Invalid tenant_id or order_number."}, status=400)

        if DeliveryJob.objects.filter(tenant_id=tenant_id, order_number=order_number).exists():
            return Response({"detail": "A delivery job already exists for this order."}, status=409)

        zone = None
        if data.get("zone_id"):
            try:
                zone = DeliveryZone.objects.get(pk=data["zone_id"])
            except DeliveryZone.DoesNotExist:
                pass

        # Auto-compute fee from zone tiers when distance coords are available
        # and caller hasn't explicitly provided a fee.
        _explicit_fee = data.get("delivery_fee")
        _explicit_payout = data.get("driver_payout")
        if _explicit_fee is None and zone and zone.fee_tiers:
            pickup_lat = float(data["pickup_lat"]) if data.get("pickup_lat") else None
            pickup_lng = float(data["pickup_lng"]) if data.get("pickup_lng") else None
            del_lat = float(data["delivery_lat"]) if data.get("delivery_lat") else None
            del_lng = float(data["delivery_lng"]) if data.get("delivery_lng") else None
            if all(v is not None for v in (pickup_lat, pickup_lng, del_lat, del_lng)):
                distance = _haversine_km(pickup_lat, pickup_lng, del_lat, del_lng)
                _explicit_fee = str(zone.compute_fee(distance))

        try:
            delivery_fee = Decimal(str(_explicit_fee or "0"))
            driver_payout = Decimal(str(_explicit_payout or "0"))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Invalid delivery_fee or driver_payout."}, status=400)

        job = DeliveryJob.objects.create(
            tenant_id=tenant_id,
            order_number=order_number,
            pickup_address=str(data.get("pickup_address") or "")[:200],
            pickup_lat=float(data["pickup_lat"]) if data.get("pickup_lat") else None,
            pickup_lng=float(data["pickup_lng"]) if data.get("pickup_lng") else None,
            delivery_address=str(data.get("delivery_address") or "")[:200],
            delivery_lat=float(data["delivery_lat"]) if data.get("delivery_lat") else None,
            delivery_lng=float(data["delivery_lng"]) if data.get("delivery_lng") else None,
            delivery_fee=delivery_fee,
            driver_payout=driver_payout,
            zone=zone,
        )
        # Real-time dispatch: nudge online/free drivers to claim the new job.
        try:
            from accounts.push import push_new_job_to_drivers as _pnj
            _pnj(None)
        except Exception:
            pass
        log_admin_action(
            action=AdminAuditLog.Actions.DELIVERY_JOB_CREATED,
            request=request,
            target_repr=f"job:{job.id}:{order_number}",
            metadata={
                "job_id": job.id,
                "tenant_id": tenant_id,
                "order_number": order_number,
                "delivery_fee": str(delivery_fee),
                "driver_payout": str(driver_payout),
            },
        )
        _bt = _batch_business_types({job.tenant_id}).get(job.tenant_id, "restaurant")
        return Response(_serialize_delivery_job(job, business_type=_bt), status=status.HTTP_201_CREATED)


# ── B1-followup: one-click email unsubscribe ────────────────────────────────────


class _IgnoreClientNegotiation(BaseContentNegotiation):
    """Disable Accept-header negotiation for the unsubscribe endpoint.

    DRF runs perform_content_negotiation() in APIView.initial() BEFORE get()/post().
    With the prod renderer set (JSONRenderer only — BrowsableAPIRenderer is added
    just when DJANGO_DEBUG=True), a request with a JSON-less Accept (e.g. RFC 8058
    one-click POSTs that send `Accept: text/html`) would raise NotAcceptable → HTTP
    406 and the recipient would never be unsubscribed.  Always pick the view's own
    renderer so the Accept header can never 406 a compliance-critical opt-out.
    """

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


class EmailUnsubscribeView(APIView):
    """GET/POST /api/unsubscribe/<token>/  — public promotional-email opt-out.

    Gmail/Yahoo bulk-sender rules + CAN-SPAM require a working one-click
    unsubscribe.  Marketing mail carries an https link to this endpoint (visible
    body link + RFC 8058 List-Unsubscribe header), with the recipient encoded in
    a tamper-proof django.core.signing token (no DB field needed).

      * GET  — a human clicking the body link → confirmation HTML page.
      * POST — the mailbox provider's automated ONE-CLICK call (RFC 8058). It
        carries NO credentials and NO meaningful body, so the view is AllowAny
        with authentication_classes = [] — there is no SessionAuthentication to
        enforce CSRF, so the POST is accepted without a CSRF token.

    Both verbs have the SAME effect: flip the token's customer
    notify_promotions=False (idempotent).  An unknown/invalid/forged token does
    NOT 500 and returns the SAME generic confirmation as a valid one, so the
    response never leaks whether a given id exists.  The signed token resists
    forgery; EmailUnsubscribeThrottle blunts sequential scanning.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [EmailUnsubscribeThrottle]
    # Renderer-agnostic: the view writes its own HttpResponse, but DRF still runs
    # content negotiation in initial() before the handler.  Advertise an HTML
    # renderer and ignore the client's Accept so a strict/JSON-less Accept (RFC
    # 8058 one-click providers) can never 406 the opt-out before it runs.
    renderer_classes = [StaticHTMLRenderer]
    content_negotiation_class = _IgnoreClientNegotiation

    _PAGE = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Unsubscribed</title></head>"
        "<body style=\"font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;"
        "padding:0 1rem;text-align:center\">"
        "<h1>You've been unsubscribed</h1>"
        "<p>You will no longer receive promotional emails from Kepoli. "
        "Order updates are unaffected.</p>"
        "</body></html>"
    )

    def _unsubscribe(self, token):
        """Flip notify_promotions=False for the token's customer (idempotent).

        Never raises and never reveals whether the id exists — an invalid token
        and an already-opted-out customer both fall through silently.
        """
        from .unsubscribe import load_unsubscribe_token

        customer_id = load_unsubscribe_token(token)
        if customer_id is None:
            return
        try:
            customer = Customer.objects.filter(pk=customer_id).first()
            if customer is not None and customer.notify_promotions:
                customer.notify_promotions = False
                customer.save(update_fields=["notify_promotions"])
        except Exception:  # pragma: no cover - defensive: opt-out must never 500
            logger.exception("Email unsubscribe failed for token customer %s", customer_id)

    def _respond(self):
        from django.http import HttpResponse

        return HttpResponse(self._PAGE, content_type="text/html; charset=utf-8")

    def get(self, request, token, *args, **kwargs):
        self._unsubscribe(token)
        return self._respond()

    def post(self, request, token, *args, **kwargs):
        # RFC 8058 one-click: same effect as GET, accepted without CSRF/auth/body.
        self._unsubscribe(token)
        return self._respond()
