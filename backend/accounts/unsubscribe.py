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
"""

from django.core import signing

# Salt namespaces the signature so an "email-unsubscribe" token can never be
# accepted by any other signing.dumps/loads call (and vice-versa).
_SALT = "email-unsubscribe"

# Tokens shouldn't expire quickly — an unsubscribe link a recipient clicks
# months later must still work — but cap at ~1 year to bound replay value.
MAX_AGE_SECONDS = 365 * 24 * 60 * 60


def make_unsubscribe_token(customer_id) -> str:
    """Return a signed, URL-safe opt-out token for ``customer_id``.

    Timestamped (``signing.dumps`` is a TimestampSigner under the hood) so
    ``load_unsubscribe_token`` can enforce ``MAX_AGE_SECONDS``.
    """
    return signing.dumps(int(customer_id), salt=_SALT)


def load_unsubscribe_token(token):
    """Return the customer id encoded in ``token`` or ``None``.

    Returns ``None`` for a missing/garbage/forged token; tolerates an old (but
    not-yet-expired) timestamp.  Never raises — callers treat ``None`` as
    "invalid token" and must not leak whether the id exists.
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
