"""Run 8 G3b W10 — AdminConsole backend slices (A2-46 / A2-47).

Unit-level (SimpleTestCase + mocks — no real DB), same style as
tests/test_admin_delivery_views.py.

Covered here:
- A2-47: ProvisioningJobSerializer exposes `lead_id` (the console's Retry
  re-runs the existing PUT /lead-provision/{lead_id}/ path for that lead).
- A2-47: ProvisioningJobViewSet.list keeps the bare-array shape but returns
  the true total in the X-Total-Count header, so the console metric stops
  showing the capped length as the total.

NOT covered here (needs a tenant schema + Order rows — staging check):
- A2-46: AdminTenantLiveOrdersView returns the true active count
  (`active_order_count` from a COUNT before the [:200] slice, plus
  `capped` / `limit`). Verify at staging with a tenant holding >200 active
  orders: count must exceed 200 while results stays at 200.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from sales.serializers import ProvisioningJobSerializer
from sales.views import ProvisioningJobViewSet


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


class _FakeQS(list):
    """A list that also answers .count() like a queryset."""

    def __init__(self, items, total):
        super().__init__(items)
        self._total = total

    def count(self):
        return self._total

    def __getitem__(self, key):
        if isinstance(key, slice):
            return list.__getitem__(self, key)
        return list.__getitem__(self, key)


def _fake_serializer(self, queryset, many=True):
    m = MagicMock()
    m.data = [{"id": getattr(o, "id", None)} for o in queryset]
    return m


class ProvisioningJobSerializerTests(SimpleTestCase):
    def test_fields_include_lead_id(self):
        self.assertIn("lead_id", ProvisioningJobSerializer.Meta.fields)
        self.assertIn("lead_name", ProvisioningJobSerializer.Meta.fields)


class ProvisioningJobViewSetListTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ProvisioningJobViewSet.as_view({"get": "list"})

    def _get(self, query=""):
        req = self.factory.get("/api/provision-jobs/" + query)
        req.user = _admin()
        return self.view(req)

    def test_list_returns_total_count_header_and_caps_rows(self):
        rows = [SimpleNamespace(id=i) for i in range(1, 6)]
        fake_qs = _FakeQS(rows, total=5)
        with (
            patch.object(ProvisioningJobViewSet, "get_queryset", return_value=fake_qs),
            patch.object(ProvisioningJobViewSet, "get_serializer", _fake_serializer),
        ):
            res = self._get("?limit=2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)  # capped at ?limit=2
        self.assertEqual(res["X-Total-Count"], "5")  # true total, not the capped length

    def test_list_default_limit_header(self):
        rows = [SimpleNamespace(id=i) for i in range(1, 6)]
        fake_qs = _FakeQS(rows, total=5)
        with (
            patch.object(ProvisioningJobViewSet, "get_queryset", return_value=fake_qs),
            patch.object(ProvisioningJobViewSet, "get_serializer", _fake_serializer),
        ):
            res = self._get()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["X-Total-Count"], "5")
