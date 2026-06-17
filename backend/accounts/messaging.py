import logging

from django.conf import settings
from django.core.mail import EmailMessage, send_mail

logger = logging.getLogger("app.email")


def _brand_https_base() -> str:
    """Server-authoritative ``https://host`` for links in CRON-sent mail.

    Marketing mail is sent from a scheduled job — there is NO request, so the
    unsubscribe host must come from a configured, server-authoritative setting,
    never request.get_host() (which honours the spoofable Host header).  Mirrors
    accounts.views._canonical_brand_host: BRAND_DOMAIN → PUBLIC_MENU_BASE_URL →
    TENANT_DOMAIN_SUFFIX → localhost.
    """
    from urllib.parse import urlparse as _urlparse

    brand = (getattr(settings, "BRAND_DOMAIN", "") or "").strip()
    host = ""
    if brand:
        host = brand.split("://")[-1].split("/")[0].split(":")[0]
    if not host:
        pub = (getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "").strip()
        if pub:
            host = _urlparse(pub if "://" in pub else f"https://{pub}").hostname or ""
    if not host:
        host = (getattr(settings, "TENANT_DOMAIN_SUFFIX", "") or "").strip()
    if not host:
        host = "localhost"
    return f"https://{host}"


def send_password_reset_email(email: str, reset_url: str, token: str):
    subject = "Reset your Kepoli account password"
    body = (
        "Hello,\n\n"
        "We received a request to reset your password.\n"
        f"Reset URL: {reset_url}\n"
        f"Reset token: {token}\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    sent = send_mail(
        subject,
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("Password reset email not sent", extra={"target_email": email})
    return sent


def send_otp_email(email: str, code: str):
    subject = "Your verification code"
    body = (
        "Hello,\n\n"
        f"Your one-time verification code is: {code}\n\n"
        "This code expires in 5 minutes.\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    sent = send_mail(
        subject,
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("OTP email not sent", extra={"target_email": email})
    return sent


def send_marketing_email(
    email: str,
    subject: str,
    body: str,
    tenant_name: str = "",
    customer_id=None,
    tenant_id=None,
):
    """Send a plain-text promotional/retention email (win-back nudge or owner campaign).

    EMAIL_FAIL_SILENTLY honoured, logs on a 0 send count, returns the number of
    messages delivered (0 or 1) — same contract as before.

    B1-followup (deliverability + CAN-SPAM/Gmail/Yahoo bulk-sender compliance):
    promotional mail must carry a working ONE-CLICK unsubscribe.  We mint a
    signed per-recipient token from ``customer_id`` and attach:

      * ``List-Unsubscribe`` — both an https POST endpoint and a mailto fallback
      * ``List-Unsubscribe-Post: List-Unsubscribe=One-Click`` (RFC 8058)
      * a visible unsubscribe line in the body with the same https URL.

    The unsubscribe host is taken from a server-authoritative setting (these are
    sent from a CRON — there is no request), never request.get_host().  When
    ``customer_id`` is omitted the headers/link are skipped (the message still
    keeps the "manage in your Kepoli account" opt-out line); callers should
    always pass it.
    """
    who = tenant_name or "this restaurant"

    unsubscribe_url = ""
    if customer_id is not None:
        if tenant_id is not None:
            from .unsubscribe import make_tenant_unsubscribe_token
            token = make_tenant_unsubscribe_token(customer_id, tenant_id)
        else:
            from .unsubscribe import make_unsubscribe_token
            token = make_unsubscribe_token(customer_id)
        unsubscribe_url = f"{_brand_https_base()}/api/unsubscribe/{token}/"

    body_lines = [
        body,
        "",
        f"You're receiving this because you opted into promotions from {who}; "
        "manage notifications in your Kepoli account.",
    ]
    if unsubscribe_url:
        body_lines.append(f"Unsubscribe from promotional emails: {unsubscribe_url}")
    full_body = "\n".join(body_lines) + "\n"

    headers = {}
    if unsubscribe_url:
        support = (
            getattr(settings, "SUPPORT_EMAIL", "")
            or getattr(settings, "DEFAULT_FROM_EMAIL", "")
            or "support@kepoli.app"
        )
        headers["List-Unsubscribe"] = (
            f"<{unsubscribe_url}>, <mailto:{support}?subject=unsubscribe>"
        )
        # RFC 8058: lets the mailbox provider's UI unsubscribe with a single POST.
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg = EmailMessage(
        subject=subject,
        body=full_body,
        from_email=None,  # → DEFAULT_FROM_EMAIL
        to=[email],
        headers=headers,
    )
    sent = msg.send(fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True))
    if sent < 1:
        logger.warning("Marketing email not sent", extra={"target_email": email})
    return sent


def send_renewal_reminder_email(
    email: str,
    tenant_name: str,
    grace_days: int,
    subscription_end_date: str | None = None,
) -> int:
    """Pre-lapse renewal reminder to the restaurant owner.

    Sent by enforce_subscriptions when payment_overdue_since is first set.
    grace_days is the grace window remaining before suspension.
    """
    brand_base = _brand_https_base()
    end_note = (
        f"\nYour subscription ended on: {subscription_end_date}\n"
        if subscription_end_date else ""
    )
    subject = f"Action required: renew your {tenant_name} subscription"
    body = (
        f"Hello,\n\n"
        f"Your Kepoli subscription for {tenant_name} has lapsed.{end_note}\n"
        f"You have {grace_days} day(s) remaining before your account is suspended.\n\n"
        f"To renew your subscription, please contact support or log in to your dashboard:\n"
        f"{brand_base}/admin\n\n"
        "If you have already renewed, please disregard this message.\n"
    )
    sent = send_mail(
        subject,
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning(
            "Renewal reminder email not sent",
            extra={"target_email": email, "tenant_name": tenant_name},
        )
    return sent
