import json
import logging
import random
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
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .messaging import send_password_reset_email
from .models import Customer
from .throttles import (
    ActivationThrottle,
    CustomerEmailOtpRequestThrottle,
    CustomerEmailOtpVerifyThrottle,
    CustomerGoogleAuthThrottle,
    CustomerOtpRequestThrottle,
    CustomerOtpVerifyThrottle,
    CustomerProfileUpdateThrottle,
    LoginBurstThrottle,
    LoginSustainedThrottle,
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
)
from .serializers import (
    ActivationSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)

logger = logging.getLogger("app.customer")


def serialize_user_session(user):
    tenant = getattr(user, "tenant", None)
    can_access_admin_console = bool(user.is_staff or user.is_superuser or user.is_platform_admin)
    can_edit_tenant_menu = bool(user.is_tenant_owner or user.is_tenant_staff)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_platform_admin": user.is_platform_admin,
        "can_access_admin_console": can_access_admin_console,
        "can_edit_tenant_menu": can_edit_tenant_menu,
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


def build_frontend_base_url(request, user):
    domain = None
    tenant = getattr(user, "tenant", None)
    if tenant is not None:
        primary = tenant.domains.filter(is_primary=True).first()
        if primary:
            domain = primary.domain

    if not domain:
        host = request.get_host().split(":")[0]
        domain = host

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
    }


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

        code = f"{random.randint(100000, 999999)}"
        cache_key = _OTP_CACHE_KEY.format(phone=phone)
        cache.set(cache_key, {"code": code, "attempts": 0, "expires_at": time.time() + _OTP_TTL}, timeout=_OTP_TTL)
        _send_otp(phone, code)

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

        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
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

        # Import Order from menu app — cross-app import is intentional here.
        from menu.models import Order
        qs = (
            Order.objects.filter(customer=customer)
            .order_by("-created_at")
            .values(
                "order_number", "status", "fulfillment_type",
                "table_label", "total", "currency", "created_at",
                "customer_name",
            )[:20]
        )
        return Response({"orders": list(qs), "count": len(qs)})


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

        code = f"{random.randint(100000, 999999)}"
        cache_key = f"customer_email_otp:{email}"
        cache.set(cache_key, {"code": code, "attempts": 0, "expires_at": time.time() + _OTP_TTL}, timeout=_OTP_TTL)
        send_otp_email(email, code)

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

        request.session["customer_id"] = customer.pk
        return Response({"customer": _serialize_customer(customer)})


# ── Customer profile update ───────────────────────────────────────────────────


class CustomerProfileUpdateView(APIView):
    """PATCH /api/customer/profile/ — update name for the current customer session."""

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

        name = (request.data.get("name") or "").strip()[:80]
        if name:
            customer.name = name
            customer.save(update_fields=["name", "updated_at"])

        return Response({"customer": _serialize_customer(customer)})


# ── Staff management (owner only) ─────────────────────────────────────────────

import re as _re
import secrets as _secrets


