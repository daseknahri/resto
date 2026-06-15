"""
CHANGE 2b — enforce_subscriptions busts the PUBLIC LIST cache ONCE per --apply run
when it suspends or reactivates any tenant.

The command flips Tenant.lifecycle_status across the active<->non-active line, which is
the public marketplace/directory membership filter (tenant__lifecycle_status="active").
The list-cache version is GLOBAL, so a single bump after the run covers every affected
tenant — the command must NOT bust per-tenant in the loop.

These are mock-only SimpleTestCases (no DB) so they run in the local gate — the real
DB-backed lifecycle assertions live in test_enforce_subscriptions.py (CI/Postgres).
"""
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import timezone


@contextmanager
def _atomic_noop(*a, **k):
    yield


def _tenant(pk=1, *, payment_overdue_since=None):
    return SimpleNamespace(
        id=pk, pk=pk, slug=f"t{pk}", name=f"Tenant {pk}",
        payment_overdue_since=payment_overdue_since,
    )


class _FakeTenantManager:
    """Minimal Tenant.objects stand-in. filter() returns a queryset whose iteration
    yields the rows configured per lifecycle_status; .update() is a recorded no-op."""

    def __init__(self, *, active=None, billing_suspended=None):
        self._active = active or []
        self._billing_suspended = billing_suspended or []
        self.LifecycleStatus = SimpleNamespace(ACTIVE="active", SUSPENDED="suspended")

    def filter(self, *args, **kwargs):
        status = kwargs.get("lifecycle_status")
        rows = []
        if status == "active" and "is_active" not in kwargs:
            rows = self._active
        elif status == "suspended":
            rows = self._billing_suspended
        # pk-scoped .update() calls land here too (kwargs has pk) → empty iter is fine.
        qs = MagicMock()
        qs.__iter__ = lambda s: iter(rows)
        qs.update = MagicMock(return_value=len(rows))
        return qs


def _run_command(*, active=None, billing_suspended=None, sub_valid_map=None,
                 has_any_sub=True, apply=True):
    """Invoke enforce_subscriptions.handle with the ORM mocked; return the
    _bust_public_list_cache mock so the caller can assert call count.

    sub_valid_map: {tenant_id: bool} — whether the tenant has a currently-valid sub.
    """
    sub_valid_map = sub_valid_map or {}

    tenant_mgr = _FakeTenantManager(active=active, billing_suspended=billing_suspended)
    GRACE = 14
    fake_tenant_cls = SimpleNamespace(
        objects=tenant_mgr,
        LifecycleStatus=tenant_mgr.LifecycleStatus,
        GRACE_PERIOD_DAYS=GRACE,
    )

    def _sub_filter(*args, tenant_id=None, **kwargs):
        qs = MagicMock()
        # valid_filter(...) call (has positional Q) → "currently valid?" check.
        if args:
            qs.exists.return_value = sub_valid_map.get(tenant_id, False)
        else:
            qs.exists.return_value = has_any_sub
        return qs

    fake_sub_cls = SimpleNamespace(objects=SimpleNamespace(filter=_sub_filter))
    fake_audit_cls = SimpleNamespace(
        Actions=SimpleNamespace(TENANT_DEACTIVATED="tenant_deactivated",
                                TENANT_REACTIVATED="tenant_reactivated"),
        objects=SimpleNamespace(create=MagicMock()),
    )

    import sys
    fake_tenancy_models = MagicMock()
    fake_tenancy_models.Tenant = fake_tenant_cls
    fake_sales_models = MagicMock()
    fake_sales_models.Subscription = fake_sub_cls
    fake_sales_models.AdminAuditLog = fake_audit_cls

    orig_tenancy = sys.modules.get("tenancy.models")
    orig_sales = sys.modules.get("sales.models")
    sys.modules["tenancy.models"] = fake_tenancy_models
    sys.modules["sales.models"] = fake_sales_models
    try:
        with patch("django.db.transaction.atomic", _atomic_noop), \
                patch("accounts.views._bust_public_list_cache") as bust_mock:
            args = ["enforce_subscriptions"]
            if apply:
                args.append("--apply")
            call_command(*args, stdout=StringIO())
            return bust_mock
    finally:
        if orig_tenancy is None:
            sys.modules.pop("tenancy.models", None)
        else:
            sys.modules["tenancy.models"] = orig_tenancy
        if orig_sales is None:
            sys.modules.pop("sales.models", None)
        else:
            sys.modules["sales.models"] = orig_sales


class EnforceSubscriptionsListCacheTests(SimpleTestCase):

    def test_busts_once_when_a_tenant_is_suspended(self):
        """An active+flagged+past-grace tenant gets suspended → bust exactly once."""
        overdue = timezone.now() - timedelta(days=30)  # well past the 14d grace
        t = _tenant(1, payment_overdue_since=overdue)
        bust = _run_command(active=[t], sub_valid_map={1: False}, has_any_sub=True)
        bust.assert_called_once_with()

    def test_busts_once_when_a_tenant_is_reactivated(self):
        """A billing-suspended tenant that paid again gets reactivated → bust once."""
        t = _tenant(2, payment_overdue_since=timezone.now() - timedelta(days=30))
        bust = _run_command(billing_suspended=[t], sub_valid_map={2: True})
        bust.assert_called_once_with()

    def test_busts_only_once_for_multiple_suspensions(self):
        """The global version means a single bump covers many suspensions — not per-tenant."""
        overdue = timezone.now() - timedelta(days=30)
        ts = [_tenant(i, payment_overdue_since=overdue) for i in (1, 2, 3)]
        bust = _run_command(
            active=ts, sub_valid_map={1: False, 2: False, 3: False}, has_any_sub=True
        )
        bust.assert_called_once_with()

    def test_no_bust_when_nothing_changed(self):
        """A run that only FLAGS (overdue marker, no membership change) must not bust."""
        t = _tenant(1, payment_overdue_since=None)  # not overdue yet → gets flagged, not suspended
        bust = _run_command(active=[t], sub_valid_map={1: False}, has_any_sub=True)
        bust.assert_not_called()

    def test_no_bust_on_dry_run(self):
        """Dry-run changes nothing, so even a would-be suspension must not bust."""
        overdue = timezone.now() - timedelta(days=30)
        t = _tenant(1, payment_overdue_since=overdue)
        bust = _run_command(
            active=[t], sub_valid_map={1: False}, has_any_sub=True, apply=False
        )
        bust.assert_not_called()
