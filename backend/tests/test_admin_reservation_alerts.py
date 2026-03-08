from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import AdminReservationAlertsView


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _admin_user():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True)


def _non_admin_user():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=False)


def _lead_row(*, lead_id=1, tenant_slug="demo", created_at=None):
    created = created_at or datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
    return type(
        "LeadRow",
        (),
        {
            "id": lead_id,
            "pk": lead_id,
            "name": f"Lead {lead_id}",
            "email": "lead@example.com",
            "phone": "+212600000000",
            "source": "table_reservation",
            "status": "new",
            "notes": "Reservation request",
            "tenant": type("TenantStub", (), {"slug": tenant_slug})(),
            "plan": None,
            "created_at": created,
            "updated_at": created,
            "archived_at": None,
            "onboarded_at": None,
        },
    )()


class AdminReservationAlertsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminReservationAlertsView.as_view()

    @patch("sales.views.reservation_due_soon_cutoff")
    @patch("sales.views.reservation_overdue_cutoff")
    @patch("sales.views.schema_context")
    @patch("sales.views.Lead.objects")
    def test_returns_alert_payload(
        self,
        lead_objects,
        schema_context_mock,
        overdue_cutoff_mock,
        due_soon_cutoff_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        overdue_cutoff_mock.return_value = "overdue_cutoff"
        due_soon_cutoff_mock.return_value = "due_soon_cutoff"

        scope = Mock(name="scope")
        lead_objects.filter.return_value = scope
        scope.select_related.return_value = scope
        scope.annotate.return_value = scope

        overdue_queryset = Mock(name="overdue_queryset")
        due_soon_queryset = Mock(name="due_soon_queryset")
        alert_queryset = Mock(name="alert_queryset")
        scope.filter.side_effect = [overdue_queryset, due_soon_queryset, alert_queryset]

        overdue_queryset.count.return_value = 2
        due_soon_queryset.count.return_value = 1
        alert_queryset.order_by.return_value = [
            _lead_row(lead_id=10, tenant_slug="demo"),
            _lead_row(lead_id=9, tenant_slug="demo"),
        ]

        request = self.factory.get("/api/admin-reservation-alerts/?limit=5")
        force_authenticate(request, user=_admin_user())
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["filters"]["state"], "all")
        self.assertEqual(response.data["filters"]["limit"], 5)
        self.assertEqual(response.data["counts"]["overdue"], 2)
        self.assertEqual(response.data["counts"]["due_soon"], 1)
        self.assertEqual(response.data["counts"]["total_alerts"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["id"], 10)
        self.assertIn("sla_state", response.data["results"][0])
        self.assertIn("reminder_count", response.data["results"][0])

        lead_objects.filter.assert_called_once_with(
            source__in=("table_reservation", "reservation", "reserve_table"),
            status="new",
            archived_at__isnull=True,
        )

    @patch("sales.views.reservation_due_soon_cutoff")
    @patch("sales.views.reservation_overdue_cutoff")
    @patch("sales.views.schema_context")
    @patch("sales.views.Lead.objects")
    def test_filters_due_soon_state_and_tenant(
        self,
        lead_objects,
        schema_context_mock,
        overdue_cutoff_mock,
        due_soon_cutoff_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        overdue_cutoff_mock.return_value = "overdue_cutoff"
        due_soon_cutoff_mock.return_value = "due_soon_cutoff"

        root_scope = Mock(name="root_scope")
        tenant_scope = Mock(name="tenant_scope")
        lead_objects.filter.return_value = root_scope
        root_scope.select_related.return_value = root_scope
        root_scope.annotate.return_value = root_scope
        root_scope.filter.return_value = tenant_scope

        overdue_queryset = Mock(name="overdue_queryset")
        due_soon_queryset = Mock(name="due_soon_queryset")
        tenant_scope.filter.side_effect = [overdue_queryset, due_soon_queryset]
        overdue_queryset.count.return_value = 0
        due_soon_queryset.count.return_value = 2
        due_soon_queryset.order_by.return_value = [
            _lead_row(lead_id=5, tenant_slug="demo"),
            _lead_row(lead_id=4, tenant_slug="demo"),
        ]

        request = self.factory.get("/api/admin-reservation-alerts/?state=due_soon&tenant=demo")
        force_authenticate(request, user=_admin_user())
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["filters"]["state"], "due_soon")
        self.assertEqual(response.data["filters"]["tenant"], "demo")
        self.assertEqual(response.data["counts"]["overdue"], 0)
        self.assertEqual(response.data["counts"]["due_soon"], 2)
        self.assertEqual(len(response.data["results"]), 2)
        root_scope.filter.assert_called_once_with(tenant__slug="demo")

    def test_rejects_invalid_state(self):
        request = self.factory.get("/api/admin-reservation-alerts/?state=wrong")
        force_authenticate(request, user=_admin_user())
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_platform_admin(self):
        request = self.factory.get("/api/admin-reservation-alerts/")
        force_authenticate(request, user=_non_admin_user())
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
