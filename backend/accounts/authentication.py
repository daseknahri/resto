"""Customer session authentication (RISK IDENTITY-1).

Staff/owners authenticate through DRF's `SessionAuthentication` (a Django `User` on
`request.user`). Customers, however, are a plain `Customer` model identified only by
`request.session["customer_id"]`, so historically every customer endpoint ran with
`authentication_classes = []` + `permission_classes = [AllowAny]` and re-read the raw
session PK by hand (65 sites), doing its own ownership check — which is exactly how the
order-status IDOR class arose.

`CustomerSessionAuthentication` hydrates that session identity onto `request.user` as the
full `Customer`, so views can use `IsAuthenticated` / `IsCustomer` / `IsOrderOwner` instead
of hand-rolling the check.

CSRF (the critical design point): this is deliberately a plain `BaseAuthentication`, NOT a
subclass of DRF's `SessionAuthentication`. The latter calls `enforce_csrf()` for any
authenticated session request; customer POSTs today run with an empty auth stack and thus
NO CSRF enforcement, so subclassing would newly 403 every customer POST/PATCH/DELETE on
CSRF. Preserving today's behavior avoids that regression (customer CSRF hardening is a
separate, deliberate follow-up). `authenticate_header` is set so an unauthenticated request
to a customer-gated view yields DRF's 401 (matching the old hand-rolled
"Not authenticated" responses) rather than a 403.
"""
from rest_framework.authentication import BaseAuthentication


class CustomerSessionAuthentication(BaseAuthentication):
    """Set request.user to the signed-in Customer from session["customer_id"].

    Returns ``(customer, None)`` for a valid customer session, else ``None`` so DRF leaves
    ``request.user`` as ``AnonymousUser`` and permission checks fail closed. Never
    authenticates a staff ``User`` (that stays on ``SessionAuthentication``); a request
    carries EITHER a ``customer_id`` OR a staff user, never both (enforced at login by
    ``_staff_session_conflict``). The FULL Customer is hydrated (not just an id) so
    driver/rider views can still read ``is_driver`` / ``driver_approved`` off the principal.
    """

    def authenticate(self, request):
        # Session-safe by design: this class is also mounted on AllowAny/optional-auth
        # endpoints (e.g. CustomerOrderStatusView), which previously read the session
        # behind their own `try/except` and degraded to "anonymous" rather than erroring.
        # An unguarded `request.session` would turn that tolerated case into a 500 inside
        # the auth stack, so absent/unusable session state fails closed to anonymous.
        session = getattr(request, "session", None)
        cid = session.get("customer_id") if session is not None else None
        if not cid:
            return None
        from .models import Customer

        customer = Customer.objects.filter(pk=cid).first()
        if customer is None:
            # Stale PK (customer erased) → treat as unauthenticated. Kept side-effect-free
            # (no session mutation in auth); existing readers clean the dangling key.
            return None
        return (customer, None)

    def authenticate_header(self, request):
        # Non-None → DRF returns 401 (not 403) for an unauthenticated request, matching the
        # old hand-rolled "Not authenticated" 401s these views returned.
        return "Session"
