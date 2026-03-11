from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Validate email backend configuration and optionally send a test email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="",
            help="Recipient email for test message (required with --send-test).",
        )
        parser.add_argument(
            "--send-test",
            action="store_true",
            help="Send a test email after configuration validation.",
        )
        parser.add_argument(
            "--expect-smtp",
            action="store_true",
            help="Fail if EMAIL_BACKEND is not SMTP backend.",
        )
        parser.add_argument(
            "--expect-no-fail-silently",
            action="store_true",
            help="Fail if EMAIL_FAIL_SILENTLY is True.",
        )

    def _validate_config(self, expect_smtp: bool, expect_no_fail_silently: bool):
        backend = str(getattr(settings, "EMAIL_BACKEND", "")).strip()
        fail_silently = bool(getattr(settings, "EMAIL_FAIL_SILENTLY", True))
        use_tls = bool(getattr(settings, "EMAIL_USE_TLS", False))
        use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
        email_host = str(getattr(settings, "EMAIL_HOST", "")).strip()
        email_port = int(getattr(settings, "EMAIL_PORT", 0))

        if expect_smtp and backend != "django.core.mail.backends.smtp.EmailBackend":
            raise CommandError(
                f"EMAIL_BACKEND must be django.core.mail.backends.smtp.EmailBackend, got: {backend or '<empty>'}"
            )

        if expect_no_fail_silently and fail_silently:
            raise CommandError("EMAIL_FAIL_SILENTLY must be False.")

        if backend == "django.core.mail.backends.smtp.EmailBackend":
            if not email_host:
                raise CommandError("EMAIL_HOST is required for SMTP backend.")
            if email_port <= 0:
                raise CommandError("EMAIL_PORT must be a positive integer for SMTP backend.")
            if use_tls and use_ssl:
                raise CommandError("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True.")

            host_user = str(getattr(settings, "EMAIL_HOST_USER", "")).strip()
            host_password = str(getattr(settings, "EMAIL_HOST_PASSWORD", "")).strip()
            if not host_user or not host_password:
                self.stdout.write(
                    self.style.WARNING(
                        "SMTP credentials are empty (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD). "
                        "This is valid only for trusted relay setups."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Email config OK "
                f"(backend={backend}, host={email_host or '-'}, port={email_port}, "
                f"tls={use_tls}, ssl={use_ssl}, fail_silently={fail_silently})"
            )
        )

    def _send_test_email(self, recipient: str):
        subject = f"[Email Check] {timezone.now().isoformat()}"
        body = (
            "This is a test email from check_email_delivery.\n\n"
            f"Backend: {settings.EMAIL_BACKEND}\n"
            f"Host: {settings.EMAIL_HOST}\n"
            f"Port: {settings.EMAIL_PORT}\n"
            f"TLS: {settings.EMAIL_USE_TLS}\n"
            f"SSL: {settings.EMAIL_USE_SSL}\n"
            f"Fail silently: {getattr(settings, 'EMAIL_FAIL_SILENTLY', True)}\n"
        )

        sent = send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", None),
            [recipient],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )
        if sent < 1:
            raise CommandError("Test email was not sent (send_mail returned 0).")

        self.stdout.write(self.style.SUCCESS(f"Test email sent to: {recipient}"))

    def handle(self, *args, **options):
        expect_smtp = bool(options.get("expect_smtp"))
        expect_no_fail_silently = bool(options.get("expect_no_fail_silently"))
        send_test = bool(options.get("send_test"))
        recipient = str(options.get("to") or "").strip()

        self._validate_config(expect_smtp=expect_smtp, expect_no_fail_silently=expect_no_fail_silently)

        if send_test:
            if not recipient:
                raise CommandError("--to is required when using --send-test.")
            self._send_test_email(recipient=recipient)
