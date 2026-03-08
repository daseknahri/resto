from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the primary platform superadmin account."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email/login for the platform admin")
        parser.add_argument("--password", required=True, help="Password for the platform admin")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
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
