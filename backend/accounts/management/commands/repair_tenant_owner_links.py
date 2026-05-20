"""
Management command: repair_tenant_owner_links

Fixes tenant_owner (and tenant_staff) users whose tenant FK was set to NULL
by an on_delete=SET_NULL cascade (e.g. tenant was deleted and recreated with
a new primary key).

Usage:
    python manage.py repair_tenant_owner_links
    python manage.py repair_tenant_owner_links --dry-run
    python manage.py repair_tenant_owner_links --schema daseknahri
    python manage.py repair_tenant_owner_links --email owner@example.com
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Re-link tenant users whose tenant FK was NULLed by a cascade delete."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making any changes.",
        )
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Only repair users for the tenant with this schema_name.",
        )
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Only repair the user with this email address.",
        )

    def handle(self, *args, **options):
        from accounts.models import User
        from tenancy.models import Tenant

        dry_run = options["dry_run"]
        schema_filter = options["schema"]
        email_filter = options["email"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved."))

        # ── 1. Find orphaned users (tenant FK is NULL but role is tenant) ────
        orphan_qs = User.objects.filter(
            tenant__isnull=True,
            role__in=[User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF],
        )
        if email_filter:
            orphan_qs = orphan_qs.filter(email__iexact=email_filter)

        orphans = list(orphan_qs.select_related())
        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphaned tenant users found. Nothing to do."))
            return

        self.stdout.write(f"Found {len(orphans)} orphaned tenant user(s):")
        for u in orphans:
            self.stdout.write(f"  • id={u.id}  email={u.email}  role={u.role}")

        # ── 2. Resolve tenants ───────────────────────────────────────────────
        tenant_qs = Tenant.objects.all()
        if schema_filter:
            tenant_qs = tenant_qs.filter(schema_name=schema_filter)
        tenants = list(tenant_qs)

        if not tenants:
            raise CommandError("No tenants found. Check --schema value.")

        if len(tenants) == 1:
            # Unambiguous: single tenant on this installation
            target_tenant = tenants[0]
            self.stdout.write(
                f"\nSingle tenant found: id={target_tenant.id}  "
                f"schema={target_tenant.schema_name}  name={target_tenant.name}"
            )
            self._apply(orphans, target_tenant, dry_run)
        else:
            # Multiple tenants: only process if --schema was given
            if not schema_filter:
                self.stdout.write(
                    self.style.ERROR(
                        "\nMultiple tenants found. Use --schema <schema_name> to specify "
                        "which tenant to re-link the orphaned users to."
                    )
                )
                self.stdout.write("Available tenants:")
                for t in tenants:
                    self.stdout.write(f"  id={t.id}  schema={t.schema_name}  name={t.name}")
                return
            target_tenant = tenants[0]
            self._apply(orphans, target_tenant, dry_run)

        if not dry_run:
            self.stdout.write(self.style.SUCCESS("\nDone. Users have been re-linked."))
        else:
            self.stdout.write(self.style.WARNING("\nDry run complete. Re-run without --dry-run to apply."))

    def _apply(self, orphans, tenant, dry_run):
        from accounts.models import User

        ids = [u.id for u in orphans]
        self.stdout.write(
            f"\n{'Would link' if dry_run else 'Linking'} {len(ids)} user(s) "
            f"→ tenant id={tenant.id} (schema={tenant.schema_name})"
        )
        if not dry_run:
            updated = User.objects.filter(id__in=ids).update(tenant=tenant)
            self.stdout.write(f"  Updated {updated} row(s).")
