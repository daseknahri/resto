"""Capability gating for the business_type seam.

Restaurant-only features (tables, dine-in, waiter, kitchen, reservations) are
gated by Profile.capabilities, derived from Profile.business_type. These helpers
are the single server-side enforcement point so behaviour stays consistent across
apps (menu, sales).

NON-BREAKING: every check defaults to True when the tenant/profile/capability is
unknown, so an existing restaurant is never silently restricted.
"""


def tenant_capability_enabled(tenant, key: str) -> bool:
    """Return True if ``tenant``'s profile allows capability ``key``.

    Defaults to True for a missing tenant/profile/key (backward compatible).
    """
    if tenant is None:
        return True
    try:
        from .models import Profile

        profile = Profile.objects.filter(tenant=tenant).first()
    except Exception:
        return True
    if profile is None:
        return True
    try:
        return bool(profile.capabilities.get(key, True))
    except Exception:
        return True
