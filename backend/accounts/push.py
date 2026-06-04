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


# Post-order review nudge, sent ~30 min after an order completes. {r} = restaurant.
_REVIEW_MESSAGES = {
    "en": {"title": "How was {r}?", "body": "Tap to rate your order — it only takes a second."},
    "fr": {"title": "Comment etait {r} ?", "body": "Touchez pour noter votre commande — une seconde suffit."},
    "ar": {"title": "كيف كان {r}؟", "body": "اضغط لتقييم طلبك — لن يستغرق سوى لحظة."},
}


# New-delivery dispatch nudge, sent to online + free drivers. {r} = restaurant.
_NEW_JOB_MESSAGES = {
    "en": {"title": "New delivery available", "body": "A delivery from {r} is ready to claim — tap to view."},
    "fr": {"title": "Nouvelle livraison disponible", "body": "Une livraison de {r} est a prendre — touchez pour voir."},
    "ar": {"title": "توصيل جديد متاح", "body": "هناك توصيل من {r} متاح — اضغط للعرض."},
}


def notify_online_drivers_new_job_sync(restaurant_name=None) -> int:
    """Web-push every ONLINE, FREE driver that a new delivery is up for grabs, deep-linking
    to the /driver dashboard. Free = no active (assigned/at_restaurant/picked_up) job, so we
    don't ping drivers mid-delivery. SYNCHRONOUS; returns the number of pushes delivered.
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription, DeliveryJob

    with schema_context("public"):
        online_ids = list(
            Customer.objects.filter(is_driver=True, is_driver_online=True).values_list("id", flat=True)
        )
        if not online_ids:
            return 0
        busy_ids = set(
            DeliveryJob.objects.filter(
                driver_id__in=online_ids,
                status__in=[
                    DeliveryJob.Status.ASSIGNED,
                    DeliveryJob.Status.AT_RESTAURANT,
                    DeliveryJob.Status.PICKED_UP,
                ],
            ).values_list("driver_id", flat=True)
        )
        free_ids = [i for i in online_ids if i not in busy_ids]
        if not free_ids:
            return 0
        locales = dict(Customer.objects.filter(id__in=free_ids).values_list("id", "locale"))
        subs = list(CustomerPushSubscription.objects.filter(customer_id__in=free_ids))
    if not subs:
        return 0

    gone, sent = [], 0
    for s in subs:
        loc = locales.get(s.customer_id, "en")
        if loc not in _NEW_JOB_MESSAGES:
            loc = "en"
        msg = _NEW_JOB_MESSAGES[loc]
        title = msg["title"]
        body = msg["body"].format(r=restaurant_name or "a restaurant")
        result = _send_one(s.endpoint, s.p256dh, s.auth, title, body, "/driver")
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    return sent


def push_new_job_to_drivers(restaurant_name=None) -> None:
    """Fire-and-forget dispatch nudge to online drivers. Daemon thread; never raises."""
    def _run():
        try:
            notify_online_drivers_new_job_sync(restaurant_name)
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning("push_new_job_to_drivers failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


def send_review_request_sync(customer_id, restaurant_name, order_number) -> int:
    """Send a post-order review nudge to a customer. SYNCHRONOUS — safe to call
    from a management command (the cron process waits for delivery rather than
    racing a daemon thread). Deep-links to the customer's order-status page,
    where the star-rating prompt lives. Returns the number delivered.
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))
    if not subs:
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _REVIEW_MESSAGES:
        loc = "en"
    msg = _REVIEW_MESSAGES[loc]
    title = msg["title"].format(r=restaurant_name or "your order")
    body = msg["body"]
    url = f"/orders/{order_number}"

    gone, sent = [], 0
    for s in subs:
        result = _send_one(s.endpoint, s.p256dh, s.auth, title, body, url)
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    return sent
