from datetime import date, datetime, timezone
from unittest.mock import ANY, Mock, patch

from django.test import SimpleTestCase
from django.http import Http404
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import (
    OwnerReservationBulkReminderView,
    OwnerReservationBulkReminderResultView,
    OwnerReservationBulkStatusView,
    OwnerReservationDetailView,
    OwnerReservationExportView,
    OwnerReservationListView,
    OwnerReservationReminderView,
    OwnerReservationReminderResultView,
)


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _owner_user(tenant_id=10):
    user = Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=False)
    user.role = "tenant_owner"
    user.tenant_id = tenant_id
    user.pk = 1
    return user


def _lead_row(*, lead_id=7, status_value="new", created_at=None):
    created = created_at or datetime(2026, 3, 7, tzinfo=timezone.utc)
    return type(
        "LeadRow",
        (),
        {
            "id": lead_id,
            "pk": lead_id,
            "name": "Demo",
            "email": "owner@example.com",
            "phone": "+212600000000",
            "source": "table_reservation",
            "status": status_value,
            "notes": "Party size: 4",
            "tenant": type("TenantStub", (), {"slug": "demo"})(),
            "created_at": created,
            "updated_at": created,
        },
    )()


class OwnerReservationListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationListView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views._owner_reservations_queryset")
    def test_returns_paginated_reservations_with_counts(self, queryset_builder_mock, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()

        main_queryset = Mock()
        main_queryset.count.return_value = 3
        main_queryset.order_by.return_value = [
            _lead_row(lead_id=9, status_value="new"),
            _lead_row(lead_id=8, status_value="new"),
            _lead_row(lead_id=7, status_value="new"),
        ]

        total_queryset = Mock()
        total_queryset.count.return_value = 12
        new_queryset = Mock()
        new_queryset.count.return_value = 5
        contacted_queryset = Mock()
        contacted_queryset.count.return_value = 3
        won_queryset = Mock()
        won_queryset.count.return_value = 2
        lost_queryset = Mock()
        lost_queryset.count.return_value = 2
        overdue_queryset = Mock()
        overdue_queryset.filter.return_value = overdue_queryset
        overdue_queryset.count.return_value = 4

        queryset_builder_mock.side_effect = [
            main_queryset,
            total_queryset,
            new_queryset,
            contacted_queryset,
            won_queryset,
            lost_queryset,
            overdue_queryset,
        ]

        request = self.factory.get(
            "/api/owner/reservations/?status=new&q=demo&from=2026-03-01&to=2026-03-07&page=1&page_size=2"
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["pagination"]["total"], 3)
        self.assertEqual(response.data["pagination"]["page"], 1)
        self.assertEqual(response.data["pagination"]["pages"], 2)
        self.assertTrue(response.data["pagination"]["has_next"])
        self.assertEqual(response.data["counts"]["total"], 12)
        self.assertEqual(response.data["counts"]["new"], 5)
        self.assertEqual(response.data["counts"]["overdue_new"], 4)
        self.assertEqual(response.data["counts"]["contacted"], 3)
        self.assertEqual(response.data["counts"]["won"], 2)
        self.assertEqual(response.data["counts"]["lost"], 2)
        first_row = response.data["results"][0]
        self.assertIn("follow_up_due_at", first_row)
        self.assertIn("sla_state", first_row)
        self.assertIn("sla_minutes_overdue", first_row)
        self.assertIn("last_reminder_status", first_row)
        self.assertIn("last_reminder_at", first_row)
        self.assertIn("reminder_count", first_row)
        self.assertIn("reminder_opened_count", first_row)
        self.assertIn("reminder_failed_count", first_row)

        queryset_builder_mock.assert_any_call(
            10,
            status_filter="new",
            reminder_filter="",
            search="demo",
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 7),
        )

    def test_returns_403_when_tenant_missing(self):
        request = self.factory.get("/api/owner/reservations/")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_invalid_status_filter(self):
        request = self.factory.get("/api/owner/reservations/?status=live")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_reminder_filter(self):
        request = self.factory.get("/api/owner/reservations/?reminder_status=bad")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_date_filter(self):
        request = self.factory.get("/api/owner/reservations/?from=2026-99-01")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("sales.views.schema_context")
    @patch("sales.views._owner_reservations_queryset")
    def test_applies_reminder_filter(self, queryset_builder_mock, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        querysets = []
        for _ in range(7):
            queryset = Mock()
            queryset.count.return_value = 0
            queryset.order_by.return_value = []
            queryset.filter.return_value = queryset
            querysets.append(queryset)
        queryset_builder_mock.side_effect = querysets

        request = self.factory.get("/api/owner/reservations/?reminder_status=failed")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset_builder_mock.assert_any_call(
            10,
            status_filter="",
            reminder_filter="failed",
            search="",
            from_date=None,
            to_date=None,
        )


class OwnerReservationDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationDetailView.as_view()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_updates_reservation_status(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        lead.save = Mock()
        get_object_or_404_mock.return_value = lead

        request = self.factory.put("/api/owner/reservations/7/", {"status": "contacted"}, format="json")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))

        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "contacted")
        lead.save.assert_called_once_with(update_fields=["status", "updated_at"])
        timeline_log_mock.assert_called_once()
        get_object_or_404_mock.assert_called_once_with(
            ANY,
            pk=7,
            tenant_id=10,
            source__in=("table_reservation", "reservation", "reserve_table"),
            archived_at__isnull=True,
        )

    @patch("sales.views.get_object_or_404")
    def test_rejects_invalid_status(self, get_object_or_404_mock):
        request = self.factory.put("/api/owner/reservations/7/", {"status": "live"}, format="json")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        get_object_or_404_mock.assert_not_called()


class OwnerReservationBulkStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationBulkStatusView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views.ReservationTimelineEvent.objects")
    @patch("sales.views.Lead.objects")
    def test_bulk_status_updates_selected_reservations(self, lead_objects, timeline_objects, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()

        queryset = Mock()
        lead_one = Mock(id=7, status="new")
        lead_two = Mock(id=9, status="new")
        lead_three = Mock(id=11, status="contacted")
        queryset.only.return_value = [lead_one, lead_two, lead_three]
        queryset.filter.return_value = queryset
        queryset.update.return_value = 2
        lead_objects.filter.return_value = queryset

        request = self.factory.post(
            "/api/owner/reservations/bulk-status/",
            {"ids": [7, 9, 11], "status": "contacted"},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)
        self.assertEqual(response.data["status"], "contacted")
        self.assertEqual(response.data["ids"], [7, 9, 11])
        self.assertEqual(response.data["missing_ids"], [])
        timeline_objects.bulk_create.assert_called_once()
        lead_objects.filter.assert_called_once_with(
            id__in=[7, 9, 11],
            tenant_id=10,
            source__in=("table_reservation", "reservation", "reserve_table"),
            archived_at__isnull=True,
        )

    @patch("sales.views.Lead.objects")
    def test_bulk_status_rejects_invalid_payload(self, lead_objects):
        request = self.factory.post(
            "/api/owner/reservations/bulk-status/",
            {"ids": [], "status": "live"},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        lead_objects.filter.assert_not_called()


class OwnerReservationBulkReminderViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationBulkReminderView.as_view()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.ReservationReminder.objects.create")
    @patch("sales.views._with_reservation_reminder_metrics")
    @patch("sales.views.schema_context")
    @patch("sales.views.Lead.objects")
    def test_prepares_bulk_reminders_with_failed_filter(
        self,
        lead_objects,
        schema_context_mock,
        reminder_metrics_mock,
        reminder_create_mock,
        timeline_log_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        lead_objects.filter.return_value = Mock()
        lead_failed = _lead_row(lead_id=7, status_value="new")
        lead_failed.last_reminder_status = "failed"
        lead_opened = _lead_row(lead_id=9, status_value="new")
        lead_opened.last_reminder_status = "opened"
        reminder_metrics_mock.return_value = [lead_failed, lead_opened]
        reminder_create_mock.return_value = Mock(id=51)

        request = self.factory.post(
            "/api/owner/reservations/bulk-reminder/",
            {"ids": [7, 9, 11], "require_failed_last_reminder": True},
            format="json",
        )
        request.tenant = Mock(id=10, name="Demo Resto")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["prepared_count"], 1)
        self.assertEqual(response.data["ids"], [7, 9])
        self.assertEqual(response.data["missing_ids"], [11])
        self.assertEqual(response.data["skipped_not_failed_ids"], [9])
        self.assertEqual(response.data["skipped_unavailable_ids"], [])
        self.assertEqual(response.data["skipped_no_phone_ids"], [])
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["lead_id"], 7)
        reminder_create_mock.assert_called_once()
        timeline_log_mock.assert_called_once()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.ReservationReminder.objects.create")
    @patch("sales.views._with_reservation_reminder_metrics")
    @patch("sales.views.schema_context")
    @patch("sales.views.Lead.objects")
    def test_skips_unavailable_and_no_phone(
        self,
        lead_objects,
        schema_context_mock,
        reminder_metrics_mock,
        reminder_create_mock,
        timeline_log_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        lead_objects.filter.return_value = Mock()
        lead_lost = _lead_row(lead_id=7, status_value="lost")
        lead_lost.last_reminder_status = ""
        lead_no_phone = _lead_row(lead_id=9, status_value="new")
        lead_no_phone.phone = ""
        lead_no_phone.last_reminder_status = "failed"
        reminder_metrics_mock.return_value = [lead_lost, lead_no_phone]

        request = self.factory.post(
            "/api/owner/reservations/bulk-reminder/",
            {"ids": [7, 9]},
            format="json",
        )
        request.tenant = Mock(id=10, name="Demo Resto")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["prepared_count"], 0)
        self.assertEqual(response.data["skipped_unavailable_ids"], [7])
        self.assertEqual(response.data["skipped_no_phone_ids"], [9])
        reminder_create_mock.assert_not_called()
        timeline_log_mock.assert_not_called()


class OwnerReservationBulkReminderResultViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationBulkReminderResultView.as_view()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_updates_multiple_reminder_outcomes(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead_one = _lead_row(lead_id=7, status_value="new")
        lead_two = _lead_row(lead_id=9, status_value="new")
        reminder_one = Mock(id=51, status="sent", failure_reason="")
        reminder_one.save = Mock()
        reminder_two = Mock(id=52, status="sent", failure_reason="")
        reminder_two.save = Mock()
        get_object_or_404_mock.side_effect = [lead_one, reminder_one, lead_two, reminder_two]

        request = self.factory.post(
            "/api/owner/reservations/bulk-reminder-result/",
            {
                "items": [
                    {"lead_id": 7, "reminder_id": 51, "status": "opened"},
                    {"lead_id": 9, "reminder_id": 52, "status": "failed", "error": "Manual send skipped"},
                ]
            },
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)
        self.assertEqual(response.data["missing_count"], 0)
        reminder_one.save.assert_called_once_with(update_fields=["status", "failure_reason", "updated_at"])
        reminder_two.save.assert_called_once_with(update_fields=["status", "failure_reason", "updated_at"])
        self.assertEqual(reminder_two.failure_reason, "Manual send skipped")
        self.assertEqual(timeline_log_mock.call_count, 2)

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_reports_missing_pairs(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(lead_id=7, status_value="new")
        reminder = Mock(id=51, status="sent", failure_reason="")
        reminder.save = Mock()
        get_object_or_404_mock.side_effect = [Http404(), lead, reminder]

        request = self.factory.post(
            "/api/owner/reservations/bulk-reminder-result/",
            {
                "items": [
                    {"lead_id": 99, "reminder_id": 999, "status": "opened"},
                    {"lead_id": 7, "reminder_id": 51, "status": "opened"},
                ]
            },
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 1)
        self.assertEqual(response.data["missing_count"], 1)
        self.assertEqual(response.data["missing"][0]["lead_id"], 99)
        timeline_log_mock.assert_called_once()


class OwnerReservationExportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationExportView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views._owner_reservations_queryset")
    def test_exports_csv(self, queryset_builder_mock, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()

        queryset = Mock()
        queryset.order_by.return_value = [_lead_row(status_value="contacted")]
        queryset_builder_mock.return_value = queryset

        request = self.factory.get("/api/owner/reservations/export/?status=contacted&q=demo&from=2026-03-01&to=2026-03-07")
        request.tenant = Mock(id=10, slug="demo")
        force_authenticate(request, user=_owner_user(tenant_id=10))

        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertIn("id,created_at,status,name,phone,email,source,notes", body)
        self.assertIn("Demo", body)
        queryset_builder_mock.assert_called_once_with(
            10,
            status_filter="contacted",
            reminder_filter="",
            search="demo",
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 7),
        )

    def test_rejects_invalid_date(self):
        request = self.factory.get("/api/owner/reservations/export/?to=bad-date")
        request.tenant = Mock(id=10, slug="demo")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_reminder_filter(self):
        request = self.factory.get("/api/owner/reservations/export/?reminder_status=bad")
        request.tenant = Mock(id=10, slug="demo")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OwnerReservationTimelineViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        from sales.views import OwnerReservationTimelineView

        self.view = OwnerReservationTimelineView.as_view()

    @patch("sales.views.schema_context")
    @patch("sales.views.ReservationTimelineEvent.objects")
    @patch("sales.views.get_object_or_404")
    def test_lists_timeline_events(self, get_object_or_404_mock, timeline_objects, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        get_object_or_404_mock.return_value = lead
        event = type(
            "TimelineEvent",
            (),
            {
                "id": 1,
                "action": "note",
                "note": "Called customer.",
                "previous_status": "",
                "new_status": "",
                "actor": type("Actor", (), {"username": "owner"})(),
                "created_at": datetime(2026, 3, 7, tzinfo=timezone.utc),
            },
        )()
        timeline_queryset = Mock()
        timeline_queryset.select_related.return_value = timeline_queryset
        timeline_queryset.order_by.return_value = [event]
        timeline_objects.filter.return_value = timeline_queryset

        request = self.factory.get("/api/owner/reservations/7/timeline/?limit=20")
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["action"], "note")

    @patch("sales.views.schema_context")
    @patch("sales.views.ReservationTimelineEvent.objects")
    @patch("sales.views.get_object_or_404")
    def test_creates_timeline_note(self, get_object_or_404_mock, timeline_objects, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        get_object_or_404_mock.return_value = lead
        created = type(
            "TimelineEvent",
            (),
            {
                "id": 3,
                "action": "note",
                "note": "Customer asked for 20:00.",
                "previous_status": "",
                "new_status": "",
                "actor": type("Actor", (), {"username": "owner"})(),
                "created_at": datetime(2026, 3, 7, tzinfo=timezone.utc),
            },
        )()
        timeline_objects.create.return_value = created

        request = self.factory.post(
            "/api/owner/reservations/7/timeline/",
            {"note": "Customer asked for 20:00."},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["note"], "Customer asked for 20:00.")

    def test_rejects_empty_note(self):
        request = self.factory.post(
            "/api/owner/reservations/7/timeline/",
            {"note": ""},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OwnerReservationReminderViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationReminderView.as_view()

    @patch("sales.views.ReservationReminder.objects.create")
    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_returns_whatsapp_reminder_payload(
        self,
        get_object_or_404_mock,
        schema_context_mock,
        timeline_log_mock,
        reminder_create_mock,
    ):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        get_object_or_404_mock.return_value = lead
        created_at = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
        reminder = type(
            "Reminder",
            (),
            {
                "id": 5,
                "channel": "whatsapp",
                "status": "sent",
                "phone": "212600000000",
                "message": "Hello",
                "whatsapp_link": "https://wa.me/212600000000",
                "failure_reason": "",
                "created_at": created_at,
                "updated_at": created_at,
            },
        )()
        reminder_create_mock.return_value = reminder

        request = self.factory.post("/api/owner/reservations/7/reminder/", {}, format="json")
        request.tenant = Mock(id=10, name="Demo Resto")
        force_authenticate(request, user=_owner_user(tenant_id=10))

        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], 5)
        self.assertEqual(response.data["channel"], "whatsapp")
        self.assertEqual(response.data["status"], "sent")
        timeline_log_mock.assert_called_once()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_rejects_missing_phone(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        lead.phone = ""
        get_object_or_404_mock.return_value = lead

        request = self.factory.post("/api/owner/reservations/7/reminder/", {}, format="json")
        request.tenant = Mock(id=10, name="Demo Resto")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        timeline_log_mock.assert_not_called()


class OwnerReservationReminderResultViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerReservationReminderResultView.as_view()

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_marks_reminder_as_opened(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="new")
        reminder = type(
            "Reminder",
            (),
            {
                "id": 5,
                "status": "sent",
                "failure_reason": "",
                "channel": "whatsapp",
                "phone": "212600000000",
                "message": "Hello",
                "whatsapp_link": "https://wa.me/212600000000",
                "created_at": datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 7, 12, 1, tzinfo=timezone.utc),
            },
        )()
        reminder.save = Mock()
        get_object_or_404_mock.side_effect = [lead, reminder]

        request = self.factory.post(
            "/api/owner/reservations/7/reminder-result/",
            {"reminder_id": 5, "status": "opened"},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "opened")
        reminder.save.assert_called_once_with(update_fields=["status", "failure_reason", "updated_at"])
        timeline_log_mock.assert_called_once()

    @patch("sales.views.schema_context")
    def test_rejects_invalid_status(self, schema_context_mock):
        schema_context_mock.return_value = _passthrough_cm()
        request = self.factory.post(
            "/api/owner/reservations/7/reminder-result/",
            {"reminder_id": 5, "status": "sent"},
            format="json",
        )
        request.tenant = Mock(id=10)
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("sales.views._log_reservation_timeline_event")
    @patch("sales.views.schema_context")
    @patch("sales.views.get_object_or_404")
    def test_rejects_lost_reservation(self, get_object_or_404_mock, schema_context_mock, timeline_log_mock):
        schema_context_mock.return_value = _passthrough_cm()
        lead = _lead_row(status_value="lost")
        get_object_or_404_mock.return_value = lead

        request = self.factory.post("/api/owner/reservations/7/reminder/", {}, format="json")
        request.tenant = Mock(id=10, name="Demo Resto")
        force_authenticate(request, user=_owner_user(tenant_id=10))
        response = self.view(request, lead_id=7)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        timeline_log_mock.assert_not_called()
