from rest_framework.permissions import BasePermission

from accounts.models import User


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        # is_staff is a Django /admin/ panel flag, not a business-admin role.
        # Gate: authenticated AND (is_superuser OR is_platform_admin).
        # ensure_platform_admin sets role=PLATFORM_SUPERADMIN (which drives the
        # is_platform_admin property) AND is_superuser=True, so legitimately-
        # provisioned admins pass both predicates.
        return bool(user.is_superuser or getattr(user, "is_platform_admin", False))


class IsTenantEditor(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        tenant = getattr(request, "tenant", None)
        if not user or not user.is_authenticated or tenant is None:
            return False
        # OPS-5b: drop is_staff (Django /admin/ flag) — it let a Django staff user
        # with no tenant affiliation edit/suspend ANY tenant. Real platform admins
        # have is_superuser; tenant editors fall through to the role/tenant check.
        if user.is_superuser or getattr(user, "is_platform_admin", False):
            return True
        if not getattr(tenant, "is_active", True):
            return False
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
