"""Tests for the enforce_subscriptions management command (DB-backed → CI)."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone


def _make_tenant(slug, plan):
    from tenancy.models import Tenant
    t = Tenant(schema_name=slug, name=slug.title(), slug=slug, plan=plan)
    t.auto_create_schema = False
    t.save()
    return t


class EnforceSubscriptionsTests(TransactionTestCase):
    def setUp(self):
        from tenancy.models import Plan
        self.plan = Plan.objects.create(name="Starter", code="enf-starter")

    def _tenant_status(self, tenant):
        from tenancy.models import Tenant
        return Tenant.objects.get(pk=tenant.pk)

    def test_lapsed_tenant_gets_flagged_then_suspended_after_grace(self):
        from sales.models import Subscription
        from tenancy.models import Tenant

        tenant = _make_tenant("lapsed-resto", self.plan)
        # Subscription that ended yesterday → lapsed.
        Subscription.objects.create(
            tenant=tenant, plan=self.plan, status="active",
            end_date=timezone.now().date() - timedelta(days=1),
        )

        # First run: flags overdue (starts grace), does not suspend.
        call_command("enforce_subscriptions", "--apply", stdout=StringIO())
        t = self._tenant_status(tenant)
        self.assertIsNotNone(t.payment_overdue_since)
        self.assertEqual(t.lifecycle_status, Tenant.LifecycleStatus.ACTIVE)

        # Backdate the overdue flag beyond the grace window, then run again → suspended.
        Tenant.objects.filter(pk=tenant.pk).update(
            payment_overdue_since=timezone.now() - timedelta(days=Tenant.GRACE_PERIOD_DAYS + 1)
        )
        call_command("enforce_subscriptions", "--apply", stdout=StringIO())
        self.assertEqual(self._tenant_status(tenant).lifecycle_status, Tenant.LifecycleStatus.SUSPENDED)

    def test_valid_subscription_recovers_overdue_flag(self):
        from sales.models import Subscription
        from tenancy.models import Tenant

        tenant = _make_tenant("recovered-resto", self.plan)
        Tenant.objects.filter(pk=tenant.pk).update(payment_overdue_since=timezone.now())
        # An open-ended active subscription = currently valid.
        Subscription.objects.create(tenant=tenant, plan=self.plan, status="active", end_date=None)

        call_command("enforce_subscriptions", "--apply", stdout=StringIO())
        self.assertIsNone(self._tenant_status(tenant).payment_overdue_since)

    def test_dry_run_changes_nothing(self):
        from sales.models import Subscription
        from tenancy.models import Tenant

        tenant = _make_tenant("dryrun-resto", self.plan)
        Subscription.objects.create(
            tenant=tenant, plan=self.plan, status="active",
            end_date=timezone.now().date() - timedelta(days=1),
        )
        out = StringIO()
        call_command("enforce_subscriptions", stdout=out)  # no --apply
        self.assertIn("dry-run", out.getvalue())
        self.assertIsNone(self._tenant_status(tenant).payment_overdue_since)
