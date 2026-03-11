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
    send_mail(subject, body, None, [email], fail_silently=True)


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
