from rest_framework import permissions

from accounts.models import User


def user_can_edit_tenant(user, tenant):
    """Canonical owner/staff write-authorization rule.

    Single source of truth shared by the DRF permission below and the WebSocket
    OwnerConsumer (realtime/consumers.py), so HTTP and socket authorization can
    never drift out of sync — a drift would be a security hazard (e.g. a customer
    reaching an owner-only channel). Returns True for platform admins, or a user
    that belongs to this tenant with role TENANT_OWNER / TENANT_STAFF.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None:
        return False
    if getattr(user, "tenant_id", None) != tenant.id:
        return False
    return user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}


def user_can_edit_menu(user, tenant):
    """Write-authorization for the MENU builder (dishes, categories, options, tables).

    Owner, or staff with the 'edit menu' permission. Stricter than user_can_edit_tenant
    (which gates live order updates and stays open to all staff) — editing the menu is an
    owner-delegated capability, not a default waiter one.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None:
        return False
    if getattr(user, "tenant_id", None) != tenant.id:
        return False
    if user.role == User.Roles.TENANT_OWNER:
        return True
    return user.role == User.Roles.TENANT_STAFF and bool(getattr(user, "perm_edit_menu", False))


class IsTenantEditorOrReadOnly(permissions.BasePermission):
    message = "Editing the menu requires owner or 'edit menu' staff permission."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return user_can_edit_menu(request.user, getattr(request, "tenant", None))
