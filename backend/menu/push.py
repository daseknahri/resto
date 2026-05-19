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
import threading

logger = logging.getLogger("app.push")

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
        from pywebpush import webpush, WebPushException

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{admin_email}"},
            ttl=120,
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

        if not subs:
            return

        gone_ids = []
        for sub in subs:
            result = _send_one(sub.endpoint, sub.p256dh, sub.auth, title, body, url)
            if result == "gone":
                gone_ids.append(sub.id)

        if gone_ids:
            with schema_context(schema_name):
                PushSubscription.objects.filter(id__in=gone_ids).delete()

    except Exception as exc:
        logger.warning("_push_to_tenant(%s) failed: %s", schema_name, exc)


def push_new_order(schema_name: str, order_number: str, customer_name: str, total: str, currency: str) -> None:
    """
    Fire-and-forget: send a 'New order' push to all subscribed staff for a tenant.
    Spawns a daemon thread so it never blocks the HTTP response.
    """
    title = f"New order #{order_number}"
    name = (customer_name or "Customer").strip()
    body = f"{name} — {total} {currency}"
    threading.Thread(
        target=_push_to_tenant,
        args=(schema_name, title, body, "/owner/orders"),
        daemon=True,
    ).start()
