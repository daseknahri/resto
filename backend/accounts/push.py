"""accounts.push — Web Push to platform CUSTOMERS (public schema).

Reuses menu.push._send_one for delivery. Customer push subscriptions live in the public
schema, so we query under schema_context("public") to be correct off the request path —
on a Celery worker or the inline pool thread, whose DB connection may otherwise carry a
tenant search_path.
"""
import logging

logger = logging.getLogger("app.push")

# Minimal locale-aware copy for the charge-approval nudge. {r} = restaurant, {a} = amount.
_MESSAGES = {
    "en": {"title": "{r}: approve charge", "body": "{a} MAD — tap to review.", "restaurant": "A merchant"},
    "fr": {"title": "{r} : approuver le debit", "body": "{a} MAD — touchez pour verifier.", "restaurant": "Un commercant"},
    "ar": {"title": "{r}: الموافقة على الخصم", "body": "{a} درهم — اضغط للمراجعة.", "restaurant": "تاجر"},
}


def _send_charge_request_sync(customer_id, restaurant_name, amount):
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _MESSAGES:
        loc = "en"
    msg = _MESSAGES[loc]
    title = msg["title"].format(r=restaurant_name or msg["restaurant"])
    body = msg["body"].format(a=amount)

    # Durable inbox row mirroring the charge-approval push (a wallet event the customer
    # must see even if the push was missed). Deep-links to the account/charge surface.
    try:
        from .notifications import create_customer_notification
        create_customer_notification(
            customer_id=customer_id, title=title, body=body, url="/account",
            type="charge_request", vertical="wallet",
        )
    except Exception:
        pass

    if not subs:
        return

    gone = []
    for s in subs:
        if _send_one(s.endpoint, s.p256dh, s.auth, title, body, "/account") == "gone":
            gone.append(s.id)
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()


def push_charge_request(customer_id, restaurant_name, amount) -> None:
    """Nudge telling a customer they have a wallet charge to approve.

    Enqueued on the Celery worker when a broker is configured, else run on the bounded
    inline pool (R14b) — NOT a raw unbounded daemon thread. Never raises, never blocks
    the HTTP response."""
    from accounts.tasks import enqueue, charge_request
    enqueue(charge_request, customer_id, restaurant_name, amount)


# Post-order review nudge, sent ~30 min after an order completes. {r} = restaurant.
_REVIEW_MESSAGES = {
    "en": {"title": "How was {r}?", "body": "Tap to rate your order — it only takes a second."},
    "fr": {"title": "Comment etait {r} ?", "body": "Touchez pour noter votre commande — une seconde suffit."},
    "ar": {"title": "كيف كان {r}؟", "body": "اضغط لتقييم طلبك — لن يستغرق سوى لحظة."},
}

# Pre-dispatch reminder, sent ~60 min before a SCHEDULED order's scheduled_for time. {r} = restaurant.
_PREDISPATCH_REMINDER_MESSAGES = {
    "en": {"title": "Your order is coming up!", "body": "Your order from {r} is due soon — it's being prepared now."},
    "fr": {"title": "Votre commande arrive !", "body": "Votre commande chez {r} est prévue bientôt — elle est en cours de préparation."},
    "ar": {"title": "طلبك على وشك الجهوز!", "body": "طلبك من {r} موعده قريب — يتم تحضيره الآن."},
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


# Exclusive-offer nudge to ONE nearest driver (ranked dispatch). {r} = restaurant.
_JOB_OFFER_MESSAGES = {
    "en": {"title": "Delivery offered to you", "body": "A delivery from {r} is yours to grab first — tap to accept."},
    "fr": {"title": "Livraison proposee", "body": "Une livraison de {r} vous est proposee en priorite — touchez pour accepter."},
    "ar": {"title": "عرض توصيل لك", "body": "توصيل من {r} معروض عليك أولاً — اضغط للقبول."},
}


def notify_driver_job_offer_sync(driver_id, restaurant_name=None) -> int:
    """Web-push ONE driver that a delivery is offered to them first (deep-link /driver).
    SYNCHRONOUS; returns the number of pushes delivered."""
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=driver_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=driver_id))
    if not subs:
        return 0
    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _JOB_OFFER_MESSAGES:
        loc = "en"
    msg = _JOB_OFFER_MESSAGES[loc]
    title = msg["title"]
    body = msg["body"].format(r=restaurant_name or "a restaurant")
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
        record_notification(channel="push", event="driver.offer",
                            status="sent" if sent else "failed",
                            recipient=f"driver:{driver_id}", detail=(restaurant_name or ""))
    except Exception:
        pass
    return sent


