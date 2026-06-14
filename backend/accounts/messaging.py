import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("app.email")


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


def send_marketing_email(email: str, subject: str, body: str, tenant_name: str = ""):
    """Send a plain-text promotional/retention email (win-back nudge or owner campaign).

    Mirrors send_otp_email's send_mail style: no explicit from (None →
    DEFAULT_FROM_EMAIL), EMAIL_FAIL_SILENTLY honoured, logs on a 0 send count,
    returns the number of messages delivered (0 or 1).

    A short opt-out line is appended so promotional mail always tells the
    recipient why they got it and how to stop it (notify_promotions is the
    single opt-out for both push and email).
    """
    who = tenant_name or "this restaurant"
    full_body = (
        f"{body}\n\n"
        f"You're receiving this because you opted into promotions from {who}; "
        "manage notifications in your Kepoli account.\n"
    )
    sent = send_mail(
        subject,
        full_body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("Marketing email not sent", extra={"target_email": email})
    return sent
