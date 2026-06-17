"""B1-followup: signed one-click email-unsubscribe tokens (no DB field).

Gmail/Yahoo bulk-sender rules + CAN-SPAM require promotional mail to carry a
working one-click unsubscribe (RFC 8058: ``List-Unsubscribe`` +
``List-Unsubscribe-Post``).  Rather than store a per-recipient opt-out token on
the Customer row, we mint a tamper-proof token on the fly with
``django.core.signing`` over the customer id.  The signature is keyed by
``SECRET_KEY`` so the link cannot be forged, and a public throttle blunts
sequential scanning.

These links are emailed from a CRON (no request) and may sit in an inbox for a
long time, so the token is allowed a generous max age (1 year) — long enough
that real unsubscribe clicks never silently fail, short enough to bound replay.

Per-tenant opt-out (marketplace B1-followup):
    ``make_tenant_unsubscribe_token(customer_id, tenant_id)`` encodes both IDs
    under a separate salt so existing global tokens are not affected.  The view
    tries the per-tenant format first; an old global token still opts the customer
    out globally (backwards-compatible).
"""

from django.core import signing

# Salts namespace tokens so they cannot be accepted by unrelated signing calls.
_SALT = "email-unsubscribe"           # legacy global opt-out
_TENANT_SALT = "email-tenant-unsub"   # per-tenant opt-out

# Tokens shouldn't expire quickly — an unsubscribe link a recipient clicks
# months later must still work — but cap at ~1 year to bound replay value.
MAX_AGE_SECONDS = 365 * 24 * 60 * 60


def make_unsubscribe_token(customer_id) -> str:
    """Return a signed, URL-safe GLOBAL opt-out token for ``customer_id``."""
    return signing.dumps(int(customer_id), salt=_SALT)


def make_tenant_unsubscribe_token(customer_id, tenant_id) -> str:
    """Return a signed, URL-safe PER-TENANT opt-out token."""
    return signing.dumps({"c": int(customer_id), "t": int(tenant_id)}, salt=_TENANT_SALT)


def load_unsubscribe_token(token):
    """Return the customer id for a GLOBAL opt-out token, or ``None``.

    Returns ``None`` for a missing/garbage/forged/per-tenant token; tolerates
    an old (but not-yet-expired) timestamp.  Never raises.
    """
    if not token:
        return None
    try:
        value = signing.loads(token, salt=_SALT, max_age=MAX_AGE_SECONDS)
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_tenant_unsubscribe_token(token):
    """Return ``(customer_id, tenant_id)`` for a per-tenant token, or ``None``.

    Returns ``None`` for a missing/garbage/forged/global token.  Never raises.
    """
    if not token:
        return None
    try:
        value = signing.loads(token, salt=_TENANT_SALT, max_age=MAX_AGE_SECONDS)
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    try:
        return int(value["c"]), int(value["t"])
    except (KeyError, TypeError, ValueError):
        return None