def push_job_offer_to_driver(driver_id, restaurant_name=None) -> None:
    """Enqueue the exclusive-offer nudge to one driver. Never raises/blocks."""
    from accounts.tasks import enqueue, driver_job_offer
    enqueue(driver_job_offer, driver_id, restaurant_name)


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
        "en": {"title": "Delivery problem", "body": "There was a problem delivering your {r} order — we're on it."},
        "fr": {"title": "Probleme de livraison", "body": "Un probleme est survenu avec votre commande {r} — nous nous en occupons."},
        "ar": {"title": "مشكلة في التوصيل", "body": "حدثت مشكلة في توصيل طلبك من {r} — نحن نعالج الأمر."},
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

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in copy:
        loc = "en"
    msg = copy[loc]
    title = msg["title"].format(r=restaurant_name)
    body = msg["body"].format(r=restaurant_name)
    url = f"/orders/{order_number}"

    # Persist a durable inbox row mirroring this push (the source of truth even if the
    # push is missed/denied). Written BEFORE the no-subscription guard so the inbox is
    # populated even for customers who never enabled push.
    try:
        from .notifications import create_customer_notification
        create_customer_notification(
            customer_id=customer_id, title=title, body=body, url=url,
            type=f"delivery.{event}", vertical="food",
        )
    except Exception:
        pass

    if not subs:
        return 0

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

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _REVIEW_MESSAGES:
        loc = "en"
    msg = _REVIEW_MESSAGES[loc]
    title = msg["title"].format(r=restaurant_name or "your order")
    body = msg["body"]
    url = f"/orders/{order_number}"

    # Durable inbox row mirroring the review-prompt push (written even with no subs).
    try:
        from .notifications import create_customer_notification
        create_customer_notification(
            customer_id=customer_id, title=title, body=body, url=url,
            type="review_prompt", vertical="food",
        )
    except Exception:
        pass

    if not subs:
        return 0

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


