"""
Tests for admin delivery-related views:
  - AdminDeliveryZoneListCreateView  GET/POST /api/admin/delivery-zones/
  - AdminDeliveryZoneDetailView      GET/PATCH/DELETE /api/admin/delivery-zones/<id>/
  - AdminDriverListView              GET /api/admin/drivers/
  - AdminPlatformAnalyticsView       GET /api/admin/platform-analytics/
  - AdminDeliveryJobListView         GET /api/admin/delivery-jobs/
  - OwnerDeliveryZoneView            GET /api/owner/delivery-zone/
  - OwnerDeliveryRadiusUpdateView    PATCH /api/owner/delivery-radius/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    AdminDeliveryZoneListCreateView,
    AdminDeliveryZoneDetailView,
    AdminDriverListView,
    AdminPlatformAnalyticsView,
    AdminDeliveryJobListView,
    OwnerDeliveryZoneView,
    OwnerDeliveryRadiusUpdateView,
)
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


def _tenant(tenant_id=1, schema_name="tenant1"):
    return SimpleNamespace(id=tenant_id, schema_name=schema_name)


def _make_zone(zone_id=1):
    z = MagicMock()
    z.id = zone_id
    z.name = "Downtown"
    z.city = "Casablanca"
    z.polygon = [{"lat": 33.5, "lng": -7.6}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}]
    z.center_lat = 33.55
    z.center_lng = -7.55
    z.approx_radius_km = 5.0
    z.is_active = True
    z.fee_tiers = []
    z.created_at = MagicMock()
    z.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return z


def _sc_mock():
    """schema_context mock for use in with statements."""
    ctx = MagicMock()
    ctx.__enter__ = lambda s: None
    ctx.__exit__ = lambda s, *a: None
    return ctx


# ── AdminDeliveryZoneListCreateView ───────────────────────────────────────────

class AdminDeliveryZoneListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryZoneListCreateView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/admin/delivery-zones/")
        req.user = user or _admin()
        return req

    def _post(self, data, user=None):
        req = self.factory.post("/api/admin/delivery-zones/", data, format="json")
        req.user = user or _admin()
        return req

    def test_get_non_admin_returns_403(self):
        req = self._get(user=_non_admin())
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_non_admin_returns_403(self):
        req = self._post({"name": "Zone"}, user=_non_admin())
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_missing_name_returns_400(self):
        req = self._post({
            "city": "Casablanca",
            "polygon": [{"lat": 33.5, "lng": -7.6}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}],
        })
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_polygon_returns_400(self):
        req = self._post({
            "name": "Zone",
            "city": "Casablanca",
            "polygon": [{"lat": 33.5, "lng": -7.6}],  # < 3 points
        })
        with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_returns_list(self):
        zone = _make_zone()
        req = self._get()
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.objects.all.return_value = [zone]
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", side_effect=lambda z: {"id": z.id}):
                    resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    def test_post_creates_zone_returns_201(self):
        zone = _make_zone()
        req = self._post({
            "name": "Downtown",
            "city": "Casablanca",
            "polygon": [{"lat": 33.5, "lng": -7.6}, {"lat": 33.6, "lng": -7.5}, {"lat": 33.5, "lng": -7.5}],
        })
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.objects.create.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", side_effect=lambda z: {"id": z.id}):
                    resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ── AdminDeliveryZoneDetailView ───────────────────────────────────────────────

class AdminDeliveryZoneDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryZoneDetailView.as_view()

    def _get(self, zone_id, user=None):
        req = self.factory.get(f"/api/admin/delivery-zones/{zone_id}/")
        req.user = user or _admin()
        return self.view(req, zone_id=zone_id)

    def _patch(self, zone_id, data, user=None):
        req = self.factory.patch(f"/api/admin/delivery-zones/{zone_id}/", data, format="json")
        req.user = user or _admin()
        return self.view(req, zone_id=zone_id)

    def _delete(self, zone_id, user=None):
        req = self.factory.delete(f"/api/admin/delivery-zones/{zone_id}/")
        req.user = user or _admin()
        return self.view(req, zone_id=zone_id)

    def test_get_non_admin_returns_403(self):
        resp = self._get(1, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_non_admin_returns_403(self):
        resp = self._delete(1, user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_not_found_returns_404(self):
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.DoesNotExist = Exception
            mock_dz.objects.get.side_effect = mock_dz.DoesNotExist
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._get(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_not_found_returns_404(self):
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.DoesNotExist = Exception
            mock_dz.objects.get.side_effect = mock_dz.DoesNotExist
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._delete(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_returns_zone(self):
        zone = _make_zone()
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.objects.get.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", return_value={"id": 1}):
                    resp = self._get(1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_patch_updates_name_returns_200(self):
        zone = _make_zone()
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.objects.get.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                with patch("accounts.views._serialize_zone", return_value={"id": 1}):
                    resp = self._patch(1, {"name": "Uptown"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        zone.save.assert_called_once()

    def test_delete_returns_204(self):
        zone = _make_zone()
        with patch("accounts.models.DeliveryZone") as mock_dz:
            mock_dz.objects.get.return_value = zone
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._delete(1)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


# ── AdminDriverListView ───────────────────────────────────────────────────────

class AdminDriverListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverListView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/admin/drivers/")
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_empty_list_when_no_drivers(self):
        with patch("accounts.models.Customer") as mock_cust:
            mock_cust.objects.filter.return_value.order_by.return_value = []
            with patch("accounts.models.DeliveryJob") as mock_dj:
                resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_returns_driver_list(self):
        driver = MagicMock()
        driver.id = 1
        driver.name = "Ali"
        driver.phone = "0612345678"
        driver.email = "ali@example.com"
        driver.is_driver_online = True
        driver.driver_lat = 33.5
        driver.driver_lng = -7.6
        driver.driver_position_updated_at = None
        driver.created_at = MagicMock()
        driver.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("accounts.models.Customer") as mock_cust:
            mock_cust.objects.filter.return_value.order_by.return_value = [driver]
            with patch("accounts.models.DeliveryJob") as mock_dj, \
                 patch("accounts.models.DriverPayout") as mock_dp:
                mock_dj.objects.filter.return_value.values.return_value.annotate.return_value = []
                mock_dp.objects.filter.return_value.values.return_value.annotate.return_value = []
                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "Ali")

    def test_response_shape(self):
        driver = MagicMock()
        driver.id = 1
        driver.name = "Ali"
        driver.phone = "0612345678"
        driver.email = "ali@example.com"
        driver.is_driver_online = False
        driver.driver_lat = None
        driver.driver_lng = None
        driver.driver_position_updated_at = None
        driver.created_at = MagicMock()
        driver.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("accounts.models.Customer") as mock_cust:
            mock_cust.objects.filter.return_value.order_by.return_value = [driver]
            with patch("accounts.models.DeliveryJob") as mock_dj, \
                 patch("accounts.models.DriverPayout") as mock_dp:
                mock_dj.objects.filter.return_value.values.return_value.annotate.return_value = []
                mock_dp.objects.filter.return_value.values.return_value.annotate.return_value = []
                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        d = resp.data[0]
        for field in ("id", "name", "phone", "email", "is_online", "driver_lat", "driver_lng",
                      "total_jobs", "completed_jobs", "avg_rating"):
            self.assertIn(field, d, f"Missing field: {field}")


# ── AdminPlatformAnalyticsView ────────────────────────────────────────────────

class AdminPlatformAnalyticsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminPlatformAnalyticsView.as_view()

    def _get(self, user=None):
        req = self.factory.get("/api/admin/platform-analytics/")
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_analytics_structure(self):
        _zero_agg = {"total": 0, "delivered": 0, "failed": 0, "active": 0, "searching": 0,
                     "avg_rating": None, "total_fees": None, "total_payouts": None}
        _zero_zone = {"total": 0, "active": 0}
        _zero_fs = {"total": 0, "active": 0, "total_redemptions": None}
        _zero_wallet = {"total_balance": None}
        _zero_txn = {"total": 0, "total_bonus": None, "total_payments": None}

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.all.return_value.count.return_value = 5
            mock_tenant.objects.all.return_value.filter.return_value.count.return_value = 3

            with patch("accounts.models.Customer") as mock_cust:
                mock_cust.objects.count.return_value = 100
                mock_cust.objects.filter.return_value.aggregate.return_value = {
                    "total": 10, "online": 2, "total_balance": None
                }
                mock_cust.objects.aggregate.return_value = {"total_balance": None}

                with patch("accounts.models.DeliveryJob") as mock_dj:
                    mock_dj.objects.aggregate.return_value = _zero_agg
                    mock_dj.objects.exclude.return_value.count.return_value = 0

                    with patch("accounts.models.DeliveryZone") as mock_dz:
                        mock_dz.objects.aggregate.return_value = _zero_zone

                        with patch("accounts.models.PlatformFlashSale") as mock_fs:
                            mock_fs.objects.aggregate.return_value = _zero_fs

                            with patch("accounts.models.WalletTransaction") as mock_wt, \
                                 patch("accounts.models.DriverPayout") as mock_dp:
                                mock_wt.objects.aggregate.return_value = _zero_txn
                                mock_dp.objects.aggregate.return_value = {"s": None}

                                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for section in ("tenants", "customers", "deliveries", "zones", "flash_sales", "wallet"):
            self.assertIn(section, resp.data, f"Missing section: {section}")


# ── AdminDeliveryJobListView ──────────────────────────────────────────────────

class AdminDeliveryJobListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryJobListView.as_view()

    def _get(self, user=None, params=None):
        url = "/api/admin/delivery-jobs/"
        req = self.factory.get(url, params or {})
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_empty_list(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            qs = MagicMock()
            mock_dj.objects.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: []
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_status_filter_applied(self):
        with patch("accounts.models.DeliveryJob") as mock_dj:
            qs = MagicMock()
            mock_dj.objects.select_related.return_value.order_by.return_value = qs
            filtered_qs = MagicMock()
            qs.filter.return_value = filtered_qs
            filtered_qs.filter.return_value = filtered_qs
            filtered_qs.__getitem__ = lambda s, k: []
            with patch("accounts.views._serialize_delivery_job", return_value={}):
                resp = self._get(params={"status": "assigned"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        qs.filter.assert_called()


# ── OwnerDeliveryZoneView ─────────────────────────────────────────────────────

class OwnerDeliveryZoneViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDeliveryZoneView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/delivery-zone/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_zone_returns_null(self):
        profile = MagicMock()
        profile.delivery_zone_id = None
        profile.delivery_radius_km = 5.0

        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = profile
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["zone"])
        self.assertEqual(resp.data["delivery_radius_km"], 5.0)

    def test_with_zone_returns_zone_data(self):
        profile = MagicMock()
        profile.delivery_zone_id = 1
        profile.delivery_radius_km = 3.0

        zone = _make_zone()

        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = profile
            with patch("accounts.models.DeliveryZone") as mock_dz:
                mock_dz.objects.get.return_value = zone
                mock_dz.DoesNotExist = Exception
                with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                    with patch("accounts.views._serialize_zone", return_value={"id": 1}):
                        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data["zone"])


# ── OwnerDeliveryRadiusUpdateView ─────────────────────────────────────────────

class OwnerDeliveryRadiusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDeliveryRadiusUpdateView.as_view()

    def _patch(self, data, user=None, tenant=None):
        req = self.factory.patch("/api/owner/delivery-radius/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._patch({"delivery_radius_km": 5.0}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_negative_radius_returns_400(self):
        resp = self._patch({"delivery_radius_km": -1.0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_radius_returns_400(self):
        resp = self._patch({"delivery_radius_km": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_radius_returns_200(self):
        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.update.return_value = 1
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._patch({"delivery_radius_km": 10.0})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["delivery_radius_km"], 10.0)

    def test_zero_radius_returns_none(self):
        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.update.return_value = 1
            with patch("django_tenants.utils.schema_context", return_value=_sc_mock()):
                resp = self._patch({"delivery_radius_km": 0})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["delivery_radius_km"])
