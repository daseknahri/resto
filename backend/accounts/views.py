from django.conf import settings
from django.contrib.auth import login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .messaging import send_password_reset_email
from .throttles import (
    ActivationThrottle,
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


class ActivationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ActivationThrottle]

    def post(self, request):
        serializer = ActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response({"detail": "Account activated", "user": serialize_user_session(user)}, status=status.HTTP_200_OK)


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