def send_predispatch_reminder_sync(customer_id, restaurant_name, order_number) -> int:
    """Send a pre-dispatch reminder ~60 min before a SCHEDULED order's scheduled_for time.

    Respects ``notify_order_updates``. Cross-schema: reads Customer + subscriptions from
    the public schema. Returns the number of pushes delivered (0 = no subs / opted-out).
    Deletes stale (gone) subscriptions as a side effect.
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))

    if cust is not None and not getattr(cust, "notify_order_updates", True):
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in _PREDISPATCH_REMINDER_MESSAGES:
        loc = "en"
    msg = _PREDISPATCH_REMINDER_MESSAGES[loc]
    title = msg["title"]
    body = msg["body"].format(r=restaurant_name or "the restaurant")
    url = f"/orders/{order_number}"

    # Durable inbox row mirroring the predispatch reminder push (written even with no subs).
    try:
        from .notifications import create_customer_notification
        create_customer_notification(
            customer_id=customer_id, title=title, body=body, url=url,
            type="predispatch_reminder", vertical="food",
        )
    except Exception:
        pass

    if not subs:
        return 0

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
            channel="push", event="predispatch_reminder",
            status="sent" if sent else "failed",
            recipient=f"{sent}/{len(subs)} subs", detail=(restaurant_name or ""),
            reference=str(order_number),
        )
    except Exception:
        pass
    return sent


# ── Ride-hailing push helpers ────────────────────────────────────────────────────

# Pre-dispatch reminder sent to the RIDER ~30 min before a SCHEDULED trip. {n} = minutes.
_RIDE_PREDISPATCH_MESSAGES = {
    "ride": {
        "en": {"title": "Your ride is soon", "body": "Your scheduled ride starts in about {n} min — be ready at your pickup point."},
        "fr": {"title": "Votre course arrive", "body": "Votre course demarre dans environ {n} min — soyez pret a votre point de depart."},
        "ar": {"title": "ركوبك قريباً", "body": "رحلتك المجدولة ستبدأ خلال نحو {n} دقيقة — كن جاهزاً عند نقطة التقاطك."},
    },
    "package": {
        "en": {"title": "Pickup coming up", "body": "Your package will be picked up in about {n} min — have it ready."},
        "fr": {"title": "Enlevement proche", "body": "Votre colis sera enleve dans environ {n} min — tenez-le pret."},
        "ar": {"title": "الاستلام قريباً", "body": "سيتم استلام طردك خلال نحو {n} دقيقة — جهّزه للتسليم."},
    },
}


def send_ride_predispatch_reminder_sync(rider_id, kind, minutes_remaining) -> int:
    """Send a pre-dispatch reminder to a rider ~30 min before their SCHEDULED trip.
    SYNCHRONOUS; returns the number of pushes delivered.

    kind              — "ride" or "package"
    minutes_remaining — approximate minutes until scheduled_for (used in body copy)
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    if kind not in _RIDE_PREDISPATCH_MESSAGES:
        kind = "ride"

    with schema_context("public"):
        cust = Customer.objects.filter(pk=rider_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=rider_id))
    if not subs:
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    pool = _RIDE_PREDISPATCH_MESSAGES[kind]
    if loc not in pool:
        loc = "en"
    msg = pool[loc]
    title = msg["title"]
    body = msg["body"].format(n=minutes_remaining)

    gone, sent = [], 0
    for s in subs:
        result = _send_one(s.endpoint, s.p256dh, s.auth, title, body, "/")
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
            channel="push", event=f"ride.predispatch_reminder.{kind}",
            status="sent" if sent else "failed",
            recipient=f"rider:{rider_id}", detail=kind,
        )
    except Exception:
        pass
    return sent


_RIDE_OFFER_MESSAGES = {
    "en": {"title": "New ride request", "body": "A rider needs a car nearby — tap to view."},
    "fr": {"title": "Nouvelle demande de course", "body": "Un passager cherche une voiture — touchez pour voir."},
    "ar": {"title": "طلب ركوب جديد", "body": "راكب يبحث عن سيارة قريبة — اضغط لعرض التفاصيل."},
}

_PACKAGE_OFFER_MESSAGES = {
    "en": {"title": "New package delivery", "body": "A package needs delivering — tap to view."},
    "fr": {"title": "Nouvelle livraison de colis", "body": "Un colis a livrer — touchez pour voir."},
    "ar": {"title": "طلب توصيل طرد", "body": "هناك طرد بحاجة للتوصيل — اضغط لعرض التفاصيل."},
}

_RIDE_ACCEPTED_MESSAGES = {
    "en": {"title": "Driver on the way", "body": "Your driver accepted your ride request."},
    "fr": {"title": "Chauffeur en route", "body": "Votre chauffeur a accepte votre demande de course."},
    "ar": {"title": "السائق في الطريق", "body": "قبل السائق طلب الركوب الخاص بك."},
}


