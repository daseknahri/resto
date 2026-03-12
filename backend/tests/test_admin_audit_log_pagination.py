from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import AdminAuditLogViewSet


def _admin_user():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True, pk=1, id=1)


def _audit_row(row_id: int):
    actor = type("ActorStub", (), {"username": f"admin{row_id}"})()
    tenant = type("TenantStub", (), {"slug": "demo"})()
    lead = type("LeadStub", (), {"name": f"Lead {row_id}"})()
    created_at = datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc)
    return type(
        "AuditStub",
        (),
        {
            "id": row_id,
            "pk": row_id,
            "action": "lead_provisioned",
            "actor": actor,
            "tenant": tenant,
            "lead": lead,
            "target_repr": f"tenant:demo-{row_id}",
            "ip_address": "127.0.0.1",
            "metadata": {"status": "success"},
            "created_at": created_at,
        },
    )()


class _FakeAuditQuerySet:
    def __init__(self, rows):
        self._rows = list(rows)

    def count(self):
        return len(self._rows)

    def filter(self, *args, **kwargs):
        return self

    def __getitem__(self, item):
        return self._rows[item]


class AdminAuditLogPaginationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminAuditLogViewSet.as_view({"get": "list"})

    def test_returns_paginated_payload(self):
        rows = [_audit_row(idx) for idx in range(1, 76)]
        queryset = _FakeAuditQuerySet(rows)
        request = self.factory.get("/api/admin-audit-logs/?page=2&page_size=25")
        force_authenticate(request, user=_admin_user())

        with patch.object(AdminAuditLogViewSet, "get_queryset", return_value=queryset):
            response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 2)
        self.assertEqual(response.data["pagination"]["page_size"], 25)
        self.assertEqual(response.data["pagination"]["total"], 75)
        self.assertEqual(response.data["pagination"]["total_pages"], 3)
        self.assertTrue(response.data["pagination"]["has_next"])
        self.assertTrue(response.data["pagination"]["has_prev"])
        self.assertEqual(len(response.data["results"]), 25)
        self.assertEqual(response.data["results"][0]["id"], 26)

    def test_clamps_page_size_to_max_limit(self):
        rows = [_audit_row(idx) for idx in range(1, 211)]
        queryset = _FakeAuditQuerySet(rows)
        request = self.factory.get("/api/admin-audit-logs/?page=1&page_size=999")
        force_authenticate(request, user=_admin_user())

        with patch.object(AdminAuditLogViewSet, "get_queryset", return_value=queryset):
            response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page_size"], 200)
        self.assertEqual(response.data["pagination"]["total"], 210)
        self.assertEqual(response.data["pagination"]["total_pages"], 2)
        self.assertTrue(response.data["pagination"]["has_next"])
        self.assertEqual(len(response.data["results"]), 200)
