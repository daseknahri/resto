"""
OPS-5b Admin Security Hardening — Contract Tests

Covers every item in the OPS-5b specification:

  1. PRIV-ESC: IsPlatformAdmin predicate — is_superuser OR is_platform_admin
             (is_staff alone is now REJECTED)
  2. ADMIN-AUTH CONSOLIDATION: admin URLs return 403 for tenant-owner callers
  3. PII READ HARDENING: AdminCustomerListView + AdminCustomerDetailView
        - throttle_classes includes AdminPIIThrottle (scope = "admin_pii")
        - GET writes AdminAuditLog.Actions.CUSTOMER_PII_VIEWED
  4. ADMIN-WRITE AUDITS:
        - is_driver toggle → CUSTOMER_DRIVER_TOGGLED
        - manual delivery job create → DELIVERY_JOB_CREATED
        - tenant deletion request → TENANT_DELETION_REQUESTED
  5. AUDIT ENUM INTEGRITY: PLAN_FEATURE_FLAGS_UPDATED in Actions enum
  6. AUDIT IP TRUST: get_request_ip returns rightmost-trusted XFF entry
     (TRUSTED_PROXY_COUNT=1 default; spoofed leading entries are ignored)
  7. PLAN-LIMIT CREATE RACE: select_for_update() lock used for dish + staff
     creates; 0=unlimited sentinel preserved
  8. BONUS LEDGER: AdminWalletBonusView populates balance_after via post-update
     balance query
  9. SECRETS: ensure_platform_admin reads password from PLATFORM_ADMIN_PASSWORD
     env var first; --password CLI arg is optional (deprecated fallback)

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _user(*, authenticated=True, superuser=False, staff=False,
          platform_admin=False, role=None, pk=1):
    from accounts.models import User
    u = MagicMock(spec=User)
    u.pk = pk
    u.id = pk
    u.is_authenticated = authenticated
    u.is_superuser = superuser
    u.is_staff = staff
    u.is_platform_admin = platform_admin
    u.role = role or User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    return u


def _real_admin(pk=1):
    """Simulates the user shape that ensure_platform_admin creates."""
    from accounts.models import User
    return _user(
        superuser=True,
        staff=True,
        platform_admin=True,
        role=User.Roles.PLATFORM_SUPERADMIN,
        pk=pk,
    )


def _tenant_owner(pk=10):
    return _user(role=None, pk=pk)  # defaults to TENANT_OWNER


def _staff_only_user(pk=20):
    return _user(staff=True, pk=pk)  # is_staff=True but not superuser/platform_admin


def _req(method="GET", user=None, tenant=None, meta=None):
    req = SimpleNamespace(
        method=method,
        user=user or _real_admin(),
        tenant=tenant,
        META=meta or {},
        data={},
    )
    return req


@contextmanager
def _fake_atomic():
    yield


# ═════════════════════════════════════════════════════════════════════════════
# 1. PRIV-ESC — IsPlatformAdmin predicate
# ═════════════════════════════════════════════════════════════════════════════

class TestIsPlatformAdminPredicate(SimpleTestCase):
    """IsPlatformAdmin must admit only is_superuser OR is_platform_admin."""

    def setUp(self):
        from sales.permissions import IsPlatformAdmin
        self.perm = IsPlatformAdmin()
        self.view = None

    def _check(self, user):
        return self.perm.has_permission(_req(user=user), self.view)

    # --- Allowed shapes -------------------------------------------------------

    def test_real_admin_allowed_via_superuser(self):
        """ensure_platform_admin sets is_superuser=True — must be admitted."""
        self.assertTrue(self._check(_real_admin()))

    def test_is_platform_admin_property_alone_allows(self):
        """is_platform_admin=True (without is_superuser) is sufficient."""
        u = _user(platform_admin=True, superuser=False)
        self.assertTrue(self._check(u))

    def test_both_flags_allowed(self):
        """is_superuser=True AND is_platform_admin=True is the canonical shape."""
        u = _user(superuser=True, platform_admin=True)
        self.assertTrue(self._check(u))

    # --- Rejected shapes ------------------------------------------------------

    def test_is_staff_alone_rejected(self):
        """OPS-5b PRIV-ESC: is_staff no longer grants platform-admin access."""
        self.assertFalse(self._check(_staff_only_user()))

    def test_tenant_owner_rejected(self):
        """A TENANT_OWNER with no admin flags must be denied."""
        self.assertFalse(self._check(_tenant_owner()))

    def test_unauthenticated_rejected(self):
        u = _user(authenticated=False)
        self.assertFalse(self._check(u))

    def test_no_user_attribute_rejected(self):
        req = SimpleNamespace(method="GET")  # no .user attribute
        self.assertFalse(self.perm.has_permission(req, self.view))


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADMIN-AUTH CONSOLIDATION — admin URLs reject tenant owners
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminUrlRejectsTenantOwner(SimpleTestCase):
    """Every /api/admin/ view must return 403 for a plain tenant owner."""

    factory = APIRequestFactory()

    def _403(self, view_cls, method="get", url="/api/admin/", **view_kwargs):
        """Invoke view_cls via DRF as a non-admin and assert 403 is returned.

        Uses MagicMock(spec=User) so that isinstance(u, User) returns True — this
        means the rejection is proven to come from the IsPlatformAdmin permission gate
        (is_superuser=False, is_platform_admin=False) rather than from an isinstance
        guard inside the view.  A plain MagicMock() would fail isinstance checks and
        could mask inline gate inconsistencies.
        """
        from accounts.models import User
        u = MagicMock(spec=User)
        u.is_authenticated = True
        u.is_superuser = False
        u.is_staff = False
        u.is_platform_admin = False
        u.role = User.Roles.TENANT_OWNER

        req_factory_method = getattr(self.factory, method)
        req = req_factory_method(url)
        req.user = u
        view = view_cls.as_view()
        resp = view(req, **view_kwargs)
        self.assertEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            f"{view_cls.__name__} returned {resp.status_code} instead of 403",
        )

    def test_admin_customer_list_rejects_tenant_owner(self):
        from accounts.views import AdminCustomerListView
        self._403(AdminCustomerListView, url="/api/admin/customers/")

    def test_admin_driver_list_rejects_tenant_owner(self):
        from accounts.views import AdminDriverListView
        self._403(AdminDriverListView, url="/api/admin/drivers/")

    def test_admin_delivery_job_list_rejects_tenant_owner(self):
        from accounts.views import AdminDeliveryJobListView
        self._403(AdminDeliveryJobListView, url="/api/admin/delivery-jobs/")

    def test_admin_delivery_zone_list_rejects_tenant_owner(self):
        from accounts.views import AdminDeliveryZoneListCreateView
        self._403(AdminDeliveryZoneListCreateView, url="/api/admin/delivery-zones/")

    def test_admin_wallet_bonus_rejects_tenant_owner(self):
        from accounts.views import AdminWalletBonusView
        self._403(AdminWalletBonusView, method="post", url="/api/admin/wallet/bonus/")

    def test_admin_platform_analytics_rejects_tenant_owner(self):
        from accounts.views import AdminPlatformAnalyticsView
        self._403(AdminPlatformAnalyticsView, url="/api/admin/platform-analytics/")

    def test_admin_delivery_zone_detail_rejects_tenant_owner(self):
        from accounts.views import AdminDeliveryZoneDetailView
        self._403(AdminDeliveryZoneDetailView, url="/api/admin/delivery-zones/1/", zone_id=1)


# ═════════════════════════════════════════════════════════════════════════════
# 3. PII READ HARDENING — throttle scope + audit on GET
# ═════════════════════════════════════════════════════════════════════════════

class TestPIIReadHardening(SimpleTestCase):
    """AdminCustomerListView and AdminCustomerDetailView must throttle + audit."""

    def test_customer_list_has_admin_pii_throttle(self):
        """throttle_classes must include AdminPIIThrottle with scope 'admin_pii'."""
        from accounts.views import AdminCustomerListView
        from accounts.throttles import AdminPIIThrottle

        throttles = AdminCustomerListView.throttle_classes
        scopes = [t.scope for t in throttles if hasattr(t, "scope")]
        self.assertIn(AdminPIIThrottle, throttles,
                      "AdminPIIThrottle must be in throttle_classes")
        self.assertIn("admin_pii", scopes)

    def test_customer_detail_has_admin_pii_throttle(self):
        from accounts.views import AdminCustomerDetailView
        from accounts.throttles import AdminPIIThrottle

        throttles = AdminCustomerDetailView.throttle_classes
        self.assertIn(AdminPIIThrottle, throttles,
                      "AdminPIIThrottle must be in throttle_classes")

    def test_pii_throttle_cache_key_keyed_on_user_pk(self):
        """get_cache_key must produce a key containing the user pk."""
        from accounts.throttles import AdminPIIThrottle

        throttle = AdminPIIThrottle()
        throttle.rate = "120/min"
        throttle.num_requests, throttle.duration = 120, 60
        req = SimpleNamespace(
            META={},
            user=SimpleNamespace(is_authenticated=True, pk=42, id=42),
        )
        key = throttle.get_cache_key(req, None)
        self.assertIsNotNone(key)
        self.assertIn("42", key)
        self.assertIn("admin_pii", key)

    def test_customer_list_get_writes_pii_audit(self):
        """GET /api/admin/customers/ must call log_admin_action(CUSTOMER_PII_VIEWED)."""
        from accounts.views import AdminCustomerListView
        from sales.models import AdminAuditLog

        factory = APIRequestFactory()
        req = factory.get("/api/admin/customers/")
        req.user = _real_admin()

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = lambda s, k: []

        with patch("accounts.models.Customer.objects", mock_qs), \
             patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.views.AdminPIIThrottle.allow_request", return_value=True):
            view = AdminCustomerListView.as_view()
            resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        self.assertEqual(call_kwargs["action"], AdminAuditLog.Actions.CUSTOMER_PII_VIEWED)

    def test_customer_detail_get_writes_pii_audit(self):
        """GET /api/admin/customers/<id>/ must call log_admin_action(CUSTOMER_PII_VIEWED)."""
        from accounts.views import AdminCustomerDetailView
        from sales.models import AdminAuditLog

        factory = APIRequestFactory()
        req = factory.get("/api/admin/customers/5/")
        req.user = _real_admin()

        mock_customer = MagicMock()
        mock_customer.id = 5
        mock_customer.name = "Test"
        mock_customer.phone = "0600000001"
        mock_customer.email = "test@example.com"
        mock_customer.wallet_balance = "0.00"
        mock_customer.is_driver = False
        mock_customer.is_driver_online = False
        mock_customer.driver_lat = None
        mock_customer.driver_lng = None
        mock_customer.created_at = MagicMock()
        mock_customer.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        mock_customer.is_phone_verified = True

        with patch("accounts.models.Customer.objects") as mock_cust_objs, \
             patch("accounts.models.WalletTransaction.objects") as mock_tx, \
             patch("accounts.models.CustomerRating.objects") as mock_ratings, \
             patch("accounts.models.DeliveryJob.objects") as mock_dj, \
             patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.views.AdminPIIThrottle.allow_request", return_value=True):
            mock_cust_objs.get.return_value = mock_customer
            mock_tx.filter.return_value.order_by.return_value = []
            mock_ratings.filter.return_value.aggregate.return_value = {"avg": None, "count": 0}
            mock_dj.filter.return_value.count.return_value = 0
            view = AdminCustomerDetailView.as_view()
            resp = view(req, customer_id=5)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_log.assert_called()
        actions = [c[1]["action"] for c in mock_log.call_args_list]
        self.assertIn(AdminAuditLog.Actions.CUSTOMER_PII_VIEWED, actions)


# ═════════════════════════════════════════════════════════════════════════════
# 4. ADMIN-WRITE AUDITS
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminWriteAudits(SimpleTestCase):
    """Write-path endpoints must fire the correct audit action."""

    def test_is_driver_patch_fires_customer_driver_toggled(self):
        """PATCH with is_driver in payload → CUSTOMER_DRIVER_TOGGLED audit."""
        from accounts.views import AdminCustomerDetailView
        from sales.models import AdminAuditLog

        factory = APIRequestFactory()
        req = factory.patch(
            "/api/admin/customers/5/",
            {"is_driver": True},
            format="json",
        )
        req.user = _real_admin()

        mock_customer = MagicMock()
        mock_customer.id = 5
        mock_customer.is_driver = False
        mock_customer.is_driver_online = False

        with patch("accounts.models.Customer.objects") as mock_cust_objs, \
             patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.views.AdminPIIThrottle.allow_request", return_value=True):
            mock_cust_objs.get.return_value = mock_customer
            view = AdminCustomerDetailView.as_view()
            resp = view(req, customer_id=5)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        actions = [c[1]["action"] for c in mock_log.call_args_list]
        self.assertIn(AdminAuditLog.Actions.CUSTOMER_DRIVER_TOGGLED, actions)

    def test_owner_deletion_request_fires_tenant_deletion_requested(self):
        """POST /api/owner/deletion-request/ → TENANT_DELETION_REQUESTED audit.

        The view checks user.is_tenant_owner, then runs inside schema_context("public").
        We mock all external dependencies (schema_context, Tenant model, email) and
        assert that log_admin_action is called with TENANT_DELETION_REQUESTED.
        """
        from tenancy.api import OwnerDeletionRequestView
        from sales.models import AdminAuditLog

        factory = APIRequestFactory()
        req = factory.post(
            "/api/owner/deletion-request/",
            {"reason": "going out of business"},
            format="json",
        )
        owner = MagicMock()
        owner.is_authenticated = True
        owner.is_tenant_owner = True   # View checks this attribute directly
        owner.email = "owner@acme.com"
        req.user = owner
        req.tenant = MagicMock()
        req.tenant.id = 1
        req.tenant.pk = 1
        req.tenant.slug = "acme"
        req.tenant.name = "Acme"

        mock_now = MagicMock()
        mock_now.isoformat.return_value = "2026-06-14T00:00:00+00:00"

        mock_tenant_obj = MagicMock()
        mock_tenant_obj.slug = "acme"
        mock_tenant_obj.deletion_requested_at = None
        mock_tenant_obj.deletion_reason = ""

        def _fake_sc(schema):
            @contextmanager
            def _ctx():
                yield
            return _ctx()

        with patch("django_tenants.utils.schema_context", side_effect=_fake_sc), \
             patch("sales.audit.log_admin_action") as mock_log, \
             patch("django.utils.timezone.now", return_value=mock_now), \
             patch("django.core.mail.send_mail"):
            # Patch Tenant model inside the with-block (local import inside view)
            import tenancy.models as _tm
            orig_tenant = _tm.Tenant
            mock_tenant_cls = MagicMock()
            mock_tenant_cls.objects.get.return_value = mock_tenant_obj
            _tm.Tenant = mock_tenant_cls
            try:
                view = OwnerDeletionRequestView.as_view()
                resp = view(req)
            finally:
                _tm.Tenant = orig_tenant

        # View returns 200 on success
        self.assertEqual(resp.status_code, 200)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        self.assertEqual(call_kwargs["action"], AdminAuditLog.Actions.TENANT_DELETION_REQUESTED)

    def test_create_delivery_job_fires_delivery_job_created(self):
        """POST /api/admin/delivery-jobs/ on success path → DELIVERY_JOB_CREATED audit.

        Verifies that AdminCreateDeliveryJobView.post calls log_admin_action with
        AdminAuditLog.Actions.DELIVERY_JOB_CREATED after DeliveryJob.objects.create.
        """
        from accounts.views import AdminCreateDeliveryJobView
        from sales.models import AdminAuditLog

        factory = APIRequestFactory()
        req = factory.post(
            "/api/admin/delivery-jobs/",
            {
                "tenant_id": 1,
                "order_number": "ORD-001",
                "pickup_address": "Pickup St",
                "delivery_address": "Drop St",
                "delivery_fee": "20.00",
                "driver_payout": "15.00",
            },
            format="json",
        )
        req.user = _real_admin()

        mock_job = MagicMock()
        mock_job.id = 99
        mock_job.tenant_id = 1

        mock_dj_qs = MagicMock()
        mock_dj_qs.filter.return_value.exists.return_value = False

        mock_dz_qs = MagicMock()

        with patch("accounts.views.log_admin_action") as mock_log, \
             patch("accounts.models.DeliveryJob.objects", mock_dj_qs) as _dj, \
             patch("accounts.models.DeliveryZone.objects", mock_dz_qs), \
             patch("accounts.views._batch_business_types", return_value={1: "restaurant"}), \
             patch("accounts.views._serialize_delivery_job", return_value={}):
            mock_dj_qs.create.return_value = mock_job
            # push_new_job_to_drivers is imported inside a try/except — let it fail silently
            view = AdminCreateDeliveryJobView.as_view()
            resp = view(req)

        self.assertEqual(
            resp.status_code, status.HTTP_201_CREATED,
            f"Expected 201, got {resp.status_code}",
        )
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        self.assertEqual(
            call_kwargs["action"],
            AdminAuditLog.Actions.DELIVERY_JOB_CREATED,
        )


# ═════════════════════════════════════════════════════════════════════════════
# 5. AUDIT ENUM INTEGRITY
# ═════════════════════════════════════════════════════════════════════════════

class TestAuditEnumIntegrity(SimpleTestCase):
    """All OPS-5b actions must exist in AdminAuditLog.Actions TextChoices."""

    def _actions(self):
        from sales.models import AdminAuditLog
        return AdminAuditLog.Actions

    def test_customer_pii_viewed_in_enum(self):
        A = self._actions()
        self.assertEqual(A.CUSTOMER_PII_VIEWED, "customer_pii_viewed")

    def test_customer_driver_toggled_in_enum(self):
        A = self._actions()
        self.assertEqual(A.CUSTOMER_DRIVER_TOGGLED, "customer_driver_toggled")

    def test_delivery_job_created_in_enum(self):
        A = self._actions()
        self.assertEqual(A.DELIVERY_JOB_CREATED, "delivery_job_created")

    def test_tenant_deletion_requested_in_enum(self):
        A = self._actions()
        self.assertEqual(A.TENANT_DELETION_REQUESTED, "tenant_deletion_requested")

    def test_plan_feature_flags_updated_in_enum(self):
        A = self._actions()
        self.assertEqual(A.PLAN_FEATURE_FLAGS_UPDATED, "plan_feature_flags_updated")

    def test_sales_views_uses_enum_not_raw_string(self):
        """sales/views.py must use Actions.PLAN_FEATURE_FLAGS_UPDATED (not raw string)."""
        import inspect
        import sales.views as sv
        src = inspect.getsource(sv)
        # The old raw string assignment must be gone
        self.assertNotIn('action="plan_feature_flags_updated"', src,
                         "Raw string found — use AdminAuditLog.Actions.PLAN_FEATURE_FLAGS_UPDATED")
        self.assertIn("PLAN_FEATURE_FLAGS_UPDATED", src,
                      "sales/views.py must reference the Actions enum member")

    def test_accounts_views_uses_enum_not_raw_string_for_platform_settings(self):
        """accounts/views.py must use Actions.PLATFORM_SETTINGS_UPDATED (not raw string)."""
        import inspect
        import accounts.views as av
        src = inspect.getsource(av)
        self.assertNotIn('action="platform_settings_updated"', src,
                         "Raw string found in accounts/views.py — use AdminAuditLog.Actions.PLATFORM_SETTINGS_UPDATED")
        self.assertIn("PLATFORM_SETTINGS_UPDATED", src,
                      "accounts/views.py must reference the Actions.PLATFORM_SETTINGS_UPDATED enum member")


# ═════════════════════════════════════════════════════════════════════════════
# 6. AUDIT IP TRUST — rightmost-trusted XFF
# ═════════════════════════════════════════════════════════════════════════════

class TestAuditIPTrust(SimpleTestCase):
    """get_request_ip must use TRUSTED_PROXY_COUNT-aware rightmost-trusted IP."""

    def setUp(self):
        from sales.audit import get_request_ip
        self.get_ip = get_request_ip

    def _req(self, xff=None, remote_addr="127.0.0.1"):
        meta = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return SimpleNamespace(META=meta)

    def test_single_proxy_skips_one_rightmost_entry(self):
        """TRUSTED_PROXY_COUNT=1 (default): with 2-entry XFF, returns index len-1=1."""
        req = self._req(xff="203.0.113.1, 10.0.0.2")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            ip = self.get_ip(req)
        # idx = 2-1 = 1 → "10.0.0.2" (the IP our proxy saw)
        self.assertEqual(ip, "10.0.0.2")

    def test_spoofed_leading_entry_ignored(self):
        """Client-supplied leading XFF entries cannot forge the rightmost proxy entry."""
        req = self._req(xff="SPOOFED, also_spoofed, 10.0.0.2")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            ip = self.get_ip(req)
        # 3 entries, idx = 3-1 = 2 → "10.0.0.2" (proxy-added)
        self.assertEqual(ip, "10.0.0.2")

    def test_two_proxy_count_skips_two(self):
        """TRUSTED_PROXY_COUNT=2 with 3-entry XFF returns index 3-2=1."""
        req = self._req(xff="real_client, proxy1_added, proxy2_added")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 2
            ip = self.get_ip(req)
        self.assertEqual(ip, "proxy1_added")

    def test_zero_count_disables_xff(self):
        """TRUSTED_PROXY_COUNT=0 disables XFF processing; falls back to REMOTE_ADDR."""
        req = self._req(xff="203.0.113.1, 10.0.0.2", remote_addr="10.0.0.1")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 0
            ip = self.get_ip(req)
        self.assertEqual(ip, "10.0.0.1")

    def test_single_xff_entry_returns_it(self):
        """Single XFF entry with count=1: idx = 1-1 = 0 → return that entry."""
        req = self._req(xff="203.0.113.5")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            ip = self.get_ip(req)
        self.assertEqual(ip, "203.0.113.5")

    def test_fallback_to_remote_addr(self):
        """No XFF header → return REMOTE_ADDR."""
        req = self._req(remote_addr="192.168.1.1")
        ip = self.get_ip(req)
        self.assertEqual(ip, "192.168.1.1")

    def test_middleware_also_uses_rightmost_trusted(self):
        """RequestLoggingMiddleware._client_ip uses the same trusted-proxy logic.

        _client_ip does `from django.conf import settings as _cfg` locally, so we
        patch `django.conf.settings` at the source.  With TRUSTED_PROXY_COUNT=1 and
        XFF "1.2.3.4, 10.0.0.1", idx = 2-1 = 1 → "10.0.0.1".
        """
        from config.middleware import RequestLoggingMiddleware

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.get.return_value = "0"
        mw = RequestLoggingMiddleware(lambda r: fake_resp)

        factory = APIRequestFactory()
        request = factory.get("/api/orders/", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1")
        request.tenant = None
        request.user = MagicMock(is_authenticated=False)

        with patch("config.middleware.request_logger") as mock_logger:
            from django.conf import settings as _real_settings
            original_count = getattr(_real_settings, "TRUSTED_PROXY_COUNT", None)
            _real_settings.TRUSTED_PROXY_COUNT = 1
            try:
                mw(request)
            finally:
                if original_count is None:
                    try:
                        delattr(_real_settings, "TRUSTED_PROXY_COUNT")
                    except AttributeError:
                        pass
                else:
                    _real_settings.TRUSTED_PROXY_COUNT = original_count

        extra = mock_logger.log.call_args[1]["extra"]["structured"]
        # With count=1, idx = 2-1 = 1 → "10.0.0.1"
        self.assertEqual(extra["client_ip"], "10.0.0.1")


# ═════════════════════════════════════════════════════════════════════════════
# 7. PLAN-LIMIT CREATE RACE — select_for_update() lock used
# ═════════════════════════════════════════════════════════════════════════════

class TestPlanLimitLocking(SimpleTestCase):
    """Dish and staff creates must use select_for_update() to prevent TOCTOU races."""

    def test_dish_create_uses_select_for_update(self):
        """perform_create must call Plan.objects.select_for_update() before filtering."""
        from menu.views import DishViewSet

        tenant = MagicMock()
        tenant.id = 1

        plan_obj = MagicMock()
        plan_obj.max_dishes = 5

        view = DishViewSet()
        view.request = MagicMock()
        view.request.tenant = tenant
        serializer = MagicMock()

        def _fake_schema_ctx(schema):
            @contextmanager
            def _ctx():
                yield
            return _ctx()

        with patch("django.db.transaction.atomic", side_effect=_fake_atomic), \
             patch("django_tenants.utils.get_public_schema_name", return_value="public"), \
             patch("django_tenants.utils.schema_context", side_effect=_fake_schema_ctx), \
             patch("tenancy.models.Plan.objects") as mock_plan_qs, \
             patch("menu.models.Dish.objects") as mock_dish_qs:
            mock_plan_qs.select_for_update.return_value.filter.return_value.first.return_value = plan_obj
            mock_dish_qs.count.return_value = 2  # below limit
            view.perform_create(serializer)

        mock_plan_qs.select_for_update.assert_called_once()
        serializer.save.assert_called_once()

    def test_dish_create_unlimited_plan_skips_lock(self):
        """max_dishes=0 (unlimited): serializer.save() must be called without rejection."""
        from menu.views import DishViewSet

        tenant = MagicMock()
        tenant.id = 1

        plan_obj = MagicMock()
        plan_obj.max_dishes = 0  # unlimited

        view = DishViewSet()
        view.request = MagicMock()
        view.request.tenant = tenant
        serializer = MagicMock()

        def _fake_schema_ctx(schema):
            @contextmanager
            def _ctx():
                yield
            return _ctx()

        with patch("django.db.transaction.atomic", side_effect=_fake_atomic), \
             patch("django_tenants.utils.get_public_schema_name", return_value="public"), \
             patch("django_tenants.utils.schema_context", side_effect=_fake_schema_ctx), \
             patch("tenancy.models.Plan.objects") as mock_plan_qs, \
             patch("menu.models.Dish.objects") as mock_dish_qs:
            mock_plan_qs.select_for_update.return_value.filter.return_value.first.return_value = plan_obj
            mock_dish_qs.count.return_value = 9999  # doesn't matter — unlimited
            view.perform_create(serializer)

        serializer.save.assert_called_once()

    def test_staff_create_uses_select_for_update(self):
        """Staff limit check must call select_for_update() before counting."""
        from accounts.views import OwnerStaffListCreateView

        tenant = MagicMock()
        tenant.id = 1
        tenant.plan = SimpleNamespace(max_staff_accounts=3)

        request = MagicMock()
        request.tenant = tenant
        request.data = {"name": "Ali Ben", "email": "ali@demo.com"}
        request.user = MagicMock()
        request.user.is_authenticated = True

        MockUser = MagicMock()
        MockUser.Roles.TENANT_STAFF = "tenant_staff"
        # Email check → not taken
        email_qs = MagicMock()
        email_qs.exists.return_value = False
        MockUser.objects.filter.return_value = email_qs
        # select_for_update chain → at limit (3)
        sfu_qs = MagicMock()
        sfu_qs.count.return_value = 3
        sfu_qs.exists.return_value = False
        MockUser.objects.select_for_update.return_value.filter.return_value = sfu_qs

        import accounts.models as _am
        orig = _am.User
        _am.User = MockUser
        try:
            with patch("accounts.views._is_tenant_owner", return_value=True), \
                 patch("django.db.transaction.atomic", _fake_atomic):
                view = OwnerStaffListCreateView()
                resp = view.post(request)
        finally:
            _am.User = orig

        # Should be rejected at limit
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["code"], "staff_limit_reached")
        MockUser.objects.select_for_update.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# 8. BONUS LEDGER — balance_after populated
# ═════════════════════════════════════════════════════════════════════════════

class TestBonusLedgerBalanceAfter(SimpleTestCase):
    """AdminWalletBonusView must populate balance_after on each WalletTransaction."""

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_bulk_create_receives_balance_after(self, mock_cust_objs, mock_tx_objs):
        """WalletTransaction.bulk_create must be called with balance_after set."""
        from accounts.views import AdminWalletBonusView

        # flat id list (first values_list call)
        # (id, balance) tuples (second values_list call, after update)
        def _vl_side(*args, **kwargs):
            if kwargs.get("flat"):
                return [1, 2]
            return [(1, "15.00"), (2, "15.00")]

        mock_cust_objs.filter.return_value.values_list.side_effect = _vl_side
        mock_cust_objs.filter.return_value.update.return_value = 2
        mock_tx_objs.bulk_create.return_value = []
        mock_tx_objs.filter.return_value.exists.return_value = False

        factory = APIRequestFactory()
        req = factory.post(
            "/api/admin/wallet/bonus/",
            {"amount": "5.00", "customer_ids": [1, 2]},
            format="json",
        )
        req.user = _real_admin()

        with patch("django.db.transaction.atomic", _fake_atomic):
            view = AdminWalletBonusView.as_view()
            resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # bulk_create must have been called
        mock_tx_objs.bulk_create.assert_called_once()
        txs = mock_tx_objs.bulk_create.call_args[0][0]
        # Every transaction must have a non-None balance_after
        for tx in txs:
            self.assertIsNotNone(
                tx.balance_after,
                "WalletTransaction.balance_after must not be None — OPS-5b ledger fix",
            )

    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_balance_after_matches_post_update_value(self, mock_cust_objs, mock_tx_objs):
        """balance_after must equal the value read AFTER the wallet update."""
        from accounts.views import AdminWalletBonusView

        def _vl_side(*args, **kwargs):
            if kwargs.get("flat"):
                return [7]
            return [(7, "42.50")]  # post-update balance for customer 7

        mock_cust_objs.filter.return_value.values_list.side_effect = _vl_side
        mock_cust_objs.filter.return_value.update.return_value = 1
        mock_tx_objs.bulk_create.return_value = []
        mock_tx_objs.filter.return_value.exists.return_value = False

        factory = APIRequestFactory()
        req = factory.post(
            "/api/admin/wallet/bonus/",
            {"amount": "10.00", "customer_ids": [7]},
            format="json",
        )
        req.user = _real_admin()

        with patch("django.db.transaction.atomic", _fake_atomic):
            view = AdminWalletBonusView.as_view()
            resp = view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        txs = mock_tx_objs.bulk_create.call_args[0][0]
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].balance_after, "42.50")


# ═════════════════════════════════════════════════════════════════════════════
# 9. SECRETS — ensure_platform_admin reads from env var / stdin
# ═════════════════════════════════════════════════════════════════════════════

class TestEnsurePlatformAdminSecrets(SimpleTestCase):
    """ensure_platform_admin must prefer PLATFORM_ADMIN_PASSWORD env var."""

    def _cmd(self):
        from accounts.management.commands.ensure_platform_admin import Command
        return Command()

    def test_password_from_env_var(self):
        """When PLATFORM_ADMIN_PASSWORD is set, it must be used (not CLI arg)."""
        cmd = self._cmd()
        User = MagicMock()
        mock_user = MagicMock()
        User.objects.get_or_create.return_value = (mock_user, True)
        User.Roles = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"

        with patch.dict(os.environ, {"PLATFORM_ADMIN_PASSWORD": "env-secret-pw"}), \
             patch("accounts.management.commands.ensure_platform_admin.get_user_model", return_value=User), \
             patch("accounts.management.commands.ensure_platform_admin.getpass") as mock_gp:
            cmd.stdout = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.handle(email="admin@example.com", password=None)

        # getpass.getpass must NOT be called — env var took priority
        mock_gp.getpass.assert_not_called()
        mock_user.set_password.assert_called_once_with("env-secret-pw")

    def test_cli_password_used_when_no_env_var(self):
        """--password CLI arg is still accepted as a deprecated fallback."""
        cmd = self._cmd()
        User = MagicMock()
        mock_user = MagicMock()
        User.objects.get_or_create.return_value = (mock_user, False)
        User.Roles = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"

        env = {k: v for k, v in os.environ.items() if k != "PLATFORM_ADMIN_PASSWORD"}
        with patch.dict(os.environ, env, clear=True), \
             patch("accounts.management.commands.ensure_platform_admin.get_user_model", return_value=User), \
             patch("accounts.management.commands.ensure_platform_admin.getpass") as mock_gp:
            cmd.stdout = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.handle(email="admin@example.com", password="cli-secret-pw")

        # getpass must NOT be called — CLI arg was provided
        mock_gp.getpass.assert_not_called()
        mock_user.set_password.assert_called_once_with("cli-secret-pw")

    def test_env_var_takes_priority_over_cli_arg(self):
        """PLATFORM_ADMIN_PASSWORD env var beats --password CLI arg (safer)."""
        cmd = self._cmd()
        User = MagicMock()
        mock_user = MagicMock()
        User.objects.get_or_create.return_value = (mock_user, False)
        User.Roles = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"

        with patch.dict(os.environ, {"PLATFORM_ADMIN_PASSWORD": "env-wins"}), \
             patch("accounts.management.commands.ensure_platform_admin.get_user_model", return_value=User):
            cmd.stdout = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.handle(email="admin@example.com", password="cli-loses")

        mock_user.set_password.assert_called_once_with("env-wins")

    def test_password_arg_is_optional(self):
        """--password is declared required=False in add_arguments (CLI arg is optional)."""
        import argparse
        cmd = self._cmd()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        action = next(a for a in parser._actions if hasattr(a, "option_strings")
                      and "--password" in getattr(a, "option_strings", []))
        self.assertFalse(
            getattr(action, "required", True),
            "--password must be optional (required=False) in add_arguments",
        )
