from rest_framework.permissions import BasePermission

from accounts.models import User


def user_owns_tenant_id(user, tenant_id) -> bool:
    """Single source of truth for the tenant-owner check (RISK AUTHZ-1).

    True iff ``user`` is authenticated AND (superuser / platform-admin, OR the user's own
    ``tenant_id`` equals ``tenant_id`` AND their role is ``TENANT_OWNER``). ``tenant_id`` is a
    plain id (or ``None``). This backs both ``IsTenantOwner`` and the ``_is_tenant_owner`` view
    helpers in ``accounts/views.py`` and ``menu/views.py`` — previously three divergent
    copies — so the owner semantics now live in exactly one place.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant_id is None or getattr(user, "tenant_id", None) != tenant_id:
        return False
    return user.role == User.Roles.TENANT_OWNER


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


class IsTenantOwner(BasePermission):
    """Owner-only tenant permission.

    Mirrors the `_is_tenant_owner` helpers duplicated in accounts/views.py and
    menu/views.py: superuser / platform-admin bypass, else the request's tenant
    must match the user's tenant AND the user's role must be TENANT_OWNER.

    Unlike IsTenantEditor, TENANT_STAFF is NOT included here — this class is
    for owner-exclusive endpoints (revenue, promotions, settings, billing,
    staff management…) where a staff account with a matching tenant must still
    be denied.

    RISK AUTHZ-1 (call-site migration): ``message`` is the 403 body DRF renders when
    ``has_permission`` returns False for an *authenticated* non-owner (an anonymous caller
    still 401s via ``NotAuthenticated`` first, unchanged). It reproduces the text the
    inline ``_is_tenant_owner`` guards returned so the migration is byte-for-byte
    behavior-preserving; ``IsTenantOwnerAccessDenied`` below carries the other legacy text.
    """

    message = "Owner access required."

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return user_owns_tenant_id(getattr(request, "user", None), getattr(tenant, "id", None))

    def has_object_permission(self, request, view, obj):
        return user_owns_tenant_id(getattr(request, "user", None), getattr(obj, "tenant_id", None))


class IsTenantOwnerAccessDenied(IsTenantOwner):
    """Identical owner policy to ``IsTenantOwner``, but preserving the legacy
    ``{"detail": "Access denied."}`` 403 body of the endpoints that historically returned
    that text (RISK AUTHZ-1 exact-body preservation). The two messages are the same denial;
    the distinction is only kept to avoid a user-facing wording change during the migration.
    """

    message = "Access denied."


class IsTenantOwnerForbidden(IsTenantOwner):
    """Same owner policy, preserving the legacy ``{"detail": "Forbidden."}`` 403 body
    (RISK AUTHZ-1 exact-body preservation — e.g. OwnerWaitlistView)."""

    message = "Forbidden."


class IsTenantOwnerStaffForbidden(IsTenantOwner):
    """Same owner policy, preserving the staff endpoints' 403 body — which uniquely carries
    a ``code`` key: ``{"detail": "Owner access required.", "code": "forbidden"}`` (a test
    asserts ``resp.data["code"] == "forbidden"``).

    A ``dict`` ``message`` is rendered VERBATIM as the response body: DRF's
    ``permission_denied`` raises ``PermissionDenied(detail=message)``, and its exception
    handler uses a dict ``detail`` as the response ``data`` unchanged — so this is the one
    variant whose body is more than ``{"detail": <str>}`` (RISK AUTHZ-1 exact-body preservation)."""

    message = {"detail": "Owner access required.", "code": "forbidden"}