def notify_car_drivers_new_ride_sync(ride_id) -> int:
    """Push a trip offer to eligible online approved drivers. SYNCHRONOUS.

    Dispatch rules by kind:
        ride    — 10 nearest online approved CAR drivers with driver_car_approved=True.
        package — ALL online approved drivers (any vehicle type, no car-doc requirement).
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from tenancy.delivery_pricing import haversine_km, valid_coord
    from .models import Customer, CustomerPushSubscription, RideRequest

    with schema_context("public"):
        try:
            ride = RideRequest.objects.get(pk=ride_id)
        except RideRequest.DoesNotExist:
            return 0
        if ride.status != RideRequest.Status.SEARCHING:
            return 0

        is_package = ride.kind == RideRequest.Kind.PACKAGE

        if is_package:
            # Package: all online approved drivers, any vehicle type
            candidates = list(
                Customer.objects.filter(
                    is_driver=True,
                    driver_approved=True,
                    is_driver_online=True,
                )
            )
        else:
            # Ride: online approved CAR drivers with car docs approved
            candidates = list(
                Customer.objects.filter(
                    is_driver=True,
                    driver_approved=True,
                    is_driver_online=True,
                    driver_vehicle_type=Customer.VEHICLE_TYPE_CAR,
                )
            )

    # Pick up to 10 nearest by haversine (using last known GPS when available).
    pickup_lat = ride.pickup_lat
    pickup_lng = ride.pickup_lng
    if valid_coord(pickup_lat, pickup_lng):
        def _dist(c):
            if valid_coord(c.driver_lat, c.driver_lng):
                return haversine_km(pickup_lat, pickup_lng, c.driver_lat, c.driver_lng)
            return 1e9  # no GPS — sort to end

        candidates.sort(key=_dist)
        candidates = candidates[:10]

    if not candidates:
        return 0

    driver_ids = [c.id for c in candidates]
    with schema_context("public"):
        locales = dict(Customer.objects.filter(id__in=driver_ids).values_list("id", "locale"))
        subs = list(CustomerPushSubscription.objects.filter(customer_id__in=driver_ids))

    if not subs:
        return 0

    offer_copy = _PACKAGE_OFFER_MESSAGES if is_package else _RIDE_OFFER_MESSAGES
    gone, sent = [], 0
    for s in subs:
        loc = locales.get(s.customer_id, "en")
        if loc not in offer_copy:
            loc = "en"
        msg = offer_copy[loc]
        result = _send_one(s.endpoint, s.p256dh, s.auth, msg["title"], msg["body"], "/driver")
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    return sent


def notify_rider_sync(rider_id, event) -> int:
    """Push a ride-status event to the rider. SYNCHRONOUS."""
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    messages = {
        "accepted": _RIDE_ACCEPTED_MESSAGES,
    }
    copy = messages.get(event)
    if not copy:
        return 0

    with schema_context("public"):
        cust = Customer.objects.filter(pk=rider_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=rider_id))

    loc = (getattr(cust, "locale", "") or "en")
    if loc not in copy:
        loc = "en"
    msg = copy[loc]

    # Durable inbox row mirroring the ride-status push (written even with no subs).
    try:
        from .notifications import create_customer_notification
        create_customer_notification(
            customer_id=rider_id, title=msg["title"], body=msg["body"], url="/rides",
            type=f"ride.{event}", vertical="ride",
        )
    except Exception:
        pass

    if not subs:
        return 0

    gone, sent = [], 0
    for s in subs:
        result = _send_one(s.endpoint, s.p256dh, s.auth, msg["title"], msg["body"], "/rides")
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    return sent


def push_new_ride_to_drivers(ride_id) -> None:
    """Enqueue ride dispatch to car drivers. Never raises/blocks."""
    from accounts.tasks import enqueue, ride_dispatch_to_drivers
    enqueue(ride_dispatch_to_drivers, ride_id)


def push_ride_event_to_rider(rider_id, event) -> None:
    """Enqueue ride status push to rider. Never raises/blocks."""
    from accounts.tasks import enqueue, ride_notify_rider
    enqueue(ride_notify_rider, rider_id, event)


# ── Owner campaign push ──────────────────────────────────────────────────────

def vertical_muted_customer_ids(tenant_id) -> set:
    """Customer ids who turned OFF promos for *tenant_id*'s vertical (P2).

    A campaign/win-back from a tenant belongs to that tenant's vertical; a
    customer with a ``CustomerServiceProfile`` for that vertical and
    ``notify_promotions=False`` has muted this whole vertical's promos
    (suppress-if-either — the global flag is still the master switch, filtered
    separately). Returns the set of muted customer ids so the audience builders
    can subtract them. Call from within the public schema. Empty set if the
    vertical can't be resolved. Best-effort: never raises."""
    if tenant_id is None:
        return set()
    try:
        from .verticals import vertical_for_tenant_id
        from .models import CustomerServiceProfile

        vert = vertical_for_tenant_id(tenant_id)
        if not vert:
            return set()
        return set(
            CustomerServiceProfile.objects.filter(
                vertical=vert, notify_promotions=False
            ).values_list("customer_id", flat=True)
        )
    except Exception:
        return set()


