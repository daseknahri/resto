from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from tenancy.models import Domain, Plan, Tenant


class Command(BaseCommand):
    help = "Seed default plans and an optional demo tenant/superadmin"

    def add_arguments(self, parser):
        parser.add_argument("--with-demo", action="store_true", help="Create a demo tenant and superadmin user")
        parser.add_argument("--domain", default="demo.localhost", help="Domain for demo tenant")
        parser.add_argument("--email", default="admin@example.com", help="Email for platform superadmin")
        parser.add_argument("--password", default="admin123", help="Password for platform superadmin")

    def handle(self, *args, **options):
        self.stdout.write("Seeding plans...")
        starter, _ = Plan.objects.update_or_create(
            code="starter",
            defaults={
                "name": "Basic",
                "description": "QR menu + WhatsApp ordering for launch and validation",
                "can_checkout": False,
                "can_whatsapp_order": True,
                "max_languages": 3,
                "is_active": True,
            },
        )
        growth, _ = Plan.objects.update_or_create(
            code="growth",
            defaults={
                "name": "Growth",
                "description": "WhatsApp ordering workflow",
                "can_checkout": False,
                "can_whatsapp_order": True,
                "max_languages": 2,
                "is_active": False,
            },
        )
        pro, _ = Plan.objects.update_or_create(
            code="pro",
            defaults={
                "name": "Pro",
                "description": "Checkout, analytics, and advanced controls",
                "can_checkout": True,
                "can_whatsapp_order": True,
                "max_languages": 4,
                "is_active": False,
            },
        )
        self.stdout.write(self.style.SUCCESS("Plans ensured."))

        if options["with_demo"]:
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=options["email"],
                defaults={
                    "email": options["email"],
                    "role": User.Roles.PLATFORM_SUPERADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if created:
                user.set_password(options["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Superadmin created: {options['email']}"))
            else:
                self.stdout.write("Superadmin already exists; skipping password set.")

            tenant, _ = Tenant.objects.get_or_create(
                slug="demo",
                defaults={
                    "schema_name": "demo",
                    "name": "Demo Restaurant",
                    "plan": starter,
                    "owner": user,
                },
            )
            Domain.objects.get_or_create(
                domain=options["domain"],
                defaults={"tenant": tenant, "is_primary": True},
            )
            self.stdout.write(self.style.SUCCESS("Demo tenant and domain ensured."))

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
