"""
Tests for the outbound-notification audit log (Phase 4 — no queue).

Covers the record_notification helper's truncation + best-effort behaviour, and the
OwnerNotificationsView permission gate + tenant-scoped serialization. Unit-level
(SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.notifications import record_notification
from menu.views import OwnerNotificationsView


class RecordNotificationTests(SimpleTestCase):
    @patch("accounts.models.NotificationLog")
    def test_creates_row_with_given_fields(self, NL):
        record_notification(channel="push", event="order.new", status="sent",
                            recipient="3/3 subs", detail="Acme", reference="ORD-1", tenant_id=7)
        NL.objects.create.assert_called_once()
        kw = NL.objects.create.call_args.kwargs
        self.assertEqual(kw["channel"], "push")
        self.assertEqual(kw["event"], "order.new")
        self.assertEqual(kw["status"], "sent")
        self.assertEqual(kw["reference"], "ORD-1")
        self.assertEqual(kw["tenant_id"], 7)

    @patch("accounts.models.NotificationLog")
    def test_fields_are_truncated(self, NL):
        record_notification(channel="email", event="x" * 80, status="failed",
                            recipient="r" * 200, detail="d" * 400, reference="f" * 80, error="e" * 500)
        kw = NL.objects.create.call_args.kwargs
        self.assertEqual(len(kw["event"]), 40)
        self.assertEqual(len(kw["recipient"]), 120)
        self.assertEqual(len(kw["detail"]), 200)
        self.assertEqual(len(kw["reference"]), 40)
        self.assertEqual(len(kw["error"]), 300)

    @patch("accounts.models.NotificationLog")
    def test_never_raises_on_db_error(self, NL):
        NL.objects.create.side_effect = RuntimeError("db down")
        # Must not propagate — auditing is best-effort.
        record_notification(channel="sms", status="sent")

    @patch("tenancy.models.Tenant")
    @patch("accounts.models.NotificationLog")
    def test_resolves_tenant_from_schema_name(self, NL, Tenant):
        Tenant.objects.filter.return_value.values_list.return_value.first.return_value = 42
        record_notification(channel="push", status="sent", schema_name="acme")
        self.assertEqual(NL.objects.create.call_args.kwargs["tenant_id"], 42)


class OwnerNotificationsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerNotificationsView.as_view()

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_denied_for_non_editor(self, _gate):
        req = self.factory.get("/api/owner/notifications/")
        req.user = MagicMock(id=1)
        req.tenant = MagicMock(id=7)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.NotificationLog")
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    def test_returns_tenant_scoped_rows(self, _gate, NL):
        row = MagicMock(id=1, channel="push", event="order.new", status="sent",
                        recipient="3 subs", detail="Acme", reference="ORD-1", error="")
        row.created_at.isoformat.return_value = "2026-06-05T10:00:00+00:00"
        # filtered list (slice) → [row]
        NL.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [row]
        # summary aggregate → []
        NL.objects.filter.return_value.values.return_value.annotate.return_value = []
        req = self.factory.get("/api/owner/notifications/")
        req.user = MagicMock(id=1)
        req.tenant = MagicMock(id=7)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["reference"], "ORD-1")
        NL.objects.filter.assert_any_call(tenant_id=7)
