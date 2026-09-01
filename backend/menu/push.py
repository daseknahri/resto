"""
menu.push — Web Push notification helpers for the owner dashboard.

Uses the W3C Web Push protocol with VAPID authentication. No external paid
service is required — the browser's push service (Chrome/Firefox/etc.) handles
delivery directly.

Setup (one-time, per deployment):
    pip install pywebpush
    # Generate a VAPID key pair:
    python -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import base64, json
key = ec.generate_private_key(ec.SECP256R1(), default_backend())
priv_bytes = key.private_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.PEM,
    format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PrivateFormat']).PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=__import__('cryptography.hazmat.primitives.serialization', fromlist=['NoEncryption']).NoEncryption(),
)
pub_bytes = key.public_key().public_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.X962,
    format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PublicFormat']).PublicFormat.UncompressedPoint,
)
print('VAPID_PRIVATE_KEY (PEM):')
print(priv_bytes.decode())
print('VAPID_PUBLIC_KEY (URL-safe base64, paste in frontend):')
print(base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode())
"
    # Add the two values to your .env:
    #   VAPID_PRIVATE_KEY=<PEM string, all on one line with \\n escapes>
    #   VAPID_PUBLIC_KEY=<URL-safe base64 string>
    #   VAPID_ADMIN_EMAIL=you@yourdomain.com
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("app.push")

# Per-send HTTP timeout (seconds). pywebpush forwards this to requests; without it a slow
# or hung push endpoint would block the calling Celery task (hard time limit 120s, worker
# --concurrency 2) with no ceiling. Mirrors the app's other outbound-HTTP timeouts
# (Twilio timeout=10 in menu/sms.py, OSRM timeout=4 in tenancy/routing.py).
_PUSH_TIMEOUT = 5

# Max concurrent sends per fan-out (see _fan_out). Small + bounded so a large audience is
# delivered in parallel without spawning an unbounded number of HTTP-bound threads.
_PUSH_FANOUT_WORKERS = 8

# ─── low-level single-subscription sender ────────────────────────────────────


def _send_one(endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str) -> str:
    """
    Send one Web Push message.

    Returns:
      "ok"    — delivered
      "gone"  — subscription expired (caller should delete it)
      "error" — transient failure (keep subscription, retry later)
    """
    from django.conf import settings

    private_key = (settings.VAPID_PRIVATE_KEY or "").strip()
    public_key = (settings.VAPID_PUBLIC_KEY or "").strip()
    admin_email = (settings.VAPID_ADMIN_EMAIL or "admin@example.com").strip()

    if not private_key or not public_key:
        logger.debug("VAPID keys not configured — skipping Web Push")
        return "error"

    try:
        from pywebpush import webpush

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{admin_email}"},
            ttl=120,
            timeout=_PUSH_TIMEOUT,
        )
        return "ok"
    except Exception as exc:
        # Detect expired subscriptions (HTTP 410 Gone)
        status_code = None
        try:
            status_code = exc.response.status_code  # type: ignore[attr-defined]
        except Exception:
            pass
        if status_code == 410:
            return "gone"
        logger.warning("Web Push failed for %.60s: %s", endpoint, exc)
        return "error"


# ─── bounded-concurrency fan-out ─────────────────────────────────────────────
# A push fan-out to many subscriptions is one blocking HTTP call per recipient. Done
# strictly sequentially, even with the per-send timeout above, a large audience (e.g.
# every online driver on a new job) still costs the SUM of the sends. _fan_out spreads
# the sends across a SMALL bounded thread pool: wall-clock cost drops toward a single
# send, while the worker cap keeps a mealtime burst from fanning out unboundedly
# (mirrors accounts.tasks._inline_executor).
#
# Thread-safety contract: send_fn(sub) does HTTP ONLY (via _send_one) and MUST NOT touch
# the ORM — Django opens a fresh DB connection per thread, and concurrent cursors on one
# connection are unsafe. All DB work stays on the CALLER's thread: it materialises `subs`
# before calling _fan_out and bulk-deletes the returned expired ("gone") ids AFTER
# _fan_out returns, so no ORM ever runs off the main thread.


def _fan_out(subs, send_fn):
    """Deliver a push to every subscription in ``subs`` concurrently, preserving the
    sequential loop's exact semantics.

    ``send_fn(sub)`` performs the send and returns ``_send_one``'s status string
    ("ok" | "gone" | "error"); it may compute per-subscription title/body but must do
    NO database access (see the thread-safety contract above).

    Returns ``(sent, gone_ids)`` — the count delivered ("ok") and the ids of expired
    ("gone") subscriptions for the caller to bulk-delete. Tallying happens on the calling
    thread from the collected results, so the counts are deterministic regardless of send
    order.
    """
    if not subs:
        return 0, []
    workers = min(_PUSH_FANOUT_WORKERS, len(subs))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="push-fanout") as ex:
        results = list(ex.map(send_fn, subs))
    sent = 0
    gone_ids = []
    for sub, result in zip(subs, results):
        if result == "gone":
            gone_ids.append(sub.id)
        elif result == "ok":
            sent += 1
    return sent, gone_ids


# ─── tenant-level batch sender ────────────────────────────────────────────────


def _push_to_tenant(schema_name: str, title: str, body: str, url: str) -> None:
    """
    Send a push notification to all registered subscriptions for a tenant.
    Runs in a daemon thread — must not raise.
    Expired subscriptions (HTTP 410) are removed automatically.
    """
    try:
        from django_tenants.utils import schema_context
        from .models import PushSubscription

        with schema_context(schema_name):
            subs = list(PushSubscription.objects.all())

        from accounts.notifications import record_notification

        if not subs:
            record_notification(
                channel="push", event="push", status="skipped",
                recipient="0 subs", detail=title, schema_name=schema_name,
            )
            return

        gone_ids = []
        ok = 0
        for sub in subs:
            result = _send_one(sub.endpoint, sub.p256dh, sub.auth, title, body, url)
            if result == "ok":
                ok += 1
            elif result == "gone":
                gone_ids.append(sub.id)

        if gone_ids:
            with schema_context(schema_name):
                PushSubscription.objects.filter(id__in=gone_ids).delete()

        record_notification(
            channel="push", event="push",
            status="sent" if ok else "failed",
            recipient=f"{ok}/{len(subs)} subs", detail=title, schema_name=schema_name,
        )

    except Exception as exc:
        logger.warning("_push_to_tenant(%s) failed: %s", schema_name, exc)


def push_new_order(schema_name: str, order_number: str, customer_name: str, total: str, currency: str) -> None:
    """
    Send a 'New order' push to all subscribed staff for a tenant. Enqueued on the Celery
    worker when a broker is configured; otherwise runs in a daemon thread (never blocks
    the HTTP response either way).
    """
    title = f"New order #{order_number}"
    name = (customer_name or "Customer").strip()
    body = f"{name} — {total} {currency}"
    from accounts.tasks import enqueue, web_push_tenant
    enqueue(web_push_tenant, schema_name, title, body, "/owner/orders")


def push_sla_escalation(schema_name: str, order_number: str, waited_minutes: int) -> None:
    """
    Send an SLA-escalation push to all subscribed owner/manager devices for a tenant
    when an order has been left PENDING (unconfirmed) longer than the configured SLA.

    Deep-links to OwnerOrders filtered to this order number (?q=…) so a single tap
    lands the owner on the order that needs confirming. Enqueued like push_new_order
    (Celery when a broker is configured, else a bounded inline thread) so it never
    blocks the sweep.
    """
    title = f"Order #{order_number} still waiting"
    body = f"Order #{order_number} has been waiting {waited_minutes} min — confirm it"
    url = f"/owner/orders?q={order_number}"
    from accounts.tasks import enqueue, web_push_tenant
    enqueue(web_push_tenant, schema_name, title, body, url)
