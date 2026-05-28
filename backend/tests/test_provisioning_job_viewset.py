"""
Tests for ProvisioningJobViewSet — GET /api/admin/provisioning-jobs/

Covers: permission check, list, limit param (default/min/max).
All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.views import ProvisioningJobViewSet


# ── Helpers ───────────────────────────────────────────────────────────────────

def _admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    u.pk = 1
    u.id = 1
    return u


def _non_admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_platform_admin = False
    u.is_superuser = False
    u.is_staff = False
    return u


def _job_stub(job_id=1):
    tenant = type("T", (), {"slug": "demo"})()
    lead = type("L", (), {"name": "Café Test"})()
    from datetime import datetime, timezone
    now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    return type(
        "Job",
        (),
        {
            "pk": job_id,
            "id": job_id,
            "tenant": tenant,
            "lead": lead,
            "status": "success",
            "log": "All good",
            "created_at": now,
            "updated_at": now,
        },
    )()


def _make_qs(items):
    """Mock queryset that supports slicing and tracks __getitem__ calls."""
    qs = MagicMock()
    qs.order_by.return_value = qs
    qs.__getitem__ = MagicMock(return_value=items)
    return qs


# ── Tests ─────────────────────────────────────────────────────────────────────

class ProvisioningJobViewSetTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ProvisioningJobViewSet.as_view({"get": "list"})

    def _get(self, user=None, params=None):
        req = self.factory.get("/api/admin/provisioning-jobs/", params or {})
        req.user = user or _admin()
        return self.view(req)

    def _patched_get(self, jobs=None, params=None, user=None):
        jobs = jobs if jobs is not None else []
        qs = _make_qs(jobs)
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = [{"id": j.id} for j in jobs]
                return self._get(user=user, params=params)

    def test_non_admin_returns_403(self):
        resp = self._get(user=_non_admin())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_returns_403(self):
        u = MagicMock()
        u.is_authenticated = False
        resp = self._get(user=u)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_returns_200(self):
        resp = self._patched_get(jobs=[_job_stub(1), _job_stub(2)])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_default_limit_is_100(self):
        """Without limit param the queryset is sliced with [:100]."""
        qs = _make_qs([])
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = []
                self._get()
        qs.__getitem__.assert_called_once_with(slice(None, 100, None))

    def test_custom_limit_respected(self):
        qs = _make_qs([])
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = []
                self._get(params={"limit": "25"})
        qs.__getitem__.assert_called_once_with(slice(None, 25, None))

    def test_limit_clamped_to_max_500(self):
        qs = _make_qs([])
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = []
                self._get(params={"limit": "9999"})
        qs.__getitem__.assert_called_once_with(slice(None, 500, None))

    def test_limit_clamped_to_min_1(self):
        qs = _make_qs([])
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = []
                self._get(params={"limit": "0"})
        qs.__getitem__.assert_called_once_with(slice(None, 1, None))

    def test_non_numeric_limit_uses_default(self):
        qs = _make_qs([])
        with patch.object(ProvisioningJobViewSet, "get_queryset", return_value=qs):
            with patch("sales.views.ProvisioningJobSerializer") as mock_ser:
                mock_ser.return_value.data = []
                self._get(params={"limit": "abc"})
        qs.__getitem__.assert_called_once_with(slice(None, 100, None))
