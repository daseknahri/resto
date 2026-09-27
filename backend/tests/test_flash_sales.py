"""
Tests for flash-sale views:
  - AdminFlashSaleListCreateView   GET/POST /api/admin/flash-sales/
  - AdminFlashSaleDetailView       GET/PATCH/DELETE /api/admin/flash-sales/<id>/
  - OwnerFlashSaleListView         GET /api/owner/flash-sales/
  - OwnerFlashSaleOptInView        POST/DELETE /api/owner/flash-sales/<id>/opt-in/

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema switching).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    AdminFlashSaleDetailView,
    AdminFlashSaleListCreateView,
    OwnerFlashSaleListView,
    OwnerFlashSaleOptInView,
)
from accounts.models import User
from sales.models import AdminAuditLog


# ── Helpers ───────────────────────────────────────────────────────────────────

def _admin():
    """Platform admin — passes isinstance(user, User) check via __class__."""
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    u.tenant_id = None
    return u


def _non_admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _outsider(tenant_id=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_fs(fs_id=1, name="Summer Sale", discount_value=Decimal("15.00"),
              is_active=True):
    fs = MagicMock()
    fs.id = fs_id
    fs.name = name
    fs.description = ""
    fs.discount_value = discount_value
    fs.active_from = MagicMock()
    fs.active_from.isoformat.return_value = "2026-06-01T00:00:00+00:00"
    fs.active_until = MagicMock()
    fs.active_until.isoformat.return_value = "2026-06-30T23:59:59+00:00"
    fs.is_active = is_active
    fs.max_redemptions = None
    fs.redemption_count = 0
    fs.created_at = MagicMock()
    fs.created_at.isoformat.return_value = "2026-05-01T00:00:00+00:00"
    return fs


# ── AdminFlashSaleListCreateView ──────────────────────────────────────────────

class AdminFlashSaleListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleListCreateView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/admin/flash-sales/")
        req.user = user or _admin()
        return req

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/flash-sales/", data, format="json")
        req.user = user or _admin()
        return req

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_non_admin_returns_403(self):
        req = self._get(user=_non_admin())
        with patch("accounts.views.schema_context", create=True):  # create-true-ok: schema_context is imported lazily inside view fns (from django_tenants.utils import schema_context as _sc), not at accounts.views module scope; create=True needed to patch the name. 403 path short-circuits before any schema switch, so the patch is just a guard.
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_non_admin_returns_403(self):
        req = self._post({"name": "Sale"}, user=_non_admin())
        with patch("accounts.views.schema_context", create=True):  # create-true-ok: schema_context is imported lazily inside view fns, not at accounts.views module scope; create=True needed to patch the name. 403 path short-circuits before any schema switch, so the patch is just a guard.
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_missing_required_fields_returns_400(self):
        req = self._post({"name": "Sale"})  # missing discount_value, active_from, active_until
        with patch("django_tenants.utils.schema_context"):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_discount_value_returns_400(self):
        req = self._post({
            "name": "Sale", "discount_value": "bad",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
        })
        with patch("django_tenants.utils.schema_context"):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_active_from_after_until_returns_400(self):
        req = self._post({
            "name": "Sale", "discount_value": "10",
            "active_from": "2026-07-01T00:00:00Z",
            "active_until": "2026-06-01T00:00:00Z",
        })
        with patch("django_tenants.utils.schema_context"):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── GET + POST happy paths ────────────────────────────────────────────────

    def test_get_returns_flash_sales_list(self):
        fs = _make_fs()
        req = self._get()
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.all.return_value = [fs]
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_post_creates_flash_sale_and_returns_201(self):
        fs = _make_fs(name="Happy Deal")
        req = self._post({
            "name": "Happy Deal",
            "discount_value": "15.0",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
        })
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.create.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_post_create_busts_public_list_cache_version(self):
        """A flash-sale create changes flash_sale_active in the public listing, so it
        must bust the list cache (bump the global version) — otherwise a new sale can
        take up to the list TTL to surface."""
        from django.core.cache import cache
        from accounts.views import _PUBLIC_LIST_VER_KEY

        cache.set(_PUBLIC_LIST_VER_KEY, 7, timeout=None)
        fs = _make_fs(name="Cache Buster")
        req = self._post({
            "name": "Cache Buster",
            "discount_value": "10.0",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
        })
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.create.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Version was bumped → existing cache entries are orphaned.
        self.assertEqual(cache.get(_PUBLIC_LIST_VER_KEY), 8)

    def test_post_writes_audit_log(self):
        """A flash sale sets a platform-wide discount % — creating one is a money-affecting
        config write that must land in AdminAuditLog (accountability: who/when)."""
        fs = _make_fs(name="Audited Deal", discount_value=Decimal("30.00"))
        req = self._post({
            "name": "Audited Deal",
            "discount_value": "30.0",
            "active_from": "2026-06-01T00:00:00Z",
            "active_until": "2026-06-30T23:59:59Z",
        })
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log:
            mock_fs.objects.create.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.FLASH_SALE_CREATED)
        self.assertEqual(kwargs["target_repr"], f"flash_sale:{fs.id}")
        self.assertEqual(kwargs["metadata"]["discount_value"], "30.00")


# ── AdminFlashSaleDetailView ──────────────────────────────────────────────────

class AdminFlashSaleDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminFlashSaleDetailView.as_view()

    def _get(self, fs_id, user=None):
        req = self.factory.get(f"/api/admin/flash-sales/{fs_id}/")
        req.user = user or _admin()
        return self.view(req, fs_id=fs_id)

    def _delete(self, fs_id, user=None):
        req = self.factory.delete(f"/api/admin/flash-sales/{fs_id}/")
        req.user = user or _admin()
        return self.view(req, fs_id=fs_id)

    def _patch(self, fs_id, data, user=None):
        req = self.factory.patch(f"/api/admin/flash-sales/{fs_id}/", data, format="json")
        req.user = user or _admin()
        return self.view(req, fs_id=fs_id)

    def test_get_non_admin_returns_403(self):
        resp = self._get(1, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_not_found_returns_404(self):
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.DoesNotExist = Exception
            mock_fs.objects.get.side_effect = mock_fs.DoesNotExist
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._get(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_admin_returns_403(self):
        resp = self._delete(1, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_not_found_returns_404(self):
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.DoesNotExist = Exception
            mock_fs.objects.get.side_effect = mock_fs.DoesNotExist
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._delete(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_writes_audit_log(self):
        """Editing a flash sale's discount % must be audited."""
        fs = _make_fs(fs_id=7, discount_value=Decimal("20.00"))
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log:
            mock_fs.objects.get.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._patch(7, {"discount_value": "20"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.FLASH_SALE_UPDATED)
        self.assertEqual(kwargs["target_repr"], "flash_sale:7")
        self.assertIn("discount_value", kwargs["metadata"]["changed_fields"])

    def test_patch_no_change_does_not_audit(self):
        """A no-op PATCH (no recognized fields) changes nothing, so it writes no audit row."""
        fs = _make_fs(fs_id=7)
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log:
            mock_fs.objects.get.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._patch(7, {"unknown_field": "x"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_log.assert_not_called()

    def test_delete_writes_audit_log(self):
        """Deleting a flash sale must be audited (snapshotting the discount it removed)."""
        fs = _make_fs(fs_id=9, discount_value=Decimal("40.00"))
        with patch("accounts.models.PlatformFlashSale") as mock_fs, \
             patch("accounts.views.log_admin_action") as mock_log:
            mock_fs.objects.get.return_value = fs
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._delete(9)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        fs.delete.assert_called_once()
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.FLASH_SALE_DELETED)
        self.assertEqual(kwargs["target_repr"], "flash_sale:9")
        self.assertEqual(kwargs["metadata"]["discount_value"], "40.00")


# ── OwnerFlashSaleListView ────────────────────────────────────────────────────

class OwnerFlashSaleListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerFlashSaleListView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/flash-sales/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_flash_sales_with_opt_in(self):
        fs = _make_fs(fs_id=5)

        with patch("accounts.models.PlatformFlashSale") as mock_fs_model:
            mock_fs_model.objects.filter.return_value = [fs]
            with patch("accounts.models.PlatformFlashSaleOptIn") as mock_optin:
                mock_optin.objects.filter.return_value.values_list.return_value = [5]
                with patch("django_tenants.utils.schema_context") as mock_ctx:
                    mock_ctx.return_value.__enter__ = lambda s: None
                    mock_ctx.return_value.__exit__ = lambda s, *a: None
                    resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)


# ── OwnerFlashSaleOptInView ───────────────────────────────────────────────────

class OwnerFlashSaleOptInViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerFlashSaleOptInView.as_view()

    def _post(self, fs_id, user=None, tenant=None):
        req = self.factory.post(f"/api/owner/flash-sales/{fs_id}/opt-in/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, fs_id=fs_id)

    def _delete(self, fs_id, user=None, tenant=None):
        req = self.factory.delete(f"/api/owner/flash-sales/{fs_id}/opt-in/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, fs_id=fs_id)

    def test_post_outsider_returns_403(self):
        resp = self._post(1, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_outsider_returns_403(self):
        resp = self._delete(1, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_flash_sale_not_found_returns_404(self):
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.DoesNotExist = Exception
            mock_fs.objects.get.side_effect = mock_fs.DoesNotExist
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._post(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_opt_in_creates_returns_201(self):
        fs = _make_fs(fs_id=3)
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.get.return_value = fs
            with patch("accounts.models.PlatformFlashSaleOptIn") as mock_optin:
                mock_optin.objects.get_or_create.return_value = (MagicMock(), True)
                with patch("django_tenants.utils.schema_context") as mock_ctx:
                    mock_ctx.return_value.__enter__ = lambda s: None
                    mock_ctx.return_value.__exit__ = lambda s, *a: None
                    resp = self._post(3)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["opted_in"])

    def test_post_already_opted_in_returns_200(self):
        fs = _make_fs(fs_id=3)
        with patch("accounts.models.PlatformFlashSale") as mock_fs:
            mock_fs.objects.get.return_value = fs
            with patch("accounts.models.PlatformFlashSaleOptIn") as mock_optin:
                mock_optin.objects.get_or_create.return_value = (MagicMock(), False)
                with patch("django_tenants.utils.schema_context") as mock_ctx:
                    mock_ctx.return_value.__enter__ = lambda s: None
                    mock_ctx.return_value.__exit__ = lambda s, *a: None
                    resp = self._post(3)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["opted_in"])

    def test_delete_opt_out_returns_200(self):
        with patch("accounts.models.PlatformFlashSaleOptIn") as mock_optin:
            mock_optin.objects.filter.return_value.delete.return_value = (1, {})
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._delete(3)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["opted_in"])

    def test_delete_not_opted_in_returns_404(self):
        with patch("accounts.models.PlatformFlashSaleOptIn") as mock_optin:
            mock_optin.objects.filter.return_value.delete.return_value = (0, {})
            with patch("django_tenants.utils.schema_context") as mock_ctx:
                mock_ctx.return_value.__enter__ = lambda s: None
                mock_ctx.return_value.__exit__ = lambda s, *a: None
                resp = self._delete(3)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