def _is_tenant_owner(request, tenant) -> bool:
    """Return True if the request user is the owner of the given tenant."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
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
            .values("id", "email", "first_name", "last_name", "username", "date_joined")
        )
        results = [
            {
                "id": s["id"],
                "email": s["email"],
                "name": f"{s['first_name']} {s['last_name']}".strip() or s["username"],
                "username": s["username"],
                "date_joined": s["date_joined"].isoformat() if s["date_joined"] else None,
            }
            for s in staff
        ]
        return Response({"results": results, "count": len(results)})

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
            signin_url = f"{base_url}/signin" if base_url else "/signin"

            _send_mail(
                subject=f"You've been added to {tenant.name}",
                message=(
                    f"Hi {first_name},\n\n"
                    f"You've been added as a staff member at {tenant.name}.\n\n"
                    f"Sign in at: {signin_url}\n"
                    f"Email: {email}\n"
                    f"Temporary password: {temp_password}\n\n"
                    f"Please change your password after signing in.\n\n"
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
    """DELETE /api/owner/staff/<staff_id>/ — remove a staff account from this tenant."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, staff_id, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not _is_tenant_owner(request, tenant):
            return Response({"detail": "Owner access required.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from .models import User
        staff_user = User.objects.filter(id=staff_id, tenant=tenant, role=User.Roles.TENANT_STAFF).first()
        if staff_user is None:
            return Response({"detail": "Staff member not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        staff_user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Customer wallet ────────────────────────────────────────────────────────────


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

        from .models import WalletTransaction
        txs = WalletTransaction.objects.filter(customer=customer).order_by("-created_at")[:50]
        return Response({
            "balance": str(customer.wallet_balance),
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


# ── Admin bonus campaigns ──────────────────────────────────────────────────────


class AdminWalletBonusView(APIView):
    """POST /api/admin/wallet/bonus/ — issue bonus credits to customers.

    Body: { "amount": "10.00", "note": "Welcome bonus", "customer_ids": [1, 2] }
    Omit customer_ids (or set all_customers=true) to credit every customer.
    Requires platform_superadmin role.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not (user and (user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False))):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

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

        note = str(request.data.get("note") or "Bonus credits").strip()[:200]
        customer_ids = request.data.get("customer_ids")
        all_customers = bool(request.data.get("all_customers"))

        if customer_ids:
            qs = Customer.objects.filter(pk__in=customer_ids)
        elif all_customers:
            qs = Customer.objects.all()
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
            Customer.objects.filter(pk__in=ids).update(
                wallet_balance=F("wallet_balance") + amount
            )
            WalletTransaction.objects.bulk_create([
                WalletTransaction(
                    customer_id=cid,
                    type=WalletTransaction.Type.BONUS,
                    amount=amount,
                    note=note,
                )
                for cid in ids
            ])

        return Response({"issued_to": len(ids), "amount": str(amount), "note": note})


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
    schedule = getattr(profile, "business_hours_schedule", None)
    if not schedule or not isinstance(schedule, dict):
        return bool(profile.is_open)
    if not any(isinstance(v, dict) and v.get("enabled", False) for v in schedule.values()):
        return bool(profile.is_open)
    from datetime import datetime as _dt
    _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    now = _dt.utcnow()
    entry = schedule.get(_WDAY[now.weekday()])
    if not entry or not isinstance(entry, dict) or not entry.get("enabled", False):
        return False
    open_str = (entry.get("open") or "").strip()
    close_str = (entry.get("close") or "").strip()
    if not open_str or not close_str:
        return False
    current_hhmm = now.strftime("%H:%M")
    return open_str <= current_hhmm < close_str


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres (Haversine formula)."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _is_promo_active_now(promo) -> bool:
    """Return True if a Promotion object is currently active (schedule + date range).

    Mirror of menu.views._is_promo_active_now — duplicated here to avoid
    cross-app import while running in the public-schema context.
    """
    from datetime import datetime as _dt, date as _date
    _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    today = _date.today()
    if promo.active_from and today < promo.active_from:
        return False
    if promo.active_until and today > promo.active_until:
        return False
    allowed_days = promo.days or []
    if allowed_days:
        if _WDAY[_dt.utcnow().weekday()] not in allowed_days:
            return False
    ts = (promo.time_start or "").strip()
    te = (promo.time_end or "").strip()
    if ts and te:
        now_hhmm = _dt.utcnow().strftime("%H:%M")
        if not (ts <= now_hhmm < te):
            return False
    return True


class DirectoryView(APIView):
    """GET /api/directory/ — public list of restaurants that opted in.

    Query params:
      city=        filter by city (case-insensitive contains)
      cuisine=     filter by cuisine_type (case-insensitive contains)
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        from tenancy.models import Profile

        city_q = (request.query_params.get("city") or "").strip()
        cuisine_q = (request.query_params.get("cuisine") or "").strip()

        qs = (
            Profile.objects
            .filter(directory_opt_in=True, is_menu_published=True)
            .select_related("tenant")
            .order_by("tenant__name")
        )
        if city_q:
            qs = qs.filter(city__icontains=city_q)
        if cuisine_q:
            qs = qs.filter(cuisine_type__icontains=cuisine_q)

        results = []
        for profile in qs[:100]:
            tenant = profile.tenant
            is_currently_open = bool(profile.is_open) and not getattr(profile, "is_menu_temporarily_disabled", False)

            rating_avg = None
            rating_count = 0
            try:
                from django_tenants.utils import schema_context as _sc
                from django.db.models import Avg, Count
                with _sc(tenant.schema_name):
                    from menu.models import Rating as _Rating
                    agg = _Rating.objects.aggregate(avg=Avg("score"), cnt=Count("id"))
                    if agg["cnt"]:
                        rating_avg = round(float(agg["avg"]), 1)
                        rating_count = agg["cnt"]
            except Exception:
                pass

            results.append({
                "slug": tenant.slug,
                "name": tenant.name,
                "tagline": profile.tagline or "",
                "logo_url": profile.logo_url or "",
                "cuisine_type": profile.cuisine_type or "",
                "city": profile.city or "",
                "is_open": is_currently_open,
                "rating_average": rating_avg,
                "rating_count": rating_count,
                "delivery_enabled": bool(profile.delivery_enabled),
            })

        all_opted = Profile.objects.filter(directory_opt_in=True, is_menu_published=True)
        cities = sorted({p for p in all_opted.exclude(city="").values_list("city", flat=True)})
        cuisines = sorted({p for p in all_opted.exclude(cuisine_type="").values_list("cuisine_type", flat=True)})

        return Response({"restaurants": results, "filters": {"cities": cities, "cuisines": cuisines}})


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

    def get(self, request, *args, **kwargs):
        from tenancy.models import Profile

        q = (request.query_params.get("q") or "").strip().lower()
        city_q = (request.query_params.get("city") or "").strip()
        cuisine_q = (request.query_params.get("cuisine") or "").strip()
        fulfillment = (request.query_params.get("fulfillment") or "any").strip().lower()
        open_only = request.query_params.get("open") == "1"
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
            .filter(directory_opt_in=True, is_menu_published=True)
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

        results = []
        for profile in qs[:200]:
            tenant = profile.tenant
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

            rating_avg = None
            rating_count = 0
            promo_badge = None
            flash_sale_active = False
            try:
                from django_tenants.utils import schema_context as _sc
                from django.db.models import Avg, Count
                with _sc(tenant.schema_name):
                    from menu.models import Rating as _Rating, Promotion as _Promo
                    agg = _Rating.objects.aggregate(avg=Avg("score"), cnt=Count("id"))
                    if agg["cnt"]:
                        rating_avg = round(float(agg["avg"]), 1)
                        rating_count = agg["cnt"]
                    for _p in _Promo.objects.filter(is_active=True).order_by("-discount_value")[:5]:
                        if _is_promo_active_now(_p):
                            if _p.promo_type == "percentage":
                                promo_badge = f"{int(_p.discount_value)}% off"
                            elif _p.promo_type == "fixed":
                                promo_badge = f"-{_p.discount_value} off"
                            else:
                                promo_badge = "Free delivery"
                            break
            except Exception:
                pass

            # Check if this restaurant is opted into any live platform flash sale
            try:
                from .models import PlatformFlashSale, PlatformFlashSaleOptIn
                opted_ids = set(
                    PlatformFlashSaleOptIn.objects.filter(tenant_id=tenant.id).values_list("flash_sale_id", flat=True)
                )
                if opted_ids:
                    for _fs in PlatformFlashSale.objects.filter(id__in=opted_ids, is_active=True):
                        if _fs.is_live():
                            flash_sale_active = True
                            break
            except Exception:
                pass

            if min_rating is not None and (rating_avg is None or rating_avg < min_rating):
                continue

            distance_km = None
            if user_lat is not None and profile.lat and profile.lng:
                distance_km = round(_haversine_km(user_lat, user_lng, profile.lat, profile.lng), 1)

            results.append({
                "slug": tenant.slug,
                "name": tenant.name,
                "tagline": profile.tagline or "",
                "logo_url": profile.logo_url or "",
                "cuisine_type": profile.cuisine_type or "",
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
            })

        if user_lat is not None:
            results.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 9999))
        else:
            results.sort(key=lambda r: (not r["is_open"], r["name"].lower()))

        all_opted = Profile.objects.filter(directory_opt_in=True, is_menu_published=True)
        cities = sorted({p for p in all_opted.exclude(city="").values_list("city", flat=True)})
        cuisines = sorted({p for p in all_opted.exclude(cuisine_type="").values_list("cuisine_type", flat=True)})
        all_tags: set = set()
        for tlist in all_opted.exclude(tags=[]).values_list("tags", flat=True):
            if isinstance(tlist, list):
                all_tags.update(str(t).lower() for t in tlist)

        return Response({
            "restaurants": results[:100],
            "filters": {
                "cities": cities,
                "cuisines": cuisines,
                "tags": sorted(all_tags),
            },
        })


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

        try:
            with _sc(tenant.schema_name):
                from menu.models import (
                    Profile as _Profile,
                    SuperCategory as _SC,
                    Category as _Cat,
                    Dish as _Dish,
                    OptionGroup as _OG,
                )

                profile = _Profile.objects.filter(tenant=tenant).first()
                if not profile or not profile.is_menu_published:
                    return Response({"detail": "Restaurant menu is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

                dishes_qs = (
                    _Dish.objects.filter(is_published=True, category__is_published=True)
                    .select_related("category__super_category")
                    .prefetch_related("option_groups__options")
                    .order_by("position", "name")
                )

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

                    sc_map[sc.id]["categories"][cat.id]["dishes"].append({
                        "id": dish.id,
                        "slug": dish.slug,
                        "name": dish.name,
                        "name_i18n": dish.name_i18n or {},
                        "description": dish.description or "",
                        "description_i18n": dish.description_i18n or {},
                        "price": str(dish.price),
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

        except Exception as exc:
            logger.exception("MarketplaceMenuView error for slug=%s: %s", slug, exc)
            return Response({"detail": "Could not load menu.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        is_open = _compute_is_open_now(profile)
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
            "delivery_minimum_order": str(profile.delivery_minimum_order) if profile.delivery_minimum_order else "0",
            "price_tier": profile.price_tier,
            "tags": profile.tags or [],
            "is_open": is_open,
            "is_menu_temporarily_disabled": bool(getattr(profile, "is_menu_temporarily_disabled", False)),
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

    def post(self, request, *args, **kwargs):
        from decimal import Decimal
        from tenancy.models import Tenant
        from django_tenants.utils import schema_context as _sc
        import secrets as _sec

        restaurant_slug = (request.data.get("restaurant") or "").strip().lower()
        if not restaurant_slug:
            return Response({"detail": "restaurant is required.", "code": "missing_restaurant"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = Tenant.objects.get(slug=restaurant_slug)
        except Tenant.DoesNotExist:
            return Response({"detail": "Restaurant not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

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
        delivery_location_url = (request.data.get("delivery_location_url") or "").strip()[:500]
        use_wallet = bool(request.data.get("use_wallet")) and _linked_customer is not None

        try:
            delivery_lat = float(request.data["delivery_lat"]) if request.data.get("delivery_lat") is not None else None
            delivery_lng = float(request.data["delivery_lng"]) if request.data.get("delivery_lng") is not None else None
        except (ValueError, TypeError):
            delivery_lat = delivery_lng = None

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
                    Profile as _Profile,
                    Promotion as _Promo,
                )
                from django.db import transaction as _dbtx, IntegrityError as _IE

                profile = _Profile.objects.filter(tenant=tenant).first()
                if not profile or not profile.is_menu_published:
                    return Response({"detail": "Restaurant is not available.", "code": "unavailable"}, status=status.HTTP_404_NOT_FOUND)

                if not _compute_is_open_now(profile):
                    return Response(
                        {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                        status=status.HTTP_409_CONFLICT,
                    )

                slugs = []
                for it in items_raw:
                    if not isinstance(it, dict) or not it.get("slug"):
                        return Response({"detail": "Each item must have a slug.", "code": "invalid_items"}, status=status.HTTP_400_BAD_REQUEST)
                    slugs.append(str(it["slug"]))

                dishes_map = {
                    d.slug: d
                    for d in _Dish.objects.filter(
                        slug__in=slugs, is_published=True, is_available=True, category__is_published=True
                    ).select_related("category")
                }
                missing = [s for s in slugs if s not in dishes_map]
                if missing:
                    return Response({"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing}, status=status.HTTP_400_BAD_REQUEST)

                all_option_ids = [int(oid) for it in items_raw for oid in (it.get("option_ids") or []) if str(oid).isdigit()]
                options_map = {o.id: o for o in _DO.objects.filter(id__in=all_option_ids)} if all_option_ids else {}

                order_items_data = []
                food_subtotal = Decimal("0")
                currency = "USD"

                for it in items_raw:
                    dish = dishes_map[it["slug"]]
                    currency = dish.currency or "USD"
                    unit_price = Decimal(str(dish.price))
                    option_snapshots = []
                    for oid in (it.get("option_ids") or []):
                        opt = options_map.get(int(oid)) if str(oid).isdigit() else None
                        if opt:
                            unit_price += Decimal(str(opt.price_delta))
                            option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})
                    qty = max(1, min(99, int(it.get("qty", 1))))
                    subtotal = unit_price * qty
                    food_subtotal += subtotal
                    order_items_data.append({
                        "dish_slug": dish.slug,
                        "dish_name": dish.name,
                        "unit_price": unit_price,
                        "qty": qty,
                        "note": str(it.get("note") or "")[:120],
                        "options": option_snapshots,
                        "subtotal": subtotal,
                    })

                _delivery_fee = Decimal("0")
                if fulfillment_type == "delivery":
                    try:
                        _delivery_fee = Decimal(str(profile.delivery_fee or "0"))
                    except Exception:
                        _delivery_fee = Decimal("0")

                # Best restaurant promo
                _best_promo = None
                _promo_discount = Decimal("0")
                for _p in _Promo.objects.filter(is_active=True).order_by("-discount_value"):
                    if _p.max_uses is not None and _p.use_count >= _p.max_uses:
                        continue
                    if Decimal(str(_p.min_order_amount or "0")) > food_subtotal:
                        continue
                    if not _is_promo_active_now(_p):
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
                commission_amount = (food_subtotal * Decimal("0.10")).quantize(Decimal("0.01"))

                _stock_updates = []
                _pk_to_slug = {}
                for _item_d in order_items_data:
                    _d = dishes_map[_item_d["dish_slug"]]
                    _pk_to_slug[_d.pk] = _d.slug
                    if _d.stock_qty is not None:
                        _stock_updates.append((_d.pk, _item_d["qty"]))

                _wallet_deduction = Decimal("0")
                if use_wallet and _linked_customer:
                    _available = Decimal(str(_linked_customer.wallet_balance or "0"))
                    _wallet_deduction = min(_available, total)
                    if _wallet_deduction <= Decimal("0"):
                        _wallet_deduction = Decimal("0")

                class _OutOfStock(Exception):
                    def __init__(self, slug):
                        self.slug = slug

                if fulfillment_type == "delivery" and _linked_customer:
                    customer_name = _linked_customer.name or customer_name
                    customer_phone = _linked_customer.phone or customer_phone

                try:
                    with _dbtx.atomic():
                        if _stock_updates:
                            _locked = {
                                d.pk: d
                                for d in _Dish.objects.select_for_update().filter(
                                    pk__in=[pk for pk, _ in _stock_updates]
                                )
                            }
                            for _dish_pk, _ordered_qty in _stock_updates:
                                _ld = _locked.get(_dish_pk)
                                if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered_qty:
                                    raise _OutOfStock(_pk_to_slug.get(_dish_pk, ""))
                            for _dish_pk, _ordered_qty in _stock_updates:
                                _ld = _locked.get(_dish_pk)
                                if _ld and _ld.stock_qty is not None:
                                    _new_qty = max(0, _ld.stock_qty - _ordered_qty)
                                    _Dish.objects.filter(pk=_dish_pk).update(
                                        **{"stock_qty": _new_qty, **({"is_available": False} if _new_qty == 0 else {})}
                                    )

                        for _attempt in range(10):
                            _candidate = f"ORD-{_sec.token_hex(3).upper()}"
                            if not _Order.objects.filter(order_number=_candidate).exists():
                                order_number = _candidate
                                break
                        else:
                            return Response({"detail": "Order could not be placed. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

                        order = _Order.objects.create(
                            order_number=order_number,
                            status=_Order.Status.PENDING,
                            customer=_linked_customer,
                            customer_name=customer_name,
                            customer_phone=customer_phone,
                            customer_note=customer_note,
                            fulfillment_type=fulfillment_type,
                            delivery_address=delivery_address,
                            delivery_location_url=delivery_location_url,
                            delivery_lat=delivery_lat,
                            delivery_lng=delivery_lng,
                            total=total,
                            delivery_fee=_delivery_fee,
                            currency=currency,
                            source=_Order.Source.MARKETPLACE,
                            commission_amount=commission_amount,
                            promotion_discount=_promo_discount,
                            applied_promotion_name=_applied_promo_name,
                        )
                        for item_data in order_items_data:
                            _OI.objects.create(order=order, **item_data)

                        # Increment restaurant promo use_count atomically
                        if _best_promo is not None:
                            from django.db.models import F as _F
                            _Promo.objects.filter(pk=_best_promo.pk).update(use_count=_F("use_count") + 1)

                        # Increment platform flash sale redemption_count atomically
                        if _flash_sale_used is not None:
                            from .models import PlatformFlashSale as _PFS2
                            from django.db.models import F as _F2
                            _PFS2.objects.filter(pk=_flash_sale_used.pk).update(redemption_count=_F2("redemption_count") + 1)

                        # Wallet deduction
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
                                )
                                order.wallet_amount_paid = _actual
                                order.save(update_fields=["wallet_amount_paid"])

                except _OutOfStock as _e:
                    return Response(
                        {"detail": "Item sold out.", "code": "items_unavailable", "slugs": [_e.slug]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except _IE:
                    return Response(
                        {"detail": "Order could not be placed due to a conflict. Please try again."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

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
            "currency": order.currency,
            "restaurant_slug": tenant.slug,
            "restaurant_name": tenant.name,
        }, status=status.HTTP_201_CREATED)


class MarketplaceOrderStatusView(APIView):
    """GET /api/marketplace/order/<order_number>/?restaurant=<slug> — poll order status."""

    permission_classes = [AllowAny]
    authentication_classes = []

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

                items = [
                    {
                        "dish_name": item.dish_name,
                        "qty": item.qty,
                        "unit_price": str(item.unit_price),
                        "subtotal": str(item.subtotal),
                        "options": item.options,
                        "note": item.note,
                    }
                    for item in order.items.all()
                ]
        except Exception as exc:
            logger.exception("MarketplaceOrderStatusView error for order=%s tenant=%s: %s", order_number, slug, exc)
            return Response({"detail": "Could not load order.", "code": "server_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "items": items,
            "restaurant_slug": slug,
            "restaurant_name": tenant.name,
        })


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
    """

    permission_classes = [IsAuthenticated]

    def _check_admin(self, request):
        from .models import User
        user = request.user
        if not isinstance(user, User) or not user.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get(self, request, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            sales = list(PlatformFlashSale.objects.all())
            return Response([_serialize_flash_sale(fs) for fs in sales])

    def post(self, request, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
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
        return Response(_serialize_flash_sale(fs), status=status.HTTP_201_CREATED)


class AdminFlashSaleDetailView(APIView):
    """
    GET/PATCH/DELETE /api/admin/flash-sales/<id>/  — platform admin only
    """

    permission_classes = [IsAuthenticated]

    def _check_admin(self, request):
        from .models import User
        user = request.user
        if not isinstance(user, User) or not user.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _get_fs(self, fs_id):
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                return PlatformFlashSale.objects.get(pk=fs_id)
            except PlatformFlashSale.DoesNotExist:
                return None

    def get(self, request, fs_id, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
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
        err = self._check_admin(request)
        if err:
            return err
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

        return Response(_serialize_flash_sale(fs))

    def delete(self, request, fs_id, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
        from .models import PlatformFlashSale
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                PlatformFlashSale.objects.get(pk=fs_id).delete()
            except PlatformFlashSale.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
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

        return Response({"detail": "Opted out.", "opted_in": False})


# ── Phase 4: Delivery Platform ────────────────────────────────────────────────

def _serialize_delivery_job(job, include_driver_position: bool = False) -> dict:
    data = {
        "id": job.id,
        "order_number": job.order_number,
        "tenant_id": job.tenant_id,
        "status": job.status,
        "pickup_address": job.pickup_address,
        "pickup_lat": job.pickup_lat,
        "pickup_lng": job.pickup_lng,
        "delivery_address": job.delivery_address,
        "delivery_lat": job.delivery_lat,
        "delivery_lng": job.delivery_lng,
        "delivery_fee": str(job.delivery_fee),
        "driver_payout": str(job.driver_payout),
        "assigned_at": job.assigned_at.isoformat() if job.assigned_at else None,
        "picked_up_at": job.picked_up_at.isoformat() if job.picked_up_at else None,
        "delivered_at": job.delivered_at.isoformat() if job.delivered_at else None,
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        "created_at": job.created_at.isoformat(),
        "is_terminal": job.is_terminal,
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
        }
        if include_driver_position:
            driver_data["lat"] = job.driver.driver_lat
            driver_data["lng"] = job.driver.driver_lng
            driver_data["is_online"] = job.driver.is_driver_online
            driver_data["position_updated_at"] = (
                job.driver.driver_position_updated_at.isoformat()
                if job.driver.driver_position_updated_at else None
            )
        data["driver"] = driver_data
    return data


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


class DriverRegisterView(APIView):
    """POST /api/driver/register/ — customer signs up as a delivery driver.

    Requires an active customer session. Sets is_driver=True on the Customer.
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

        if not customer.is_driver:
            customer.is_driver = True
            customer.save(update_fields=["is_driver", "updated_at"])

        return Response({
            "is_driver": True,
            "is_driver_online": customer.is_driver_online,
            "message": "Driver account activated.",
        })


class DriverStatusView(APIView):
    """PATCH /api/driver/status/ — toggle driver online/offline.

    Body: { "online": true|false }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def patch(self, request, *args, **kwargs):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        online = bool(request.data.get("online", False))
        customer.is_driver_online = online
        customer.save(update_fields=["is_driver_online", "updated_at"])

        return Response({"is_driver_online": customer.is_driver_online})


class DriverPositionUpdateView(APIView):
    """POST /api/driver/position/ — driver updates their current GPS position.

    Body: { "lat": 48.85, "lng": 2.35 }
    Also accepts optional job_id to update the specific job context.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        from django.utils import timezone as _tz

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            lat = float(request.data["lat"])
            lng = float(request.data["lng"])
        except (KeyError, ValueError, TypeError):
            return Response({"detail": "lat and lng are required."}, status=status.HTTP_400_BAD_REQUEST)

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

        # Pending jobs (no driver yet)
        pending_jobs = list(
            DeliveryJob.objects.filter(
                driver__isnull=True,
                status=DeliveryJob.Status.SEARCHING,
            ).select_related("driver")[:20]
        )

        return Response({
            "active": [_serialize_delivery_job(j) for j in active_jobs],
            "pending": [_serialize_delivery_job(j) for j in pending_jobs],
        })


class DriverJobAcceptView(APIView):
    """POST /api/driver/jobs/<job_id>/accept/ — driver accepts a pending delivery job."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, job_id, *args, **kwargs):
        from django.utils import timezone as _tz
        from django.db import transaction as _tx
        from .models import DeliveryJob

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True, is_driver_online=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver must be online to accept jobs."}, status=status.HTTP_403_FORBIDDEN)

        # Check driver doesn't already have an active job
        if DeliveryJob.objects.filter(
            driver=customer,
            status__in=[DeliveryJob.Status.ASSIGNED, DeliveryJob.Status.AT_RESTAURANT, DeliveryJob.Status.PICKED_UP],
        ).exists():
            return Response({"detail": "Complete your current delivery before accepting a new one."}, status=status.HTTP_409_CONFLICT)

        with _tx.atomic():
            try:
                job = DeliveryJob.objects.select_for_update().get(
                    pk=job_id,
                    status=DeliveryJob.Status.SEARCHING,
                    driver__isnull=True,
                )
            except DeliveryJob.DoesNotExist:
                return Response({"detail": "Job not available."}, status=status.HTTP_404_NOT_FOUND)

            job.driver = customer
            job.status = DeliveryJob.Status.ASSIGNED
            job.assigned_at = _tz.now()
            job.save(update_fields=["driver", "status", "assigned_at"])

        return Response(_serialize_delivery_job(job), status=status.HTTP_200_OK)


class DriverJobStatusUpdateView(APIView):
    """PATCH /api/driver/jobs/<job_id>/status/ — driver advances job status.

    Body: { "status": "at_restaurant" | "picked_up" | "delivered" | "failed" }
    """

    VALID_TRANSITIONS = {
        "assigned": ["at_restaurant", "failed"],
        "at_restaurant": ["picked_up", "failed"],
        "picked_up": ["delivered", "failed"],
    }

    permission_classes = [AllowAny]
    authentication_classes = []

    def patch(self, request, job_id, *args, **kwargs):
        from django.utils import timezone as _tz
        from .models import DeliveryJob

        customer_id = request.session.get("customer_id")
        if not customer_id:
            return Response({"detail": "Customer session required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer = Customer.objects.get(pk=customer_id, is_driver=True)
        except Customer.DoesNotExist:
            return Response({"detail": "Driver account not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            job = DeliveryJob.objects.select_related("driver").get(pk=job_id, driver=customer)
        except DeliveryJob.DoesNotExist:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status", "").strip()
        allowed = self.VALID_TRANSITIONS.get(job.status, [])
        if new_status not in allowed:
            return Response(
                {"detail": f"Cannot transition from '{job.status}' to '{new_status}'.",
                 "allowed": allowed},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = _tz.now()
        job.status = new_status
        update_fields = ["status"]

        if new_status == DeliveryJob.Status.PICKED_UP:
            job.picked_up_at = now
            update_fields.append("picked_up_at")
        elif new_status == DeliveryJob.Status.DELIVERED:
            job.delivered_at = now
            update_fields.append("delivered_at")
            # Go offline after delivery
            customer.is_driver_online = False
            customer.save(update_fields=["is_driver_online", "updated_at"])
        elif new_status == DeliveryJob.Status.FAILED:
            job.failed_at = now
            update_fields.append("failed_at")

        job.save(update_fields=update_fields)

        # Push notification to restaurant when driver arrives at pickup
        if new_status == DeliveryJob.Status.AT_RESTAURANT:
            try:
                import threading as _threading
                from tenancy.models import Tenant as _Tenant
                from menu.push import _push_to_tenant as _push_restaurant
                _tenant = _Tenant.objects.filter(pk=job.tenant_id).first()
                if _tenant:
                    _driver_name = (getattr(job.driver, "name", "") or "Driver").strip()
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

        return Response(_serialize_delivery_job(job))


# ── Order tracking SSE ────────────────────────────────────────────────────────


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

        if not use_sse:
            return Response(_serialize_delivery_job(job, include_driver_position=True))

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
                data = _json.dumps(_serialize_delivery_job(fresh_job, include_driver_position=True))
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


# ── Admin: delivery zone management ───────────────────────────────────────────


class AdminDriverListView(APIView):
    """GET /api/admin/drivers/ — list all registered drivers with job stats (platform admin)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=403)

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

        result = []
        for d in drivers:
            s = stats_map.get(d.id, {})
            avg = s.get("avg_rating")
            result.append({
                "id": d.id,
                "name": d.name or "",
                "phone": d.phone or "",
                "email": d.email or "",
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
                "created_at": d.created_at.isoformat(),
            })
        return Response(result)


class AdminPlatformAnalyticsView(APIView):
    """GET /api/admin/platform-analytics/ — cross-platform aggregate stats (platform admin only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Avg, Count, Q, Sum
        from django.utils import timezone
        from .models import Customer, DeliveryJob, DeliveryZone, PlatformFlashSale, WalletTransaction
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

        # ── Wallet ────────────────────────────────────────────────────────────
        wallet_agg = Customer.objects.aggregate(
            total_balance=Sum("wallet_balance"),
        )
        txn_agg = WalletTransaction.objects.aggregate(
            total=Count("id"),
            total_bonus=Sum("amount", filter=Q(type="bonus")),
            total_payments=Sum("amount", filter=Q(type="payment")),
        )

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
        })


class AdminDeliveryZoneListCreateView(APIView):
    """
    GET  /api/admin/delivery-zones/   — list all zones (platform admin only)
    POST /api/admin/delivery-zones/   — create a zone
    """

    permission_classes = [IsAuthenticated]

    def _check_admin(self, request):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get(self, request, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
        from .models import DeliveryZone
        from django_tenants.utils import schema_context
        with schema_context("public"):
            zones = list(DeliveryZone.objects.all())
        return Response([_serialize_zone(z) for z in zones])

    def post(self, request, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
        from .models import DeliveryZone
        from django_tenants.utils import schema_context

        data = request.data
        name = str(data.get("name") or "").strip()
        city = str(data.get("city") or "").strip()
        polygon = data.get("polygon") or []

        if not name or not city:
            return Response({"detail": "name and city are required."}, status=400)
        if not isinstance(polygon, list) or len(polygon) < 3:
            return Response({"detail": "polygon must be a list of ≥ 3 {lat, lng} points."}, status=400)

        center_lat = data.get("center_lat")
        center_lng = data.get("center_lng")
        approx_radius_km = float(data.get("approx_radius_km", 5.0))

        fee_tiers = data.get("fee_tiers") or []
        if not isinstance(fee_tiers, list):
            fee_tiers = []

        with schema_context("public"):
            zone = DeliveryZone.objects.create(
                name=name,
                city=city,
                polygon=polygon,
                center_lat=float(center_lat) if center_lat is not None else None,
                center_lng=float(center_lng) if center_lng is not None else None,
                approx_radius_km=approx_radius_km,
                is_active=bool(data.get("is_active", True)),
                fee_tiers=fee_tiers,
            )
        return Response(_serialize_zone(zone), status=status.HTTP_201_CREATED)


class AdminDeliveryZoneDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/delivery-zones/<zone_id>/ — platform admin only."""

    permission_classes = [IsAuthenticated]

    def _check_admin(self, request):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _get_zone(self, zone_id):
        from .models import DeliveryZone
        from django_tenants.utils import schema_context
        with schema_context("public"):
            try:
                return DeliveryZone.objects.get(pk=zone_id)
            except DeliveryZone.DoesNotExist:
                return None

    def get(self, request, zone_id, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
        zone = self._get_zone(zone_id)
        if zone is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(_serialize_zone(zone))

    def patch(self, request, zone_id, *args, **kwargs):
        err = self._check_admin(request)
        if err:
            return err
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
                if isinstance(data["polygon"], list) and len(data["polygon"]) >= 3:
                    zone.polygon = data["polygon"]
                    update_fields.append("polygon")
            if "center_lat" in data:
                zone.center_lat = float(data["center_lat"]) if data["center_lat"] is not None else None
                update_fields.append("center_lat")
            if "center_lng" in data:
                zone.center_lng = float(data["center_lng"]) if data["center_lng"] is not None else None
                update_fields.append("center_lng")
            if "approx_radius_km" in data:
                zone.approx_radius_km = float(data["approx_radius_km"])
                update_fields.append("approx_radius_km")
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
        err = self._check_admin(request)
        if err:
            return err
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
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=403)

        from .models import DeliveryJob
        qs = DeliveryJob.objects.select_related("driver", "zone").order_by("-created_at")
        status_filter = request.query_params.get("status")
        tenant_filter = request.query_params.get("tenant_id")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if tenant_filter:
            qs = qs.filter(tenant_id=tenant_filter)

        jobs = list(qs[:100])
        return Response([_serialize_delivery_job(j, include_driver_position=True) for j in jobs])


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
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from .models import User
        u = request.user
        if not isinstance(u, User) or not u.is_platform_admin:
            return Response({"detail": "Platform admin access required."}, status=403)

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
        return Response(_serialize_delivery_job(job), status=status.HTTP_201_CREATED)