def send_campaign_push_sync(customer_id, tenant_name, title, message, url) -> int:
    """Send a promotional campaign push to ONE customer. SYNCHRONOUS.

    Respects ``notify_promotions``. Cross-schema: reads Customer + subscriptions
    from the public schema. Returns number of pushes delivered (0 or 1+).
    Deletes stale (gone) subscriptions as a side effect.
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        if cust is not None and not getattr(cust, "notify_promotions", True):
            return 0
        subs = list(CustomerPushSubscription.objects.filter(customer_id=customer_id))
    if not subs:
        return 0

    gone, sent = [], 0
    for s in subs:
        result = _send_one(s.endpoint, s.p256dh, s.auth, title, message, url)
        if result == "gone":
            gone.append(s.id)
        elif result == "ok":
            sent += 1
    if gone:
        with schema_context("public"):
            CustomerPushSubscription.objects.filter(id__in=gone).delete()
    return sent


def push_campaign_to_customer(customer_id, tenant_name, title, message, url) -> None:
    """Enqueue a campaign push to one customer. Never raises/blocks."""
    from accounts.tasks import enqueue, campaign_push
    enqueue(campaign_push, customer_id, tenant_name, title, message, url)


def send_campaign_email_sync(customer_id, tenant_name, title, message, tenant_id=None) -> int:
    """Send a promotional campaign email to ONE customer. SYNCHRONOUS (B1).

    Respects ``notify_promotions`` and reads the address from the public
    Customer row (so an opt-out between enqueue and send still suppresses).
    Returns the number of emails delivered (0 or 1). Never raises — failures
    are recorded as a NotificationLog row and 0 is returned.
    """
    from django_tenants.utils import schema_context
    from accounts.messaging import send_marketing_email
    from accounts.notifications import record_notification
    from .models import Customer

    with schema_context("public"):
        cust = Customer.objects.filter(pk=customer_id).first()
        if cust is None:
            return 0
        if not getattr(cust, "notify_promotions", True):
            return 0
        if not getattr(cust, "email_verified", False):
            return 0
        # Per-tenant opt-out: if the customer has opted out of this specific tenant's
        # promos (marketplace unsubscribe), suppress even when global flag is still True.
        if tenant_id is not None:
            from .models import CustomerTenantOptOut
            if CustomerTenantOptOut.objects.filter(customer_id=customer_id, tenant_id=tenant_id).exists():
                return 0
        email = (getattr(cust, "email", "") or "").strip()
    if not email:
        return 0

    # Hard bounce / complaint suppression: skip if address is on the global list.
    from .models import CustomerEmailSuppression
    if CustomerEmailSuppression.objects.filter(email=email.lower()).exists():
        return 0

    try:
        sent = send_marketing_email(
            email, title, message, tenant_name,
            customer_id=customer_id, tenant_id=tenant_id,
        )
    except Exception:
        record_notification(
            channel="email", event="campaign", status="failed",
            recipient=email, detail=tenant_name, tenant_id=tenant_id,
        )
        return 0

    record_notification(
        channel="email",
        event="campaign",
        status="sent" if sent else "failed",
        recipient=email,
        detail=tenant_name,
        tenant_id=tenant_id,
    )
    return sent


def email_campaign_to_customer(customer_id, tenant_name, title, message, tenant_id=None) -> None:
    """Enqueue a campaign email to one customer. Never raises/blocks."""
    from accounts.tasks import enqueue, campaign_email
    enqueue(campaign_email, customer_id, tenant_name, title, message, tenant_id)


# ── Driver car-doc expiry push helpers ───────────────────────────────────────

# Warning sent when doc expires in WARN_WINDOW_MIN..WARN_WINDOW_MAX days. {d} = days.
_DOC_EXPIRY_WARNING_MESSAGES = {
    "en": {
        "licence": {
            "title": "Licence expires soon",
            "body": "Your driving licence expires in {d} day(s) — upload a new one to keep accepting rides.",
        },
        "insurance": {
            "title": "Insurance expires soon",
            "body": "Your car insurance expires in {d} day(s) — upload a new one to keep accepting rides.",
        },
    },
    "fr": {
        "licence": {
            "title": "Permis expire bientot",
            "body": "Votre permis de conduire expire dans {d} jour(s) — telechargez-en un nouveau pour continuer.",
        },
        "insurance": {
            "title": "Assurance expire bientot",
            "body": "Votre assurance auto expire dans {d} jour(s) — telechargez-en une nouvelle pour continuer.",
        },
    },
    "ar": {
        "licence": {
            "title": "رخصة القيادة ستنتهي قريباً",
            "body": "رخصة قيادتك ستنتهي خلال {d} يوم — حمّل رخصة جديدة للاستمرار في قبول الركائب.",
        },
        "insurance": {
            "title": "التأمين سينتهي قريباً",
            "body": "تأمين سيارتك سينتهي خلال {d} يوم — حمّل وثيقة جديدة للاستمرار في العمل.",
        },
    },
}

# Sent when doc has already expired and the driver is de-approved.
_DOC_EXPIRED_MESSAGES = {
    "en": {
        "licence": {
            "title": "Licence expired",
            "body": "Your driving licence has expired — your account has been de-approved. Upload a new licence to get re-approved.",
        },
        "insurance": {
            "title": "Insurance expired",
            "body": "Your car insurance has expired — your account has been de-approved. Upload new insurance to get re-approved.",
        },
    },
    "fr": {
        "licence": {
            "title": "Permis expire",
            "body": "Votre permis a expire — votre compte a ete desactive. Telechargez un nouveau permis pour etre reapprouve.",
        },
        "insurance": {
            "title": "Assurance expiree",
            "body": "Votre assurance a expire — votre compte a ete desactive. Telechargez une nouvelle assurance pour etre reapprouve.",
        },
    },
    "ar": {
        "licence": {
            "title": "انتهت صلاحية الرخصة",
            "body": "انتهت صلاحية رخصة قيادتك — تم إيقاف تفعيل حسابك. حمّل رخصة جديدة لإعادة التفعيل.",
        },
        "insurance": {
            "title": "انتهى التأمين",
            "body": "انتهى تأمين سيارتك — تم إيقاف تفعيل حسابك. حمّل وثيقة تأمين جديدة لإعادة التفعيل.",
        },
    },
}


def send_driver_doc_expiry_push_sync(driver_id, doc_kind, days_remaining) -> int:
    """Send a doc-expiry push to one driver. SYNCHRONOUS; returns pushes delivered.

    doc_kind      — "licence" or "insurance"
    days_remaining — days until expiry; <= 0 sends the "already expired" message.
    """
    from django_tenants.utils import schema_context
    from menu.push import _send_one
    from .models import Customer, CustomerPushSubscription

    if doc_kind not in ("licence", "insurance"):
        return 0

    with schema_context("public"):
        cust = Customer.objects.filter(pk=driver_id).first()
        subs = list(CustomerPushSubscription.objects.filter(customer_id=driver_id))
    if not subs:
        return 0

    loc = (getattr(cust, "locale", "") or "en")
    if days_remaining <= 0:
        pool = _DOC_EXPIRED_MESSAGES
        event = f"driver.doc.expired.{doc_kind}"
    else:
        pool = _DOC_EXPIRY_WARNING_MESSAGES
        event = f"driver.doc.expiry_warning.{doc_kind}"

    if loc not in pool:
        loc = "en"
    msg = pool[loc][doc_kind]
    title = msg["title"]
    if days_remaining > 0:
        body = msg["body"].format(d=days_remaining)
    else:
        body = msg["body"]

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
            channel="push", event=event,
            status="sent" if sent else "failed",
            recipient=f"driver:{driver_id}", detail=doc_kind,
        )
    except Exception:
        pass
    return sent
