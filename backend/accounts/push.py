"""accounts.push — Web Push to platform CUSTOMERS (public schema).

Reuses menu.push._send_one for delivery. Customer push subscriptions live in the public
schema, so we query under schema_context("public") to be correct inside a daemon thread
(whose DB connection may otherwise carry a tenant search_path).
"""
import logging
import threading

logger = logging.getLogger("app.push")

# Minimal locale-aware copy for the charge-approval nudge. {r} = restaurant, {a} = amount.
_MESSAGES = {
    "en": {"title": "{r}: approve charge", "body": "{a} MAD — tap to review.", "restaurant": "A restaurant"},
    "fr": {"title": "{r} : approuver le debit", "body": "{a} MAD — touchez pour verifier.", "restaurant": "Un restaurant"},
    "ar": {"title": "{r}: الموافقة على الخصم", "body": "{a} درهم — اضغط للمراجعة.", "restaurant": "مطعم"},
}


def _send_charge_request_sync(customer_id, restaurant_name, amount):
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))
    if not subs:
        return

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _MESSAGES:
        loc = "en"
    msg = _MESSAGES[loc]
    title = msg["title"].format(r=restaurant_name or msg["restaurant"])
    body = msg["body"].format(a=amount)

    gone = []
    for s in subs:
        if _send_one(s.endpoint, s.p256dh, s.auth, title, body, "/account") == "gone":
            gone.append(s.id)
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()


def push_charge_request(customer_id, restaurant_name, amount) -> None:
    """Fire-and-forget nudge telling a customer they have a wallet charge to approve.

    Spawns a daemon thread so it never blocks the HTTP response; never raises.
    """
    def _run():
        try:
            _send_charge_request_sync(customer_id, restaurant_name, amount)
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning("push_charge_request(%s) failed: %s", customer_id, exc)

    threading.Thread(target=_run, daemon=True).start()
