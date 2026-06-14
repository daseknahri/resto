"""
OPS-5 BILLING + SUPPORT tests.

Contracts covered:

  E — Plan-limit enforcement at write time
      - DishViewSet.perform_create: 402/ValidationError when at max_dishes (limit >0).
      - DishViewSet.perform_create: unlimited plan (max_dishes=0) is NOT rejected.
      - OwnerStaffListCreateView POST: 400 when at max_staff_accounts (limit >0).
      - OwnerStaffListCreateView POST: unlimited plan (max_staff_accounts=0) NOT rejected
        (mocked so the create itself succeeds without a real DB).

  F — Admin live-orders support view
      - Non-admin gets HTTP 403.
      - Admin access writes an audit row (action=tenant_live_orders_viewed).
      - Returns only that tenant's active orders (reads inside schema_context).

  G — Billing: invoice_amount persisted on approve
      - decide_tier_upgrade_request sets invoice_amount on the upgrade_request object
        when invoice_amount is provided.
      - invoice_amount is included in the save update_fields list.
      - invoice_currency is also persisted when provided.
      - Neither field is touched when invoice_amount=None (no regression).

House style: SimpleTestCase + MagicMock, no real DB.
Sentinel: max_dishes=0 / max_staff_accounts=0 → unlimited (falsy guard in both views).
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call, PropertyMock, ANY

from django.test import SimpleTestCase, RequestFactory
from rest_framework.test import APIRequestFactory


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_plan(max_dishes=0, max_staff_accounts=0, code="starter", is_active=True):
    plan = MagicMock()
    plan.max_dishes = max_dishes
    plan.max_staff_accounts = max_staff_accounts
    plan.code = code
    plan.is_active = is_active
    return plan


def _make_tenant(plan=None, slug="test-tenant", schema_name="tenant_test", id=1):
    tenant = MagicMock()
    tenant.id = id
    tenant.slug = slug
    tenant.schema_name = schema_name
    tenant.plan = plan or _make_plan()
    return tenant


# ═══════════════════════════════════════════════════════════════════════════════
# E — Plan-limit enforcement: DishViewSet.perform_create
# ═══════════════════════════════════════════════════════════════════════════════

class TestDishPlanLimit(SimpleTestCase):
    """DishViewSet.perform_create must reject when max_dishes is reached,
    but must NOT reject when the plan is unlimited (max_dishes=0)."""

    def _call_perform_create(self, tenant, dish_count):
        """Import the view and call perform_create with mocked DB."""
        from menu.views import DishViewSet
        from rest_framework.exceptions import ValidationError

        view = DishViewSet()
        view.request = MagicMock()
        view.request.tenant = tenant
        serializer = MagicMock()

        public_schema = "public"

        def fake_schema_context(schema):
            from contextlib import contextmanager

            @contextmanager
            def _ctx():
                yield

            return _ctx()

        # OPS-5b: perform_create now uses transaction.atomic() + select_for_update().
        # Patch atomic as a no-op so the limit check runs without a real DB.
        # Plan mock chain updated: select_for_update().filter().first() → plan obj.
        plan_obj = MagicMock()
        plan_obj.max_dishes = tenant.plan.max_dishes

        def _fake_atomic():
            from contextlib import contextmanager
            @contextmanager
            def _ctx():
                yield
            return _ctx()

        with patch("django.db.transaction.atomic", side_effect=_fake_atomic), \
             patch("django_tenants.utils.get_public_schema_name", return_value=public_schema), \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("tenancy.models.Plan.objects") as mock_plan_qs, \
             patch("menu.models.Dish.objects") as mock_dish_qs:

            # Plan lookup: select_for_update().filter().first() returns plan object
            mock_plan_qs.select_for_update.return_value.filter.return_value.first.return_value = plan_obj
            # Current dish count
            mock_dish_qs.count.return_value = dish_count

            try:
                view.perform_create(serializer)
            except ValidationError:
                raise
            # If serializer.save() was called, the create succeeded.
            return serializer.save.called

    def test_rejected_at_limit(self):
        """When dish count equals max_dishes (limit > 0), perform_create raises ValidationError."""
        from rest_framework.exceptions import ValidationError
        plan = _make_plan(max_dishes=10)
        tenant = _make_tenant(plan=plan)
        with self.assertRaises(ValidationError) as ctx:
            self._call_perform_create(tenant, dish_count=10)
        detail = ctx.exception.detail
        # Either a dict or list containing the error info
        detail_str = str(detail)
        self.assertIn("dish_limit_reached", detail_str)

    def test_rejected_when_over_limit(self):
        """When dish count exceeds max_dishes, ValidationError is raised."""
        from rest_framework.exceptions import ValidationError
        plan = _make_plan(max_dishes=5)
        tenant = _make_tenant(plan=plan)
        with self.assertRaises(ValidationError):
            self._call_perform_create(tenant, dish_count=7)

    def test_unlimited_plan_not_rejected(self):
        """When max_dishes=0 (unlimited), perform_create proceeds even at 10000 dishes."""
        plan = _make_plan(max_dishes=0)
        tenant = _make_tenant(plan=plan)
        saved = self._call_perform_create(tenant, dish_count=10000)
        self.assertTrue(saved, "serializer.save() must be called for unlimited plans")

    def test_below_limit_not_rejected(self):
        """When dish count is below max_dishes, perform_create succeeds."""
        plan = _make_plan(max_dishes=10)
        tenant = _make_tenant(plan=plan)
        saved = self._call_perform_create(tenant, dish_count=5)
        self.assertTrue(saved)


# ═══════════════════════════════════════════════════════════════════════════════
# E — Plan-limit enforcement: staff create
# ═══════════════════════════════════════════════════════════════════════════════

class TestStaffPlanLimit(SimpleTestCase):
    """OwnerStaffListCreateView.post must 400 when staff count >= max_staff_accounts (>0),
    but must NOT reject when max_staff_accounts=0 (unlimited)."""

    def _post_staff(self, tenant, staff_count, max_staff):
        """Simulate the plan-limit section of OwnerStaffListCreateView.post.

        User is imported locally inside the view method as `from .models import User`,
        so we patch `accounts.models.User` (the canonical location) and also patch
        the local import binding via sys.modules so the `from .models import User`
        inside the method picks up the mock.
        """
        import sys
        from accounts.views import OwnerStaffListCreateView
        from rest_framework.response import Response

        view = OwnerStaffListCreateView()
        request = MagicMock()
        request.tenant = tenant
        request.data = {"name": "New Waiter", "email": "new@example.com"}
        request.user = MagicMock()
        request.user.is_authenticated = True

        tenant.plan.max_staff_accounts = max_staff

        MockUser = MagicMock()
        # Email uniqueness check: no existing user with this email
        email_exists_qs = MagicMock()
        email_exists_qs.exists.return_value = False
        # Staff count filter. exists()=False is REQUIRED: the view's username-dedup
        # loop (`while User.objects.filter(username=...).exists()`) routes through this
        # same non-email branch, so leaving exists() as a truthy MagicMock spins an
        # infinite loop that grows `counter`/username unbounded → MemoryError.
        staff_filter_qs = MagicMock()
        staff_filter_qs.count.return_value = staff_count
        staff_filter_qs.exists.return_value = False

        def filter_side_effect(**kwargs):
            if "email" in kwargs:
                return email_exists_qs
            # role filter — returns staff count queryset
            return staff_filter_qs

        MockUser.objects.filter.side_effect = filter_side_effect
        MockUser.Roles.TENANT_STAFF = "tenant_staff"

        # OPS-5b: staff limit check now uses select_for_update().filter().count()
        # instead of filter().count().  We must set the count on the select_for_update
        # chain; the username-dedup loop still uses filter() directly, so exists()=False
        # on select_for_update chain is also required to be safe.
        su_qs = MockUser.objects.select_for_update.return_value
        su_filter_qs = MagicMock()
        su_filter_qs.count.return_value = staff_count
        su_filter_qs.exists.return_value = False  # safety — avoid any while-loop spin
        su_qs.filter.return_value = su_filter_qs

        # Also patch transaction.atomic so the atomic block works without a real DB.
        import django.db.transaction as _dbt
        from contextlib import contextmanager
        @contextmanager
        def _fake_atomic():
            yield
        _dbt_atomic_orig = _dbt.atomic
        _dbt.atomic = _fake_atomic

        # If limit is not reached we need to avoid the rest of the create; patch
        # create_user to raise StopIteration so we can detect we got past the gate.
        MockUser.objects.create_user.side_effect = StopIteration("past limit check")

        # Patch: _is_tenant_owner → True, and inject MockUser into accounts.models
        # so local `from .models import User` inside the method gets the mock.
        import accounts.models as _am
        original_user = _am.User if hasattr(_am, "User") else None
        _am.User = MockUser
        try:
            with patch("accounts.views._is_tenant_owner", return_value=True):
                try:
                    resp = view.post(request)
                    return resp
                except StopIteration:
                    # Got past the limit check successfully (unlimited or below limit)
                    return None
        finally:
            if original_user is not None:
                _am.User = original_user
            elif hasattr(_am, "User"):
                del _am.User
            # Restore real transaction.atomic
            _dbt.atomic = _dbt_atomic_orig

    def test_staff_rejected_at_limit(self):
        """When staff count equals max_staff_accounts (>0), 400 is returned."""
        plan = _make_plan(max_staff_accounts=3)
        tenant = _make_tenant(plan=plan)
        resp = self._post_staff(tenant, staff_count=3, max_staff=3)
        self.assertIsNotNone(resp, "Expected a Response, not StopIteration")
        self.assertEqual(resp.status_code, 400)
        data = resp.data
        self.assertEqual(data.get("code"), "staff_limit_reached")
        self.assertIn("limit", data)
        self.assertIn("current", data)

    def test_staff_not_rejected_unlimited(self):
        """When max_staff_accounts=0 (unlimited), the limit check is skipped."""
        plan = _make_plan(max_staff_accounts=0)
        tenant = _make_tenant(plan=plan)
        # Should raise StopIteration (got past limit check into create path)
        resp = self._post_staff(tenant, staff_count=9999, max_staff=0)
        # resp is None means we hit StopIteration — the limit guard was skipped
        self.assertIsNone(resp, "Unlimited plan must not return a limit-rejection response")

    def test_staff_not_rejected_below_limit(self):
        """When staff count is below max_staff_accounts, create proceeds."""
        plan = _make_plan(max_staff_accounts=5)
        tenant = _make_tenant(plan=plan)
        resp = self._post_staff(tenant, staff_count=2, max_staff=5)
        self.assertIsNone(resp)


# ═══════════════════════════════════════════════════════════════════════════════
# F — Admin live-orders support view
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminLiveOrdersView(SimpleTestCase):
    """AdminTenantLiveOrdersView must be IsPlatformAdmin-gated and audit-logged."""

    def _make_request(self, is_platform_admin=True):
        factory = APIRequestFactory()
        req = factory.get("/api/admin/tenants/1/live-orders/")
        req.user = MagicMock()
        req.user.is_authenticated = True
        req.user.is_platform_admin = is_platform_admin
        req.user.is_staff = False
        req.user.is_superuser = False
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        return req

    def test_non_admin_gets_403(self):
        """A non-platform-admin user receives HTTP 403."""
        from sales.views import AdminTenantLiveOrdersView
        from sales.permissions import IsPlatformAdmin

        view = AdminTenantLiveOrdersView.as_view()
        request = self._make_request(is_platform_admin=False)

        # IsPlatformAdmin.has_permission returns False → DRF returns 403
        with patch.object(IsPlatformAdmin, "has_permission", return_value=False):
            from rest_framework.test import APIRequestFactory as ARF
            factory = ARF()
            req = factory.get("/")
            req.user = MagicMock()
            req.user.is_authenticated = True
            req.user.is_platform_admin = False
            req.user.is_staff = False
            req.user.is_superuser = False

            resp = view(req, tenant_id=1)
            self.assertEqual(resp.status_code, 403)

    def test_admin_access_writes_audit_row(self):
        """Admin access creates an AdminAuditLog row with action=tenant_live_orders_viewed.

        OPS-5: the view now calls AdminAuditLog.objects.create() directly inside
        transaction.atomic() instead of the best-effort log_admin_action() helper.
        We mock at that level so the test verifies the mandatory audit path.
        """
        from sales.views import AdminTenantLiveOrdersView
        from sales.models import AdminAuditLog

        view = AdminTenantLiveOrdersView()

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "acme"
        tenant.schema_name = "tenant_acme"

        fake_order = SimpleNamespace(
            order_number="ORD-001",
            status="pending",
            order_type="dine_in",
            total=Decimal("25.00"),
            created_at=None,
            customer_phone="+212600000001",
        )

        request = self._make_request(is_platform_admin=True)

        public_schema = "public"

        def fake_schema_context(schema):
            from contextlib import contextmanager

            @contextmanager
            def _ctx():
                yield

            return _ctx()

        mock_audit_log_create = MagicMock()

        from contextlib import contextmanager

        @contextmanager
        def fake_atomic():
            yield

        with patch("django_tenants.utils.get_public_schema_name", return_value=public_schema), \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("sales.views.get_object_or_404", return_value=tenant), \
             patch("menu.models.Order.objects") as mock_order_qs, \
             patch("django.db.transaction.atomic", return_value=fake_atomic()), \
             patch("sales.views.AdminAuditLog") as mock_aal_cls, \
             patch("sales.audit.get_request_ip", return_value="127.0.0.1"):

            mock_aal_cls.objects.create = mock_audit_log_create
            mock_aal_cls.Actions.TENANT_LIVE_ORDERS_VIEWED = AdminAuditLog.Actions.TENANT_LIVE_ORDERS_VIEWED
            mock_order_qs.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [fake_order]

            resp = view.get(request, tenant_id=1)

        self.assertEqual(resp.status_code, 200)

        # Audit log MUST have been created directly (mandatory — not best-effort)
        mock_audit_log_create.assert_called_once()
        call_kwargs = mock_audit_log_create.call_args.kwargs
        self.assertEqual(call_kwargs["action"], AdminAuditLog.Actions.TENANT_LIVE_ORDERS_VIEWED)
        self.assertEqual(call_kwargs["tenant"], tenant)
        self.assertIn("order_count", call_kwargs.get("metadata", {}))

    def test_audit_failure_propagates_error(self):
        """If AdminAuditLog.objects.create() raises, the view must NOT return data.

        OPS-5: audit is mandatory; the atomic block ensures that a failed INSERT
        rolls back and the exception propagates (no cross-tenant data served without
        a corresponding audit row).
        """
        from sales.views import AdminTenantLiveOrdersView
        from sales.models import AdminAuditLog

        view = AdminTenantLiveOrdersView()

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "acme"
        tenant.schema_name = "tenant_acme"

        request = self._make_request(is_platform_admin=True)

        public_schema = "public"

        def fake_schema_context(schema):
            from contextlib import contextmanager

            @contextmanager
            def _ctx():
                yield

            return _ctx()

        from django.db import DatabaseError

        # transaction.atomic() is a real context manager — simulate it raising
        # on exit when the audit INSERT fails by making the create() raise.
        from contextlib import contextmanager

        @contextmanager
        def fake_atomic():
            yield  # let the body run; exception from create() propagates out

        with patch("django_tenants.utils.get_public_schema_name", return_value=public_schema), \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("sales.views.get_object_or_404", return_value=tenant), \
             patch("menu.models.Order.objects") as mock_order_qs, \
             patch("django.db.transaction.atomic", return_value=fake_atomic()), \
             patch("sales.views.AdminAuditLog") as mock_aal_cls, \
             patch("sales.audit.get_request_ip", return_value="127.0.0.1"):

            mock_aal_cls.objects.create.side_effect = DatabaseError("DB saturated")
            mock_aal_cls.Actions.TENANT_LIVE_ORDERS_VIEWED = AdminAuditLog.Actions.TENANT_LIVE_ORDERS_VIEWED
            mock_order_qs.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = []

            with self.assertRaises(Exception):
                view.get(request, tenant_id=1)

    def test_returns_only_active_orders(self):
        """The response includes only active-status orders (not terminal ones)."""
        from sales.views import AdminTenantLiveOrdersView

        view = AdminTenantLiveOrdersView()
        view._ACTIVE_STATUSES  # must exist and include non-terminal statuses
        self.assertIn("pending", view._ACTIVE_STATUSES)
        self.assertIn("confirmed", view._ACTIVE_STATUSES)
        self.assertIn("preparing", view._ACTIVE_STATUSES)
        self.assertNotIn("completed", view._ACTIVE_STATUSES)
        self.assertNotIn("cancelled", view._ACTIVE_STATUSES)

    def test_response_shape(self):
        """Response includes tenant_id, tenant_slug, active_order_count, results."""
        from sales.views import AdminTenantLiveOrdersView

        view = AdminTenantLiveOrdersView()

        tenant = MagicMock()
        tenant.id = 7
        tenant.slug = "bistro"
        tenant.schema_name = "tenant_bistro"

        request = self._make_request(is_platform_admin=True)

        public_schema = "public"

        def fake_schema_context(schema):
            from contextlib import contextmanager

            @contextmanager
            def _ctx():
                yield

            return _ctx()

        from contextlib import contextmanager

        @contextmanager
        def fake_atomic():
            yield

        with patch("django_tenants.utils.get_public_schema_name", return_value=public_schema), \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("sales.views.get_object_or_404", return_value=tenant), \
             patch("menu.models.Order.objects") as mock_order_qs, \
             patch("django.db.transaction.atomic", return_value=fake_atomic()), \
             patch("sales.views.AdminAuditLog") as mock_aal_cls, \
             patch("sales.audit.get_request_ip", return_value="127.0.0.1"):

            mock_aal_cls.objects.create = MagicMock()
            mock_aal_cls.Actions.TENANT_LIVE_ORDERS_VIEWED = "tenant_live_orders_viewed"
            mock_order_qs.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = []

            resp = view.get(request, tenant_id=7)

        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertIn("tenant_id", data)
        self.assertIn("tenant_slug", data)
        self.assertIn("active_order_count", data)
        self.assertIn("results", data)
        self.assertEqual(data["tenant_id"], 7)
        self.assertEqual(data["tenant_slug"], "bistro")


# ═══════════════════════════════════════════════════════════════════════════════
# G — Billing: invoice_amount persisted on approve
# ═══════════════════════════════════════════════════════════════════════════════

class TestInvoiceAmountOnApprove(SimpleTestCase):
    """decide_tier_upgrade_request must set invoice_amount on the upgrade_request
    when invoice_amount is provided, and must save it via update_fields.
    When invoice_amount=None, the field must not be touched."""

    def _run_decide(self, invoice_amount=None, invoice_currency="", decision="approve"):
        """Run decide_tier_upgrade_request with mocked DB and return (upgrade_request, saved_fields)."""
        from sales.services import decide_tier_upgrade_request
        from sales.models import TierUpgradeRequest

        # Build mock upgrade_request
        current_plan = MagicMock()
        current_plan.code = "starter"
        current_plan.is_active = True

        target_plan = MagicMock()
        target_plan.code = "growth"
        target_plan.is_active = True
        target_plan.name = "Growth"

        tenant_obj = MagicMock()
        tenant_obj.id = 1
        tenant_obj.plan = current_plan

        upgrade_request = MagicMock()
        upgrade_request.status = TierUpgradeRequest.Status.PENDING
        upgrade_request.tenant = tenant_obj
        upgrade_request.target_plan = target_plan
        upgrade_request.invoice_amount = None
        upgrade_request.invoice_currency = "USD"

        saved_update_fields = []

        def fake_save(update_fields=None):
            if update_fields:
                saved_update_fields.extend(update_fields)

        upgrade_request.save.side_effect = fake_save

        public_schema = "public"

        def fake_schema_context(schema):
            from contextlib import contextmanager

            @contextmanager
            def _ctx():
                yield

            return _ctx()

        # Patch is_plan_upgrade to return True so we don't short-circuit.
        # transaction.atomic must also be patched because SimpleTestCase disallows DB access.
        # MagicMock supports __enter__/__exit__ so it works as a context manager directly.
        with patch("django_tenants.utils.get_public_schema_name", return_value=public_schema), \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("sales.services.transaction.atomic", return_value=MagicMock(__enter__=MagicMock(return_value=None), __exit__=MagicMock(return_value=False))), \
             patch("sales.services.TierUpgradeRequest.objects") as mock_req_qs, \
             patch("sales.services.Tenant.objects") as mock_tenant_qs, \
             patch("sales.services.Subscription.objects") as mock_sub_qs, \
             patch("sales.services.is_plan_upgrade", return_value=True):

            # Real chain is select_for_update().select_related(...).get() — the
            # .select_related hop must be in the mock or .get() returns a bare mock
            # whose .status != PENDING, tripping the "already resolved" guard.
            mock_req_qs.select_for_update.return_value.select_related.return_value.get.return_value = upgrade_request
            mock_tenant_qs.select_related.return_value.get.return_value = tenant_obj

            # Subscription.objects.filter and update_or_create — no-ops
            mock_sub_qs.filter.return_value.exclude.return_value.update.return_value = 0
            mock_sub_qs.update_or_create.return_value = (MagicMock(), True)

            actor = MagicMock()
            actor.is_authenticated = True

            result = decide_tier_upgrade_request(
                request_id=1,
                decision=decision,
                actor=actor,
                invoice_amount=invoice_amount,
                invoice_currency=invoice_currency,
            )

        return upgrade_request, saved_update_fields

    def test_invoice_amount_persisted_on_approve(self):
        """When invoice_amount is provided, it is set on the upgrade_request and saved."""
        upgrade_request, saved_fields = self._run_decide(invoice_amount=Decimal("99.00"))
        self.assertEqual(upgrade_request.invoice_amount, Decimal("99.00"))
        self.assertIn("invoice_amount", saved_fields)

    def test_invoice_currency_persisted_on_approve(self):
        """When invoice_currency is provided, it is saved alongside invoice_amount."""
        upgrade_request, saved_fields = self._run_decide(
            invoice_amount=Decimal("150.00"), invoice_currency="mad"
        )
        # Currency should be upper-cased
        self.assertEqual(upgrade_request.invoice_currency, "MAD")
        self.assertIn("invoice_currency", saved_fields)

    def test_invoice_amount_none_not_in_save_fields(self):
        """When invoice_amount=None (not provided), invoice_amount is NOT in update_fields."""
        _, saved_fields = self._run_decide(invoice_amount=None)
        self.assertNotIn("invoice_amount", saved_fields)

    def test_invoice_amount_string_decimal_accepted(self):
        """String representations of decimal amounts are coerced correctly."""
        upgrade_request, saved_fields = self._run_decide(invoice_amount="250.50")
        self.assertEqual(upgrade_request.invoice_amount, Decimal("250.50"))
        self.assertIn("invoice_amount", saved_fields)

    def test_status_fields_always_in_save(self):
        """Core approval fields are always in update_fields regardless of invoice_amount."""
        _, saved_fields = self._run_decide(invoice_amount=None)
        for required in ("status", "admin_note", "approved_by", "decided_at", "updated_at"):
            self.assertIn(required, saved_fields, f"'{required}' must be in update_fields")
