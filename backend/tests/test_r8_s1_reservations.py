"""
Tests for Run 8 S1-D — reservation reminders (B-06, B-07).

Covered views (backend/sales/views.py):
  - OwnerReservationReminderView        POST /owner/reservations/<id>/reminder/
  - OwnerReservationReminderResultView  POST /owner/reservations/<id>/reminder-result/
  - OwnerReservationBulkReminderView    POST /owner/reservations/bulk-reminder/
  - OwnerReservationBulkReminderResultView POST /owner/reservations/bulk-reminder-result/

B-06 rule pinned here: preparing a reminder records it as PREPARED only
(status "sent" — the server-generated wa.me link was handed to the owner).
Nothing in the prepare path marks a reminder opened/failed, and the timeline
note says "prepared", not "sent".
B-07 rule pinned here: reconciliation is per-item. The bulk-result endpoint
reports updated / missing (with a reason) / already-reconciled rows, and a
reminder whose outcome is already recorded (opened/failed) is terminal — a
stale list or a double-tap must not overwrite it (409 on the single-result
endpoint, an already_reconciled entry on the bulk one).

Mock-based SimpleTestCase (no DB), following tests/test_admin_wallet_views.py
and tests/test_flash_sales.py:
  - APIRequestFactory + view.as_view(); request.user is a superuser stand-in
    (passes IsTenantEditor) and request.tenant a SimpleNamespace.
  - sales.views.schema_context patched as a no-op (it is imported at module
    scope in sales/views.py, so patch the sales.views name, not the
    django_tenants source).
  - The model layer is replaced by small fakes with REAL status strings, so
    the view's status comparisons behave exactly as with the real models.
  - The input serializers are REAL (they validate the posted payloads); only
    the output ReservationReminderSerializer is stubbed, because the fakes
    are not real model instances.
  - _build_whatsapp_reservation_reminder is REAL (pure function) so the
    wa.me link generation itself is exercised.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.views import (
    OwnerReservationBulkReminderResultView,
    OwnerReservationBulkReminderView,
    OwnerReservationReminderResultView,
    OwnerReservationReminderView,
)


# ── Fake model layer (real status strings) ───────────────────────────────────

class _FakeLeadModel:
    class Status:
        NEW = "new"
        CONTACTED = "contacted"
        WON = "won"
        LOST = "lost"
        NO_SHOW = "no_show"

    objects = MagicMock(name="Lead.objects")


class _FakeReminderModel:
    class Statuses:
        SENT = "sent"
        OPENED = "opened"
        FAILED = "failed"

    class Channels:
        WHATSAPP = "whatsapp"

    objects = MagicMock(name="ReservationReminder.objects")


class _FakeReminder:
    """Stand-in for a ReservationReminder row; save() records update_fields."""

    def __init__(self, reminder_id, lead_id, status="sent", phone="", message="",
                 whatsapp_link="", failure_reason=""):
        self.id = reminder_id
        self.lead_id = lead_id
        self.status = status
        self.phone = phone
        self.message = message
        self.whatsapp_link = whatsapp_link
        self.failure_reason = failure_reason
        self.saved_fields = None
        self.save_calls = 0

    def save(self, update_fields=None):
        self.saved_fields = list(update_fields or [])
        self.save_calls += 1


class _FakeReminderSerializer:
    """Output serializer stub: the fakes are not real model instances."""

    def __init__(self, instance, *args, **kwargs):
        self.instance = instance

    @property
    def data(self):
        r = self.instance
        return {
            "id": getattr(r, "id", None),
            "status": getattr(r, "status", None),
            "phone": getattr(r, "phone", ""),
            "whatsapp_link": getattr(r, "whatsapp_link", ""),
            "failure_reason": getattr(r, "failure_reason", ""),
        }


def _lead(lead_id, status="new", phone="+212612345678", name="Sara Bennani",
          last_reminder_status=""):
    return SimpleNamespace(
        id=lead_id,
        status=status,
        phone=phone,
        name=name,
        last_reminder_status=last_reminder_status,
    )


def _owner_user():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = True
    u.is_platform_admin = True
    u.pk = 1
    return u


def _tenant():
    return SimpleNamespace(id=7, name="Test Resto", is_active=True)


class ReservationReminderViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.single_prepare = OwnerReservationReminderView.as_view()
        self.single_result = OwnerReservationReminderResultView.as_view()
        self.bulk_prepare = OwnerReservationBulkReminderView.as_view()
        self.bulk_result = OwnerReservationBulkReminderResultView.as_view()
        self.leads = {}
        self.reminders = {}
        self.timeline_notes = []
        self._next_reminder_id = 100

    # ── Patch scaffolding ────────────────────────────────────────────────────

    def _patches(self, prepared_leads):
        """Patch the sales.views names the reminder views touch.

        prepared_leads: list returned by _with_reservation_reminder_metrics
        (the bulk-prepare queryset, after annotation).
        """
        stack = patch.multiple(
            "sales.views",
            schema_context=MagicMock(),
            get_object_or_404=MagicMock(side_effect=self._fake_get_object_or_404),
            Lead=_FakeLeadModel,
            ReservationReminder=_FakeReminderModel,
            ReservationReminderSerializer=_FakeReminderSerializer,
            _log_reservation_timeline_event=MagicMock(
                side_effect=self._record_timeline_note
            ),
            _with_reservation_reminder_metrics=MagicMock(
                return_value=list(prepared_leads)
            ),
        )
        stack.start()
        self.addCleanup(stack.stop)
        # schema_context(...) must behave as a context manager.
        from sales.views import schema_context as _ctx

        _ctx.return_value.__enter__ = MagicMock(return_value=None)
        _ctx.return_value.__exit__ = MagicMock(return_value=False)
        # ReservationReminder.objects.create mints incrementing fake rows.
        _FakeReminderModel.objects.reset_mock()
        _FakeReminderModel.objects.create.side_effect = self._mint_reminder

    def _fake_get_object_or_404(self, model, **kwargs):
        if "lead_id" in kwargs:
            reminder = self.reminders.get(kwargs["pk"])
            if reminder is None:
                raise Http404()
            return reminder
        lead = self.leads.get(kwargs["pk"])
        if lead is None:
            raise Http404()
        return lead

    def _record_timeline_note(self, *args, **kwargs):
        self.timeline_notes.append(kwargs.get("note", ""))

    def _mint_reminder(self, **kwargs):
        self._next_reminder_id += 1
        reminder = _FakeReminder(
            reminder_id=self._next_reminder_id,
            lead_id=kwargs.get("lead_id"),
            status=kwargs.get("status", "sent"),
            phone=kwargs.get("phone", ""),
            message=kwargs.get("message", ""),
            whatsapp_link=kwargs.get("whatsapp_link", ""),
        )
        self.reminders[reminder.id] = reminder
        return reminder

    def _post(self, view, url, data, **kwargs):
        req = self.factory.post(url, data, format="json")
        req.user = _owner_user()
        req.tenant = _tenant()
        return view(req, **kwargs)

    # ── Single prepare (B-06) ────────────────────────────────────────────────

    def test_single_prepare_records_prepared_only_and_returns_wa_me_link(self):
        self.leads[1] = _lead(1)
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_prepare, "/owner/reservations/1/reminder/", {}, lead_id=1
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # The stored row is the prepared state, and the response carries the
        # server-generated wa.me URL for the owner to send.
        self.assertEqual(resp.data["status"], "sent")
        self.assertTrue(resp.data["whatsapp_link"].startswith("https://wa.me/212612345678?text="))
        create_kwargs = _FakeReminderModel.objects.create.call_args.kwargs
        self.assertEqual(create_kwargs["status"], "sent")
        self.assertIn("wa.me", create_kwargs["whatsapp_link"])
        # Timeline wording is "prepared", never "sent" as if delivered.
        self.assertEqual(len(self.timeline_notes), 1)
        self.assertIn("prepared", self.timeline_notes[0])
        self.assertNotIn("reminder sent", self.timeline_notes[0].lower())

    def test_single_prepare_lost_reservation_returns_400(self):
        self.leads[1] = _lead(1, status="lost")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_prepare, "/owner/reservations/1/reminder/", {}, lead_id=1
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        _FakeReminderModel.objects.create.assert_not_called()

    def test_single_prepare_no_phone_returns_400(self):
        self.leads[1] = _lead(1, phone="")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_prepare, "/owner/reservations/1/reminder/", {}, lead_id=1
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        _FakeReminderModel.objects.create.assert_not_called()

    # ── Single result (B-06/B-07 terminal guard) ─────────────────────────────

    def test_single_result_marks_prepared_reminder_opened(self):
        self.leads[1] = _lead(1)
        self.reminders[11] = _FakeReminder(11, lead_id=1, status="sent")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_result,
            "/owner/reservations/1/reminder-result/",
            {"reminder_id": 11, "status": "opened"},
            lead_id=1,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.reminders[11].status, "opened")
        self.assertEqual(self.reminders[11].failure_reason, "")
        self.assertIn("status", self.reminders[11].saved_fields)

    def test_single_result_failed_stores_reason(self):
        self.leads[1] = _lead(1)
        self.reminders[11] = _FakeReminder(11, lead_id=1, status="sent")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_result,
            "/owner/reservations/1/reminder-result/",
            {"reminder_id": 11, "status": "failed", "error": "Guest unreachable"},
            lead_id=1,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.reminders[11].status, "failed")
        self.assertEqual(self.reminders[11].failure_reason, "Guest unreachable")

    def test_single_result_already_reconciled_returns_409_and_keeps_status(self):
        self.leads[1] = _lead(1)
        self.reminders[11] = _FakeReminder(11, lead_id=1, status="opened")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.single_result,
            "/owner/reservations/1/reminder-result/",
            {"reminder_id": 11, "status": "failed", "error": "stale retry"},
            lead_id=1,
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_reconciled")
        self.assertEqual(resp.data["status"], "opened")
        # The recorded outcome is untouched: no overwrite, no save.
        self.assertEqual(self.reminders[11].status, "opened")
        self.assertEqual(self.reminders[11].failure_reason, "")
        self.assertEqual(self.reminders[11].save_calls, 0)

    # ── Bulk prepare (B-06/B-07 per-reservation outcomes) ────────────────────

    def test_bulk_prepare_returns_per_item_outcomes_with_prepared_status(self):
        prepared = [
            _lead(1),
            _lead(2, status="lost"),
            _lead(3, phone=""),
        ]
        self._patches(prepared_leads=prepared)
        resp = self._post(
            self.bulk_prepare,
            "/owner/reservations/bulk-reminder/",
            {"ids": [1, 2, 3, 99]},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["prepared_count"], 1)
        self.assertEqual(resp.data["missing_ids"], [99])
        self.assertEqual(resp.data["skipped_unavailable_ids"], [2])
        self.assertEqual(resp.data["skipped_no_phone_ids"], [3])
        self.assertEqual(resp.data["skipped_not_failed_ids"], [])
        # Each prepared row carries its stored (prepared) status + wa.me link.
        result = resp.data["results"][0]
        self.assertEqual(result["lead_id"], 1)
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["whatsapp_link"].startswith("https://wa.me/212612345678?text="))
        self.assertIn("prepared", self.timeline_notes[0])
        self.assertNotIn("reminder sent", self.timeline_notes[0].lower())

    def test_bulk_prepare_require_failed_filters_non_failed(self):
        prepared = [_lead(1, last_reminder_status="sent")]
        self._patches(prepared_leads=prepared)
        resp = self._post(
            self.bulk_prepare,
            "/owner/reservations/bulk-reminder/",
            {"ids": [1], "require_failed_last_reminder": True},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["prepared_count"], 0)
        self.assertEqual(resp.data["skipped_not_failed_ids"], [1])
        _FakeReminderModel.objects.create.assert_not_called()

    # ── Bulk result (B-07 per-item outcomes) ────────────────────────────────

    def test_bulk_result_reports_updated_missing_and_already_reconciled(self):
        self.leads[1] = _lead(1)
        self.leads[3] = _lead(3)
        self.reminders[11] = _FakeReminder(11, lead_id=1, status="sent")
        # Reminder 13 was already marked failed by the owner: terminal.
        self.reminders[13] = _FakeReminder(13, lead_id=3, status="failed")
        self._patches(prepared_leads=[])
        resp = self._post(
            self.bulk_result,
            "/owner/reservations/bulk-reminder-result/",
            {
                "items": [
                    {"lead_id": 1, "reminder_id": 11, "status": "opened"},
                    {"lead_id": 2, "reminder_id": 12, "status": "opened"},
                    {"lead_id": 3, "reminder_id": 13, "status": "opened"},
                ]
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated_count"], 1)
        self.assertEqual(resp.data["missing_count"], 1)
        self.assertEqual(resp.data["already_reconciled_count"], 1)
        self.assertEqual(resp.data["updated"], [{"lead_id": 1, "reminder_id": 11, "status": "opened"}])
        self.assertEqual(resp.data["missing"][0]["lead_id"], 2)
        self.assertEqual(resp.data["missing"][0]["reason"], "not_found")
        self.assertEqual(
            resp.data["already_reconciled"],
            [{"lead_id": 3, "reminder_id": 13, "status": "failed"}],
        )
        # Updated row changed; already-reconciled row untouched (no overwrite).
        self.assertEqual(self.reminders[11].status, "opened")
        self.assertEqual(self.reminders[13].status, "failed")
        self.assertEqual(self.reminders[13].save_calls, 0)

    def test_bulk_result_failed_reason_is_truncated_to_255(self):
        self.leads[1] = _lead(1)
        self.reminders[11] = _FakeReminder(11, lead_id=1, status="sent")
        self._patches(prepared_leads=[])
        long_error = "x" * 300
        resp = self._post(
            self.bulk_result,
            "/owner/reservations/bulk-reminder-result/",
            {
                "items": [
                    {"lead_id": 1, "reminder_id": 11, "status": "failed", "error": long_error}
                ]
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated_count"], 1)
        self.assertEqual(len(self.reminders[11].failure_reason), 255)
