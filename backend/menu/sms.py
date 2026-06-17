"""
SMS notification helpers — uses Twilio REST API directly via `requests`.
No extra pip dependency; gracefully no-ops when credentials are absent.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class SmsProviderError(RuntimeError):
    """Raised by send_order_ready_sms on transient Twilio / network failures.

    The Celery task (accounts.tasks.sms_order_ready) has autoretry_for=(Exception,)
    so it will retry up to 3 times with exponential backoff when this is raised.
    Permanent failures (no credentials, invalid phone) return False without raising
    so those are NOT retried.
    """

_TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def _credentials() -> tuple[str, str, str] | None:
    """Return (account_sid, auth_token, from_number) or None if not configured."""
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_num = (os.environ.get("TWILIO_FROM_NUMBER") or "").strip()
    if sid and token and from_num:
        return sid, token, from_num
    return None


def _normalize_phone(phone: str) -> str:
    """Strip spaces/dashes; ensure leading +. Returns empty string on failure."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
    if not digits:
        return ""
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits if len(digits) >= 8 else ""


def send_order_ready_sms(
    phone: str,
    tenant_name: str,
    order_number: str | int,
    tenant_id=None,
) -> bool:
    """Send an "order ready" SMS to *phone*.

    Returns True on success.
    Returns False (does NOT raise) for permanent failures: missing credentials,
    or invalid phone number — retrying cannot fix these.
    Raises SmsProviderError for transient Twilio / network failures — the Celery
    task wrapper retries these automatically via autoretry_for=(Exception,).
    """
    from accounts.notifications import record_notification

    creds = _credentials()
    if creds is None:
        logger.debug("SMS skipped: Twilio credentials not configured.")
        record_notification(channel="sms", event="order.ready", status="skipped",
                            detail=tenant_name, reference=str(order_number), error="no credentials", tenant_id=tenant_id)
        return False

    to_phone = _normalize_phone(phone)
    if not to_phone:
        logger.warning("SMS skipped: invalid phone number %r.", phone)
        record_notification(channel="sms", event="order.ready", status="skipped",
                            detail=tenant_name, reference=str(order_number), error="invalid phone", tenant_id=tenant_id)
        return False

    sid, token, from_num = creds
    body = f"Hi! Your order #{order_number} at {tenant_name} is ready. Come pick it up!"

    try:
        import requests  # noqa: PLC0415 — import inside function to keep module lightweight

        resp = requests.post(
            _TWILIO_API.format(sid=sid),
            auth=(sid, token),
            data={"To": to_phone, "From": from_num, "Body": body},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info(
                "SMS sent: order #%s to %s via Twilio (status %s).",
                order_number,
                to_phone,
                resp.status_code,
            )
            record_notification(channel="sms", event="order.ready", status="sent",
                                recipient=to_phone, detail=tenant_name, reference=str(order_number), tenant_id=tenant_id)
            return True
        else:
            logger.warning(
                "SMS failed: Twilio returned %s — %s",
                resp.status_code,
                resp.text[:200],
            )
            record_notification(channel="sms", event="order.ready", status="failed",
                                recipient=to_phone, detail=tenant_name, reference=str(order_number),
                                error=f"twilio {resp.status_code}", tenant_id=tenant_id)
            raise SmsProviderError(f"Twilio returned {resp.status_code} for order #{order_number}")
    except SmsProviderError:
        raise  # propagate so the Celery task retries
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMS failed: %s", exc)
        record_notification(channel="sms", event="order.ready", status="failed",
                            recipient=to_phone, detail=tenant_name, reference=str(order_number), error=str(exc), tenant_id=tenant_id)
        raise SmsProviderError(f"SMS network/provider error for order #{order_number}") from exc
