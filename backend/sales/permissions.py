from rest_framework.permissions import BasePermission

from accounts.models import User


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False))


class IsTenantEditor(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        tenant = getattr(request, "tenant", None)
        if not user or not user.is_authenticated or tenant is None:
            return False
        if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
            return True
        if not getattr(tenant, "is_active", True):
            return False
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
