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
    try:
        from .notifications import record_notification
        record_notification(
            channel="push", event="driver.dispatch",
            status="sent" if sent else "failed",
            recipient=f"{sent}/{len(subs)} drivers", detail=(restaurant_name or ""),
        )
    except Exception:
        pass
    return sent


def push_new_job_to_drivers(restaurant_name=None) -> None:
    """Dispatch nudge to online drivers — enqueued on the Celery worker when a broker is
    configured, else a daemon thread. Never raises, never blocks the caller."""
    from accounts.tasks import enqueue, driver_dispatch
    enqueue(driver_dispatch, restaurant_name)


# Driver "stand down" nudge when an order they're carrying is cancelled. {n} = order number.
_JOB_CANCELLED_MESSAGES = {
    "en": {"title": "Delivery cancelled", "body": "Order {n} was cancelled — you can stop. Thanks!"},
    "fr": {"title": "Livraison annulee", "body": "La commande {n} a ete annulee — vous pouvez arreter. Merci !"},
    "ar": {"title": "أُلغيت عملية التوصيل", "body": "أُلغي الطلب {n} — يمكنك التوقف. شكراً!"},
}


def notify_driver_job_cancelled_sync(driver_id, order_number) -> int:
    """Tell one driver their job's order was cancelled (deep-links to /driver). SYNCHRONOUS."""
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=driver_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=driver_id))
    if not subs:
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _JOB_CANCELLED_MESSAGES:
        loc = "en"
    msg = _JOB_CANCELLED_MESSAGES[loc]
    title = msg["title"]
    body = msg["body"].format(n=order_number)

    gone, sent = [], 0
    for s in subs:
        result = _send_one(s.endpoint, s.p256dh, s.auth, title, body, "/driver")
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    try:
        from .notifications import record_notification
        record_notification(
            channel="push", event="delivery.cancelled",
            status="sent" if sent else "failed",
            recipient=f"driver:{driver_id}", reference=str(order_number),
        )
    except Exception:
        pass
    return sent


# Customer-facing delivery milestone nudges. {r} = restaurant. Deep-link to /orders/<n>.
_MILESTONE_MESSAGES = {
    "assigned": {
        "en": {"title": "A driver is on it", "body": "{r} assigned a driver to your order."},
        "fr": {"title": "Un livreur est en route", "body": "{r} a assigne un livreur a votre commande."},
        "ar": {"title": "تم تعيين سائق", "body": "{r} عيّن سائقاً لطلبك."},
    },
    "out_for_delivery": {
        "en": {"title": "Out for delivery", "body": "Your order from {r} is on the way."},
        "fr": {"title": "En cours de livraison", "body": "Votre commande de {r} est en route."},
        "ar": {"title": "في الطريق إليك", "body": "طلبك من {r} في الطريق."},
    },
    "delivered": {
        "en": {"title": "Delivered", "body": "Your order from {r} has arrived. Enjoy!"},
        "fr": {"title": "Livre", "body": "Votre commande de {r} est arrivee. Bon appetit !"},
        "ar": {"title": "تم التسليم", "body": "وصل طلبك من {r}. بالهناء!"},
    },
    "failed": {
        "en": {"title": "Delivery problem", "body": "There was a problem delivering your {r} order — the restaurant is sorting it out."},
        "fr": {"title": "Probleme de livraison", "body": "Un probleme est survenu avec votre commande {r} — le restaurant s'en occupe."},
        "ar": {"title": "مشكلة في التوصيل", "body": "حدثت مشكلة في توصيل طلبك من {r} — المطعم يعالج الأمر."},
    },
}


def notify_customer_order_milestone_sync(order_number, tenant_id, event) -> int:
    """Push a delivery milestone to the order's customer (assigned / out_for_delivery /
    delivered / failed). Respects ``notify_order_updates``. Cross-schema: resolves the
    customer id inside the tenant schema, then pushes from the public schema. SYNCHRONOUS."""
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from tenancy.models import Tenant
    from .models import Customer, CustomerPushSubscription

    copy = _MILESTONE_MESSAGES.get(event)
    if not copy:
        return 0
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return 0
    restaurant_name = tenant.name or "the restaurant"

    with schema_context(tenant.schema_name):
        from menu.models import Order as _O
        customer_id = (
            _O.objects.filter(order_number=order_number)
            .values_list("customer_id", flat=True)
            .first()
        )
    if not customer_id:
        return 0  # guest order — nobody to push

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        if cust is not None and not getattr(cust, "notify_order_updates", True):
            return 0
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))
    if not subs:
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in copy:
        loc = "en"
    msg = copy[loc]
    title = msg["title"].format(r=restaurant_name)
    body = msg["body"].format(r=restaurant_name)
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
    try:
        from .notifications import record_notification
        record_notification(
            channel="push", event=f"delivery.{event}",
            status="sent" if sent else "failed",
            recipient=f"{sent}/{len(subs)} subs", reference=str(order_number),
        )
    except Exception:
        pass
    return sent


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
    # Respect the customer's opt-out for review reminders.
    if cust is not None and not getattr(cust, "notify_review_prompts", True):
        return 0
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
    try:
        from .notifications import record_notification
        record_notification(
            channel="push", event="review_prompt",
            status="sent" if sent else "failed",
            recipient=f"{sent}/{len(subs)} subs", detail=(restaurant_name or ""),
            reference=str(order_number),
        )
    except Exception:
        pass
    return sent
