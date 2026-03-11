from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.messaging import send_password_reset_email
from sales.messaging import send_activation_email


def _normalize_base_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise CommandError("--base-url is required")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CommandError(f"Invalid --base-url: {raw}")
    return value.rstrip("/")


def _normalize_sent_count(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class Command(BaseCommand):
    help = "Send a real activation + password-reset email drill to verify SMTP delivery."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Destination email to receive the drill messages.")
        parser.add_argument(
            "--base-url",
            default="",
            help="Frontend base URL used to build links (for example https://menu.kepoli.com).",
        )
        parser.add_argument(
            "--token",
            default="email-drill-token",
            help="Token placeholder inserted into URLs/messages.",
        )

    def handle(self, *args, **options):
        recipient = str(options["to"]).strip()
        token = str(options["token"]).strip() or "email-drill-token"
        base_url = _normalize_base_url(options.get("base_url") or getattr(settings, "PUBLIC_MENU_BASE_URL", ""))

        workspace_url = f"{base_url}/owner"
        signin_url = f"{base_url}/signin"
        onboarding_url = f"{base_url}/owner/onboarding"
        public_menu_url = f"{base_url}/menu"
        activation_url = f"{base_url}/activate?token={token}"
        reset_url = f"{base_url}/reset-password?token={token}"

        sent_activation = _normalize_sent_count(send_activation_email(
            recipient,
            workspace_url,
            signin_url,
            activation_url,
            onboarding_url,
            public_menu_url,
            token,
        ))
        sent_reset = _normalize_sent_count(send_password_reset_email(recipient, reset_url, token))

        if sent_activation < 1 or sent_reset < 1:
            raise CommandError(
                "Email drill failed: one or more messages were not sent "
                f"(activation={sent_activation}, reset={sent_reset})."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Email drill OK: activation + password reset messages sent to {recipient} "
                f"using base URL {base_url}"
            )
        )
