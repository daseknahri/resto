"""
Tests for sales/management/commands/send_reservation_reminders.py

Covers: _reminder_window, _profile_reminders_enabled, _send_reminder_email,
_send_reminder_sms, and the Command.handle() logic.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.core.management import call_command

from sales.management.commands.send_reservation_reminders import (
    _profile_reminders_enabled,
    _reminder_window,
    _send_reminder_email,
    _send_reminder_sms,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tenant(slug="demo", schema="demo", name="Demo Restaurant"):
    return SimpleNamespace(id=1, pk=1, slug=slug, schema_name=schema, name=name)


_UNSET = object()


def _lead(
    lead_id=1,
    email="customer@example.com",
    phone="+33600000001",
    name="Alice",
    booked_for=_UNSET,
    party_size=2,
):
    if booked_for is _UNSET:
        booked_for = datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=lead_id,
        pk=lead_id,
        email=email,
        phone=phone,
        name=name,
        booked_for=booked_for,
        party_size=party_size,
        reminder_sent_at=None,
        save=MagicMock(),
    )


# ── _reminder_window ──────────────────────────────────────────────────────────

class ReminderWindowTests(SimpleTestCase):
    def test_window_is_centered_2h_from_now_with_30min_half(self):
        now = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
        with patch("sales.management.commands.send_reservation_reminders.timezone") as tz_mock:
            tz_mock.now.return_value = now
            start, end = _reminder_window()
        expected_start = now + timedelta(hours=1.5)
        expected_end = now + timedelta(hours=2.5)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)


# ── _profile_reminders_enabled ────────────────────────────────────────────────

class ProfileRemindersEnabledTests(SimpleTestCase):
    def test_returns_false_when_no_profile(self):
        tenant = _tenant()
        with patch("sales.management.commands.send_reservation_reminders.schema_context") as sc_mock:
            with patch("sales.management.commands.send_reservation_reminders.Profile") as profile_mock:
                sc_mock.return_value.__enter__ = lambda s: None
                sc_mock.return_value.__exit__ = lambda s, *a: None
                profile_mock.objects.filter.return_value.first.return_value = None
                result = _profile_reminders_enabled(tenant)
        self.assertFalse(result)

    def test_returns_false_when_reminders_disabled(self):
        tenant = _tenant()
        profile = SimpleNamespace(reservation_reminders_enabled=False)
        with patch("sales.management.commands.send_reservation_reminders.schema_context") as sc_mock:
            with patch("sales.management.commands.send_reservation_reminders.Profile") as profile_mock:
                sc_mock.return_value.__enter__ = lambda s: None
                sc_mock.return_value.__exit__ = lambda s, *a: None
                profile_mock.objects.filter.return_value.first.return_value = profile
                result = _profile_reminders_enabled(tenant)
        self.assertFalse(result)

    def test_returns_true_when_reminders_enabled(self):
        tenant = _tenant()
        profile = SimpleNamespace(reservation_reminders_enabled=True)
        with patch("sales.management.commands.send_reservation_reminders.schema_context") as sc_mock:
            with patch("sales.management.commands.send_reservation_reminders.Profile") as profile_mock:
                sc_mock.return_value.__enter__ = lambda s: None
                sc_mock.return_value.__exit__ = lambda s, *a: None
                profile_mock.objects.filter.return_value.first.return_value = profile
                result = _profile_reminders_enabled(tenant)
        self.assertTrue(result)

    def test_returns_false_on_exception(self):
        tenant = _tenant()
        with patch("sales.management.commands.send_reservation_reminders.schema_context", side_effect=Exception("db down")):
            result = _profile_reminders_enabled(tenant)
        self.assertFalse(result)


# ── _send_reminder_email ──────────────────────────────────────────────────────

class SendReminderEmailTests(SimpleTestCase):
    def test_returns_false_when_no_email(self):
        lead = _lead(email="")
        result = _send_reminder_email(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_returns_false_when_email_whitespace_only(self):
        lead = _lead(email="   ")
        result = _send_reminder_email(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_sends_email_and_returns_true(self):
        # booked_for=None avoids strftime with %-d which fails on Windows
        lead = _lead(booked_for=None)
        with patch("sales.management.commands.send_reservation_reminders.send_mail", return_value=1) as mock_mail:
            result = _send_reminder_email(lead, "Demo Restaurant")
        self.assertTrue(result)
        mock_mail.assert_called_once()
        subject, body, sender, recipients = mock_mail.call_args[0]
        self.assertIn("Demo Restaurant", subject)
        self.assertIn(lead.email, recipients)

    def test_returns_false_when_send_mail_returns_zero(self):
        lead = _lead(booked_for=None)
        with patch("sales.management.commands.send_reservation_reminders.send_mail", return_value=0):
            result = _send_reminder_email(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_returns_false_on_exception(self):
        lead = _lead(booked_for=None)
        with patch("sales.management.commands.send_reservation_reminders.send_mail", side_effect=Exception("smtp error")):
            result = _send_reminder_email(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_includes_party_size_in_email(self):
        lead = _lead(party_size=4, booked_for=None)
        with patch("sales.management.commands.send_reservation_reminders.send_mail", return_value=1) as mock_mail:
            _send_reminder_email(lead, "Demo Restaurant")
        _, body, _, _ = mock_mail.call_args[0]
        self.assertIn("4", body)


# ── _send_reminder_sms ────────────────────────────────────────────────────────

class SendReminderSmsTests(SimpleTestCase):
    def test_returns_false_when_no_phone(self):
        lead = _lead(phone="")
        result = _send_reminder_sms(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_returns_false_when_twilio_not_configured(self):
        lead = _lead(booked_for=None)
        with patch("menu.sms._credentials", return_value=None):
            result = _send_reminder_sms(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_sends_sms_and_returns_true(self):
        lead = _lead(booked_for=None)
        resp_mock = MagicMock()
        resp_mock.status_code = 201
        with patch("menu.sms._credentials", return_value=("SID", "TOKEN", "+15550000")):
            with patch("menu.sms._normalize_phone", return_value="+33600000001"):
                with patch("requests.post", return_value=resp_mock):
                    result = _send_reminder_sms(lead, "Demo Restaurant")
        self.assertTrue(result)

    def test_returns_false_when_twilio_error_status(self):
        lead = _lead(booked_for=None)
        resp_mock = MagicMock()
        resp_mock.status_code = 400
        resp_mock.text = "bad request"
        with patch("menu.sms._credentials", return_value=("SID", "TOKEN", "+15550000")):
            with patch("menu.sms._normalize_phone", return_value="+33600000001"):
                with patch("requests.post", return_value=resp_mock):
                    result = _send_reminder_sms(lead, "Demo Restaurant")
        self.assertFalse(result)

    def test_returns_false_on_exception(self):
        lead = _lead(booked_for=None)
        with patch("menu.sms._credentials", return_value=("SID", "TOKEN", "+15550000")):
            with patch("menu.sms._normalize_phone", return_value="+33600000001"):
                with patch("requests.post", side_effect=Exception("network error")):
                    result = _send_reminder_sms(lead, "Demo Restaurant")
        self.assertFalse(result)


# ── Command.handle() ──────────────────────────────────────────────────────────

class SendReservationRemindersCommandTests(SimpleTestCase):
    def _run(self, *args, **kwargs):
        stdout = io.StringIO()
        call_command("send_reservation_reminders", *args, stdout=stdout, **kwargs)
        return stdout.getvalue()

    def _setup_patches(self, tenants, leads_per_tenant=None, reminders_enabled=True):
        leads_per_tenant = leads_per_tenant or {}

        def fake_schema_context(schema_name):
            ctx = MagicMock()
            ctx.__enter__ = lambda s: None
            ctx.__exit__ = lambda s, *a: None
            return ctx

        tenant_qs = MagicMock()
        tenant_qs.filter.return_value = tenant_qs
        tenant_qs.exclude.return_value = tenants
        tenant_qs.__iter__ = lambda s: iter(tenants)

        return tenant_qs

    @patch("sales.management.commands.send_reservation_reminders._profile_reminders_enabled", return_value=False)
    @patch("sales.management.commands.send_reservation_reminders.Lead")
    @patch("sales.management.commands.send_reservation_reminders.Tenant")
    def test_skips_tenant_when_reminders_disabled(self, TenantMock, LeadMock, reminders_mock):
        tenant = _tenant()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.exclude.return_value = [tenant]
        TenantMock.objects.filter.return_value = qs

        out = self._run()
        self.assertIn("Done", out)
        LeadMock.objects.filter.assert_not_called()

    @patch("sales.management.commands.send_reservation_reminders._send_reminder_email", return_value=True)
    @patch("sales.management.commands.send_reservation_reminders._send_reminder_sms", return_value=False)
    @patch("sales.management.commands.send_reservation_reminders._profile_reminders_enabled", return_value=True)
    @patch("sales.management.commands.send_reservation_reminders.Lead")
    @patch("sales.management.commands.send_reservation_reminders.Tenant")
    def test_sends_reminders_and_stamps_lead(self, TenantMock, LeadMock, reminders_mock, sms_mock, email_mock):
        tenant = _tenant()
        tenant_qs = MagicMock()
        tenant_qs.filter.return_value = tenant_qs
        tenant_qs.exclude.return_value = [tenant]
        TenantMock.objects.filter.return_value = tenant_qs
        TenantMock.LifecycleStatus = SimpleNamespace(ACTIVE="active")

        lead = _lead()
        lead_qs = MagicMock()
        lead_qs.__iter__ = lambda s: iter([lead])
        LeadMock.objects.filter.return_value = lead_qs

        with patch("sales.management.commands.send_reservation_reminders.timezone") as tz_mock:
            now = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
            tz_mock.now.return_value = now
            out = self._run()

        self.assertIn("Done", out)
        self.assertIn("1 reminder", out)
        lead.save.assert_called_once()

    @patch("sales.management.commands.send_reservation_reminders._send_reminder_email", return_value=False)
    @patch("sales.management.commands.send_reservation_reminders._send_reminder_sms", return_value=False)
    @patch("sales.management.commands.send_reservation_reminders._profile_reminders_enabled", return_value=True)
    @patch("sales.management.commands.send_reservation_reminders.Lead")
    @patch("sales.management.commands.send_reservation_reminders.Tenant")
    def test_stamps_lead_even_when_all_channels_fail(self, TenantMock, LeadMock, reminders_mock, sms_mock, email_mock):
        """Lead gets stamped (no retry) even when email and SMS both fail."""
        tenant = _tenant()
        tenant_qs = MagicMock()
        tenant_qs.filter.return_value = tenant_qs
        tenant_qs.exclude.return_value = [tenant]
        TenantMock.objects.filter.return_value = tenant_qs
        TenantMock.LifecycleStatus = SimpleNamespace(ACTIVE="active")

        lead = _lead()
        lead_qs = MagicMock()
        lead_qs.__iter__ = lambda s: iter([lead])
        LeadMock.objects.filter.return_value = lead_qs

        with patch("sales.management.commands.send_reservation_reminders.timezone") as tz_mock:
            tz_mock.now.return_value = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
            self._run()

        lead.save.assert_called_once()

    @patch("sales.management.commands.send_reservation_reminders._profile_reminders_enabled", return_value=True)
    @patch("sales.management.commands.send_reservation_reminders.Lead")
    @patch("sales.management.commands.send_reservation_reminders.Tenant")
    def test_dry_run_does_not_send_or_stamp(self, TenantMock, LeadMock, reminders_mock):
        tenant = _tenant()
        tenant_qs = MagicMock()
        tenant_qs.filter.return_value = tenant_qs
        tenant_qs.exclude.return_value = [tenant]
        TenantMock.objects.filter.return_value = tenant_qs
        TenantMock.LifecycleStatus = SimpleNamespace(ACTIVE="active")

        lead = _lead()
        lead_qs = MagicMock()
        lead_qs.__iter__ = lambda s: iter([lead])
        LeadMock.objects.filter.return_value = lead_qs

        with patch("sales.management.commands.send_reservation_reminders.timezone") as tz_mock:
            tz_mock.now.return_value = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
            out = self._run("--dry-run")

        self.assertIn("DRY RUN", out)
        lead.save.assert_not_called()
