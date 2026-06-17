"""Enforce subscription lifecycle: lapse -> grace period -> suspend (and recovery).

The data model already describes this (Tenant.payment_overdue_since + a grace window),
but nothing automated the transitions — suspension was manual. This command closes
that loop and is meant to run daily (cron):

  1. RECOVER  — a flagged tenant that now has a currently-valid subscription again has
                its overdue flag cleared (back to good standing).
  2. FLAG     — an active tenant whose subscription(s) have all lapsed (every end_date
                in the past) gets payment_overdue_since set -> the grace banner starts.
  3. SUSPEND  — a flagged tenant past the grace window is suspended.

"Currently valid" = an active subscription with end_date null or today-or-later. Billing
is handled offline; an admin lapses a tenant by setting its subscription end_date in the
past (or renews by clearing/extending it), and this command does the rest.

Safe by default: prints what it would do and changes nothing. Pass --apply to act.

    python manage.py enforce_subscriptions            # dry-run report
    python manage.py enforce_subscriptions --apply     # perform transitions (cron)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def _send_renewal_reminder(tenant, grace_days: int) -> None:
    """Best-effort: email the tenant owner a grace-period warning."""
    try:
        from accounts.messaging import send_renewal_reminder_email
        from sales.models import Subscription

        owner = getattr(tenant, "owner", None)
        if not owner or not getattr(owner, "email", ""):
            return
        sub_end = (
            Subscription.objects.filter(tenant_id=tenant.id)
            .order_by("-end_date")
            .values_list("end_date", flat=True)
            .first()
        )
        send_renewal_reminder_email(
            email=owner.email,
            tenant_name=tenant.name,
            grace_days=grace_days,
            subscription_end_date=sub_end.isoformat() if sub_end else None,
        )
    except Exception:
        pass


class Command(BaseCommand):
    help = "Enforce subscription lapse -> grace -> suspend transitions (run daily)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform the transitions. Without this flag the command only reports (dry-run).",
        )
        parser.add_argument(
            "--grace-days",
            type=int,
            default=None,
            help="Override the grace window in days (defaults to Tenant.GRACE_PERIOD_DAYS).",
        )

    def handle(self, *args, **options):
        from datetime import timedelta

        from django.db.models import Q

        from tenancy.models import Tenant
        from sales.models import AdminAuditLog, Subscription

        # A subscription is "currently valid" if it's active and either open-ended
        # (no end_date) or ends today or later.
        def valid_filter(as_of_date):
            return Q(status="active") & (Q(end_date__isnull=True) | Q(end_date__gte=as_of_date))

        apply = options["apply"]
        grace_days = options["grace_days"]
        if grace_days is None:
            grace_days = Tenant.GRACE_PERIOD_DAYS

        now = timezone.now()
        today = now.date()
        suspend_cutoff = now - timedelta(days=grace_days)
        Active = Tenant.LifecycleStatus.ACTIVE
        Suspended = Tenant.LifecycleStatus.SUSPENDED

        def has_valid_subscription(tenant_id):
            return Subscription.objects.filter(valid_filter(today), tenant_id=tenant_id).exists()

        recovered, flagged, suspended = [], [], []

        # Consider only active tenants — suspended/canceled ones are out of this loop.
        active_tenants = Tenant.objects.filter(lifecycle_status=Active)
        for tenant in active_tenants:
            valid = has_valid_subscription(tenant.id)
            overdue = tenant.payment_overdue_since is not None

            if valid and overdue:
                recovered.append(tenant)
                if apply:
                    with transaction.atomic():
                        Tenant.objects.filter(pk=tenant.pk).update(payment_overdue_since=None)
                continue

            if valid:
                continue  # healthy, nothing to do

            # No valid subscription from here on.
            has_any_sub = Subscription.objects.filter(tenant_id=tenant.id).exists()
            if not has_any_sub:
                continue  # never subscribed (e.g. mid-provisioning) — don't touch

            if not overdue:
                flagged.append(tenant)
                if apply:
                    with transaction.atomic():
                        Tenant.objects.filter(pk=tenant.pk).update(payment_overdue_since=now)
                    # B11: send renewal reminder to the tenant owner (best-effort).
                    _send_renewal_reminder(tenant, grace_days)
                continue

            # Already flagged and still lapsed — suspend once past the grace window.
            if tenant.payment_overdue_since <= suspend_cutoff:
                suspended.append(tenant)
                if apply:
                    with transaction.atomic():
                        Tenant.objects.filter(pk=tenant.pk).update(
                            lifecycle_status=Suspended, suspended_at=now
                        )
                        AdminAuditLog.objects.create(
                            action=AdminAuditLog.Actions.TENANT_DEACTIVATED,
                            tenant_id=tenant.pk,
                            target_repr=f"{tenant.slug} ({tenant.name})",
                            metadata={
                                "reason": "subscription_lapsed",
                                "grace_days": grace_days,
                                "overdue_since": tenant.payment_overdue_since.isoformat(),
                            },
                        )

        # REACTIVATE — a tenant the billing cron soft-suspended that has paid again
        # (regained a valid subscription) is restored to good standing. We only touch
        # tenants WE suspended: lifecycle SUSPENDED + an overdue marker + is_active still
        # True. An admin's hard suspension (is_active=False, e.g. ToS) must stay manual.
        reactivated = []
        billing_suspended = Tenant.objects.filter(
            lifecycle_status=Suspended, is_active=True, payment_overdue_since__isnull=False
        )
        for tenant in billing_suspended:
            if not has_valid_subscription(tenant.id):
                continue
            reactivated.append(tenant)
            if apply:
                with transaction.atomic():
                    Tenant.objects.filter(pk=tenant.pk).update(
                        lifecycle_status=Active, suspended_at=None, payment_overdue_since=None
                    )
                    AdminAuditLog.objects.create(
                        action=AdminAuditLog.Actions.TENANT_REACTIVATED,
                        tenant_id=tenant.pk,
                        target_repr=f"{tenant.slug} ({tenant.name})",
                        metadata={"reason": "subscription_renewed", "auto": True},
                    )

        # Suspend/reactivate flip listing membership (tenant__lifecycle_status="active"
        # is the public marketplace/directory filter), so bust the GLOBAL public-list
        # cache once if this --apply run changed any tenant's active state. The version
        # counter is global, so a single bump covers every affected tenant — do NOT
        # bust per-tenant in the loops. Best-effort + lazy import (avoid import cycle).
        if apply and (suspended or reactivated):
            try:
                from accounts.views import _bust_public_list_cache
                _bust_public_list_cache()
            except Exception:
                pass

        prefix = "" if apply else "[dry-run] "
        self.stdout.write(
            f"{prefix}recovered={len(recovered)} flagged_overdue={len(flagged)} "
            f"suspended={len(suspended)} reactivated={len(reactivated)} (grace={grace_days}d)"
        )
        for tenant in reactivated:
            self.stdout.write(f"{prefix}  reactivated: {tenant.slug} (paid again)")
        for tenant in suspended:
            self.stdout.write(f"{prefix}  suspended: {tenant.slug} (overdue since {tenant.payment_overdue_since})")
        if not apply and (recovered or flagged or suspended):
            self.stdout.write("Re-run with --apply to perform these transitions.")
