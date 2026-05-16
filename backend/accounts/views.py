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


def _send_otp_whatsapp(phone: str, code: str) -> bool:
    """Send OTP via Meta WhatsApp Business Cloud API.

    Returns True on success, False if not configured or on error.
    The phone number must be in E.164 format (e.g. +212612345678).
    """
    try:
        import json
        import urllib.request as _urlreq

        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        template_name = getattr(settings, "WHATSAPP_OTP_TEMPLATE_NAME", "otp_verification")
        if not access_token or not phone_number_id:
            return False

        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": code}],
                    }
                ],
            },
        }
        data = json.dumps(payload).encode()
        req = _urlreq.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Content-Type", "application/json")
        with _urlreq.urlopen(req, timeout=10):
            pass
        return True
    except Exception:  # noqa: BLE001
        return False


def _send_otp(phone: str, code: str) -> None:
    """Deliver OTP to customer's phone via WhatsApp Business Cloud API.

    Falls back to logging in DEBUG mode (so developers can test without credentials).
    """
    if getattr(settings, "DEBUG", False):
        logger.info("Customer OTP for %s: %s", phone, code)
        return

    sent = _send_otp_whatsapp(phone, code)
    if not sent:
        # WhatsApp not configured — log so the operator knows delivery is missing
        logger.warning(
            "OTP delivery failed: WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID not set. "
            "Phone ending ...%s did not receive a code.",
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
