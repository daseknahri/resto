from urllib.parse import quote_plus

import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("app.email")


def primary_domain_for_tenant(tenant) -> str:
    primary = tenant.domains.filter(is_primary=True).first()
    if primary and primary.domain:
        return primary.domain
    return f"{tenant.slug}.localhost"


def build_tenant_frontend_url(tenant) -> str:
    domain = primary_domain_for_tenant(tenant)
    if domain.endswith(".localhost") or domain == "localhost":
        return f"http://{domain}:5173"
    return f"https://{domain}"


def build_workspace_url(tenant) -> str:
    return f"{build_tenant_frontend_url(tenant)}/owner"


def build_onboarding_url(tenant) -> str:
    return f"{build_tenant_frontend_url(tenant)}/owner/onboarding"


def build_signin_url(tenant) -> str:
    return f"{build_tenant_frontend_url(tenant)}/signin"


def build_public_menu_url(tenant) -> str:
    return f"{build_tenant_frontend_url(tenant)}/menu"


def build_admin_url(tenant) -> str:
    domain = primary_domain_for_tenant(tenant)
    if domain.endswith(".localhost") or domain == "localhost":
        return f"http://{domain}:8000/admin/"
    return f"https://{domain}/admin/"


def build_activation_url(tenant, token: str) -> str:
    return f"{build_tenant_frontend_url(tenant)}/activate?token={token}"


def build_reservation_manage_url(tenant, token) -> str:
    """Public self-service link a customer uses to view/cancel their own booking."""
    return f"{build_tenant_frontend_url(tenant)}/r/{token}"


def send_reservation_confirmation_email(tenant, lead, manage_url: str) -> int:
    """Email the customer their booking details + a self-service cancel link. Best-effort."""
    email = (getattr(lead, "email", "") or "").strip()
    if not email:
        return 0
    when = ""
    try:
        if lead.booked_for:
            when = lead.booked_for.strftime("%A %d %B %Y at %H:%M")
    except Exception:  # noqa: BLE001
        when = ""
    name = (getattr(lead, "name", "") or "").strip() or "there"
    tenant_name = getattr(tenant, "name", "") or "the restaurant"
    body = (
        f"Hello {name},\n\n"
        f"We've received your reservation at {tenant_name}.\n"
    )
    if when:
        body += f"When: {when}\n"
    if getattr(lead, "party_size", None):
        body += f"Party size: {lead.party_size}\n"
    body += (
        "\nNeed to cancel or check your booking? Use this link:\n"
        f"{manage_url}\n\n"
        "We look forward to seeing you.\n"
    )
    sent = send_mail(
        f"Your reservation at {tenant_name}",
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("Reservation confirmation email not sent", extra={"target_email": email})
    return sent


def send_reservation_confirmed_email(tenant, lead, manage_url: str) -> int:
    """Email the customer that their reservation has been confirmed by the restaurant. Best-effort."""
    email = (getattr(lead, "email", "") or "").strip()
    if not email:
        return 0
    when = ""
    try:
        if lead.booked_for:
            when = lead.booked_for.strftime("%A %d %B %Y at %H:%M")
    except Exception:  # noqa: BLE001
        when = ""
    name = (getattr(lead, "name", "") or "").strip() or "there"
    tenant_name = getattr(tenant, "name", "") or "the restaurant"
    body = (
        f"Hello {name},\n\n"
        f"Great news — {tenant_name} has confirmed your reservation!\n"
    )
    if when:
        body += f"When: {when}\n"
    if getattr(lead, "party_size", None):
        body += f"Party size: {lead.party_size}\n"
    body += (
        "\nNeed to cancel or manage your booking? Use this link:\n"
        f"{manage_url}\n\n"
        "We look forward to seeing you.\n"
    )
    sent = send_mail(
        f"Your reservation at {tenant_name} is confirmed",
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("Reservation confirmed email not sent", extra={"target_email": email})
    return sent


def build_owner_checklist(workspace_url: str, signin_url: str, activation_url: str, onboarding_url: str, public_menu_url: str):
    return [
        f"Open activation link and set password: {activation_url}",
        f"Sign in if you get logged out: {signin_url}",
        f"Complete onboarding wizard: {onboarding_url}",
        "Add brand info, categories, dishes, and theme.",
        f"Publish and verify live menu: {public_menu_url}",
        f"Owner dashboard after launch: {workspace_url}",
    ]


def build_activation_message(
    workspace_url: str,
    signin_url: str,
    activation_url: str,
    onboarding_url: str,
    public_menu_url: str,
    token: str,
) -> str:
    return (
        "Your restaurant workspace is ready.\n"
        "1. Open activation link and set your password.\n"
        f"Activation: {activation_url}\n"
        "2. Continue to onboarding.\n"
        f"Onboarding: {onboarding_url}\n"
        "3. Sign in later with this URL if needed.\n"
        f"Sign in: {signin_url}\n"
        "4. Publish and verify your live menu.\n"
        f"Live menu: {public_menu_url}\n"
        f"Workspace: {workspace_url}\n"
        f"Activation token: {token}\n"
        "Open the activation link first, complete onboarding, then publish your menu."
    )


def send_activation_email(
    email: str,
    workspace_url: str,
    signin_url: str,
    activation_url: str,
    onboarding_url: str,
    public_menu_url: str,
    token: str,
):
    subject = "Your restaurant workspace is ready"
    body = (
        "Hello,\n\n"
        "Your restaurant workspace is ready.\n"
        f"Activation URL: {activation_url}\n"
        f"Onboarding URL: {onboarding_url}\n"
        f"Sign-in URL: {signin_url}\n"
        f"Workspace URL: {workspace_url}\n"
        f"Live menu URL: {public_menu_url}\n"
        f"Activation token: {token}\n\n"
        "Use the activation URL to set your password, complete onboarding, then publish your menu.\n\n"
        "Thank you."
    )
    sent = send_mail(
        subject,
        body,
        None,
        [email],
        fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
    )
    if sent < 1:
        logger.warning("Activation email not sent", extra={"target_email": email})
    return sent


def send_activation_whatsapp(
    phone: str,
    workspace_url: str,
    signin_url: str,
    activation_url: str,
    onboarding_url: str,
    public_menu_url: str,
    token: str,
) -> str:
    if not phone:
        return ""
    message = build_activation_message(
        workspace_url,
        signin_url,
        activation_url,
        onboarding_url,
        public_menu_url,
        token,
    )
    sanitized = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    return f"https://wa.me/{sanitized}?text={quote_plus(message)}"
