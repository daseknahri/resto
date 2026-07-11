"""Customer-principal permission classes (RISK IDENTITY-1).

These pair with `CustomerSessionAuthentication`, which puts the signed-in `Customer` on
`request.user`. They replace the hand-rolled `session.get("customer_id")` + `int(a) == int(b)`
checks that were copy-pasted across ~65 customer endpoints (the source of the order-status
IDOR class of bugs) with a single, tested ownership predicate.
"""
from rest_framework.permissions import BasePermission


def _is_customer_principal(user):
    """True iff `user` is an authenticated Customer principal (not a staff User / Anonymous).

    Duck-typed on the model, not `isinstance`, to avoid importing the model at permission
    definition time (and to stay robust to the public/tenant schema split). A Django `User`
    lacks `wallet_balance`; `AnonymousUser.is_authenticated` is False.
    """
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and user.__class__.__name__ == "Customer"
    )


class IsCustomer(BasePermission):
    """Allow only a signed-in Customer (request.user hydrated by CustomerSessionAuthentication).

    Fails closed for AnonymousUser and for staff Users, so a stale/absent customer session or
    a staff cookie can't reach a customer-only endpoint. DRF renders the denial as 401 (not
    403) because CustomerSessionAuthentication defines `authenticate_header`, matching the old
    hand-rolled "Not authenticated" responses.
    """

    def has_permission(self, request, view):
        return _is_customer_principal(request.user)


class IsOrderOwner(BasePermission):
    """Object-level: the order belongs to the requesting Customer.

    `obj` is a tenant `Order` (or anything exposing `customer_id`). Usable two ways:

    * As a DRF object permission via `view.check_object_permissions(request, order)`.
    * As a plain predicate: `IsOrderOwner().has_object_permission(request, self, order)` —
      used by the order-status / cancel / rating views that must keep their own specific
      coded responses (and, for status, degrade to a non-owner "public" view) rather than
      raise DRF's generic 403. This is the single home for the `customer_id` comparison the
      IDOR-prone views used to each re-implement.

    Fails closed on a missing/​unparseable id on either side.
    """

    def has_permission(self, request, view):
        # Gate object access on a real customer principal; ownership is checked per-object.
        return _is_customer_principal(request.user)

    def has_object_permission(self, request, view, obj):
        if not _is_customer_principal(request.user):
            return False
        order_cid = getattr(obj, "customer_id", None)
        if order_cid is None:
            return False
        try:
            return int(order_cid) == int(request.user.id)
        except (TypeError, ValueError):
            return False
