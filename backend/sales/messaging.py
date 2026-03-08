from urllib.parse import quote_plus

from django.core.mail import send_mail


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


def build_admin_url(tenant) -> str:
    domain = primary_domain_for_tenant(tenant)
    if domain.endswith(".localhost") or domain == "localhost":
        return f"http://{domain}:8000/admin/"
    return f"https://{domain}/admin/"


def build_activation_url(tenant, token: str) -> str:
    return f"{build_tenant_frontend_url(tenant)}/activate?token={token}"


def build_activation_message(admin_url: str, activation_url: str, token: str) -> str:
    return (
        "Your restaurant menu admin is ready.\n"
        f"Admin: {admin_url}\n"
        f"Activation: {activation_url}\n"
        f"Activation token: {token}\n"
        "Use this link to set your password and start onboarding."
    )


def send_activation_email(email: str, admin_url: str, activation_url: str, token: str):
    subject = "Your restaurant menu admin"
    body = (
        "Hello,\n\n"
        "Your restaurant menu admin is ready.\n"
        f"Admin URL: {admin_url}\n"
        f"Activation URL: {activation_url}\n"
        f"Activation token: {token}\n\n"
        "Use the activation URL to set your password.\n\n"
        "Thank you."
    )
    send_mail(subject, body, None, [email], fail_silently=True)


def send_activation_whatsapp(phone: str, admin_url: str, activation_url: str, token: str) -> str:
    if not phone:
        return ""
    message = build_activation_message(admin_url, activation_url, token)
    sanitized = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    return f"https://wa.me/{sanitized}?text={quote_plus(message)}"
