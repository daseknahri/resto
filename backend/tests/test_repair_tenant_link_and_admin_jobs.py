"""
Tests for misc admin/owner views:
  - RepairTenantLinkView        POST /api/repair-tenant-link/
  - AdminWalletListView         GET  /api/admin/wallets/
  - AdminCreateDeliveryJobView  POST /api/admin/delivery-jobs/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import RepairTenantLinkView, AdminCreateDeliveryJobView
from menu.views import AdminWalletListView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _non_admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


def _owner_user(tenant_id=None):
    u = MagicMock(spec=User)
    u.__class__ = User
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.tenant = None
    u.id = 5
    u.email = "owner@example.com"
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1, schema_name="tenant1"):
    return SimpleNamespace(id=tenant_id, schema_name=schema_name)


def _make_job(pk=1):
    j = MagicMock()
    j.pk = pk
    j.id = pk
    j.status = "searching"
    j.driver = None
    j.tenant_id = 1
    j.order_number = "ORD-001"
    j.delivery_address = "123 St"
    j.pickup_address = "456 Ave"
    j.delivery_lat = None
    j.delivery_lng = None
    j.pickup_lat = None
    j.pickup_lng = None
    j.delivery_fee = "5.00"
    j.driver_payout = "3.00"
    j.assigned_at = None
    j.picked_up_at = None
    j.delivered_at = None
    j.failed_at = None
    j.is_terminal = False
    j.customer_driver_rating = None
    j.customer_driver_note = ""
    j.driver_customer_rating = None
    j.driver_customer_note = ""
    j.restaurant_driver_rating = None
    j.restaurant_driver_note = ""
    j.created_at = MagicMock()
    j.created_at.isoformat.return_value = "2026-05-01T10:00:00+00:00"
    return j


# ── RepairTenantLinkView ──────────────────────────────────────────────────────

class RepairTenantLinkViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RepairTenantLinkView.as_view()

    def _post(self, user=None, tenant=None):
        req = self.factory.post("/api/repair-tenant-link/")
        req.user = user or _owner_user()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_non_owner_role_returns_403(self):
        u = MagicMock(spec=User)
        u.is_authenticated = True
        u.role = User.Roles.TENANT_STAFF  # not a tenant owner
        u.Roles = User.Roles
        u.tenant_id = None
        resp = self._post(user=u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "forbidden")

    def test_already_linked_returns_200(self):
        u = _owner_user(tenant_id=1)  # already has tenant_id
        with patch("accounts.views.serialize_user_session", return_value={"id": 5}):
            resp = self._post(user=u)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Already linked.")

    def test_no_tenant_in_request_returns_400(self):
        u = _owner_user(tenant_id=None)
        resp = self._post(user=u, tenant=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_tenant")

    def test_conflict_if_another_owner_exists_returns_409(self):
        u = _owner_user(tenant_id=None)
        other_owner = MagicMock()

        with patch("accounts.models.User.objects") as mock_user_objs:
            mock_user_objs.filter.return_value.exclude.return_value.first.return_value = other_owner
            resp = self._post(user=u, tenant=_tenant())

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "conflict")

    def test_successful_repair_links_tenant_and_returns_200(self):
        u = _owner_user(tenant_id=None)
        tenant = _tenant()

        with patch("accounts.models.User.objects") as mock_user_objs:
            mock_user_objs.filter.return_value.exclude.return_value.first.return_value = None
            with patch("accounts.views.serialize_user_session", return_value={"id": 5}):
                resp = self._post(user=u, tenant=tenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Tenant link repaired.")
        self.assertEqual(u.tenant, tenant)
        u.save.assert_called_once_with(update_fields=["tenant"])


# ── AdminWalletListView ───────────────────────────────────────────────────────

class AdminWalletListViewTests(SimpleTestCase):
    def setUp(self):
        # The view is behind AdminPIIThrottle (cache-backed): start each test with a clean bucket
        # so accumulated hits can never 429 a test (see test-throttle-cache-accumulation).
        from django.core.cache import cache
        cache.clear()
        # The PII read audit writes an AdminAuditLog row; stub it so SimpleTestCase never
        # touches the DB (and so tests can assert on the call).
        patcher = patch("menu.views.log_admin_action")
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)
        self.factory = APIRequestFactory()
        self.view = AdminWalletListView.as_view()

    def _get(self, user=None, params=None):
        req = self.factory.get("/api/admin/wallets/", params or {})
        req.user = user or _admin()
        return self.view(req)

    def _empty_get(self, user=None, params=None):
        """GET against an empty mocked Customer queryset."""
        with patch("accounts.models.Customer") as mock_cust:
            qs = MagicMock()
            mock_cust.objects.filter.return_value.order_by.return_value = qs
            qs.filter.return_value = qs  # a ?search= narrows the queryset again
            qs.count.return_value = 0
            qs.__getitem__ = lambda s, k: []
            return self._get(user=user, params=params)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.mock_log.assert_not_called()

    # ── Audit / throttle completeness (admin PII read) ───────────────────────
    def test_uses_platform_admin_permission_and_pii_throttle(self):
        from accounts.throttles import AdminPIIThrottle
        from sales.permissions import IsPlatformAdmin
        self.assertEqual(AdminWalletListView.permission_classes, [IsPlatformAdmin])
        self.assertIn(AdminPIIThrottle, AdminWalletListView.throttle_classes)

    def test_superuser_without_platform_admin_role_still_allowed(self):
        """IsPlatformAdmin keeps the superuser bypass the inline check had."""
        u = _non_admin()
        u.is_superuser = True
        self.assertEqual(self._empty_get(user=u).status_code, status.HTTP_200_OK)

    def test_platform_admin_who_is_not_superuser_still_allowed(self):
        u = _non_admin()
        u.is_platform_admin = True
        self.assertEqual(self._empty_get(user=u).status_code, status.HTTP_200_OK)

    def test_get_writes_customer_pii_viewed_audit_without_pii(self):
        from sales.models import AdminAuditLog
        resp = self._empty_get(params={"search": "ali", "min_balance": "5", "page": 2})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.mock_log.assert_called_once()
        kwargs = self.mock_log.call_args[1]
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.CUSTOMER_PII_VIEWED)
        self.assertEqual(kwargs["target_repr"], "wallet_list")
        self.assertEqual(
            kwargs["metadata"],
            {"query": "ali", "min_balance": "5", "count": 0, "page": 2},
        )

    def test_audit_metadata_never_carries_customer_rows(self):
        """Only filters + counts are logged — never a customer's name/email/phone/balance."""
        customer = MagicMock()
        customer.id = 1
        customer.name = "Ali Hassan"
        customer.email = "ali@example.com"
        customer.phone = "0612345678"
        customer.wallet_balance = "50.00"
        with patch("accounts.models.Customer") as mock_cust:
            qs = mock_cust.objects.filter.return_value.order_by.return_value
            qs.count.return_value = 1
            qs.__getitem__ = lambda s, k: [customer]
            self._get()
        flat = repr(self.mock_log.call_args[1]["metadata"])
        for secret in ("Ali Hassan", "ali@example.com", "0612345678", "50.00"):
            self.assertNotIn(secret, flat)

    def test_returns_wallet_list_structure(self):
        customer = MagicMock()
        customer.id = 1
        customer.name = "Ali Hassan"
        customer.email = "ali@example.com"
        customer.phone = "0612345678"
        customer.wallet_balance = "50.00"

        with patch("accounts.models.Customer") as mock_cust:
            qs = mock_cust.objects.filter.return_value.order_by.return_value
            qs.count.return_value = 1
            qs.__getitem__ = lambda s, k: [customer]
            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("results", resp.data)
        self.assertIn("page", resp.data)
        self.assertEqual(resp.data["results"][0]["name"], "Ali Hassan")
        self.assertEqual(resp.data["results"][0]["email"], "ali@example.com")

    def test_empty_results(self):
        with patch("accounts.models.Customer") as mock_cust:
            qs = MagicMock()
            mock_cust.objects.filter.return_value.order_by.return_value = qs
            qs.count.return_value = 0
            qs.__getitem__ = lambda s, k: []
            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 0)
        self.assertEqual(resp.data["results"], [])

    def test_pagination_params(self):
        with patch("accounts.models.Customer") as mock_cust:
            qs = MagicMock()
            mock_cust.objects.filter.return_value.order_by.return_value = qs
            qs.count.return_value = 0
            qs.__getitem__ = lambda s, k: []
            resp = self._get(params={"page": 2, "page_size": 10})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["page"], 2)
        self.assertEqual(resp.data["page_size"], 10)

    def test_min_balance_filter(self):
        with patch("accounts.models.Customer") as mock_cust:
            qs = MagicMock()
            mock_cust.objects.filter.return_value.order_by.return_value = qs
            qs.count.return_value = 0
            qs.__getitem__ = lambda s, k: []
            resp = self._get(params={"min_balance": "10.00"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # min_balance filter is applied in the queryset
        mock_cust.objects.filter.assert_called()


# ── AdminCreateDeliveryJobView ────────────────────────────────────────────────

class AdminCreateDeliveryJobViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCreateDeliveryJobView.as_view()

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/delivery-jobs/", data, format="json")
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        resp = self._post(
            {"tenant_id": 1, "order_number": "ORD-001"},
            user=_non_admin(),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_tenant_id_returns_400(self):
        resp = self._post({"order_number": "ORD-001"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_order_number_returns_400(self):
        resp = self._post({"tenant_id": 1})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_job_returns_409(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = True
            resp = self._post({"tenant_id": 1, "order_number": "ORD-001"})
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_creates_job_returns_201(self):
        job = _make_job()
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = False
            mock_dj.objects.create.return_value = job
            with patch("accounts.views._serialize_delivery_job", return_value={"id": 1}):
                resp = self._post({
                    "tenant_id": 1,
                    "order_number": "ORD-NEW",
                    "delivery_address": "123 Main St",
                    "pickup_address": "456 Kitchen Ave",
                })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_order_number_uppercased(self):
        job = _make_job()
        with patch("accounts.models.DeliveryJob") as mock_dj:
            mock_dj.objects.filter.return_value.exists.return_value = False
            mock_dj.objects.create.return_value = job
            with patch("accounts.views._serialize_delivery_job", return_value={"id": 1}):
                self._post({
                    "tenant_id": 1,
                    "order_number": "ord-lowercase",
                })
        _, kwargs = mock_dj.objects.create.call_args
        self.assertEqual(kwargs["order_number"], "ORD-LOWERCASE")
