import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create or update the primary platform superadmin account. "
        "Password is read from the PLATFORM_ADMIN_PASSWORD environment variable "
        "or prompted interactively when not supplied. "
        "Passing --password on the CLI is supported but deprecated "
        "(visible in /proc, shell history and deploy logs)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email/login for the platform admin")
        parser.add_argument(
            "--password",
            required=False,
            default=None,
            help=(
                "DEPRECATED: prefer PLATFORM_ADMIN_PASSWORD env var. "
                "Password for the platform admin (CLI arg is visible in shell history)."
            ),
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()

        # Password resolution order:
        #   1. PLATFORM_ADMIN_PASSWORD env var (safest — not visible in process listing)
        #   2. --password CLI arg (deprecated — visible in shell history and /proc)
        #   3. Interactive stdin prompt (fallback for local dev)
        password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or options.get("password")
        if not password:
            if not self.stdin.isatty() if hasattr(self.stdin, "isatty") else False:
                raise CommandError(
                    "No password provided. Set PLATFORM_ADMIN_PASSWORD env var, "
                    "pass --password, or run interactively."
                )
            password = getpass.getpass("Platform admin password: ")
        if not password:
            raise CommandError("Password must not be empty.")
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=email,
            defaults={"email": email},
        )
        user.email = email
        user.role = User.Roles.PLATFORM_SUPERADMIN
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Platform admin created: {email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Platform admin updated: {email}"))
