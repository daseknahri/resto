from rest_framework import permissions

from accounts.models import User


class IsTenantEditorOrReadOnly(permissions.BasePermission):
    message = "Editing requires tenant owner or staff permissions."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        tenant = getattr(request, "tenant", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
            return True
        if tenant is None:
            return False
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        if user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}:
            return True
        return False
