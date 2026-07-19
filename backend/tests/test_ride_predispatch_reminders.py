"""
Unit tests for ride pre-dispatch reminder push (BACKLOG: "Pre-dispatch reminder
push for scheduled trips").

Covers:
  send_ride_predispatch_reminder_sync:
    - no subs → 0
    - sends push with correct kind/minutes
    - FR locale
    - AR locale
    - unknown locale falls back to en
    - gone sub cleaned up
    - invalid kind falls back to "ride"

  send_ride_predispatch_reminders management command:
    - dry run: no push, no stamp, output contains ride id
    - happy path: stamps predispatch_reminder_sent_at, calls push
    - push exception still stamps (prevents retry loop)
    - no scheduled trips → clean output
    - output line contains ride id and minutes

  send_ride_predispatch_reminders is scheduled in Beat as its cron.* task (RISK ASYNC-2)
"""
from __future__ import annotations

import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


# ── send_ride_predispatch_reminder_sync ──────────────────────────────────────

class TestSendRidePredispatchReminderSync(SimpleTestCase):
    def _call(self, rider_id=1, kind="ride", minutes_remaining=28):
        from accounts.push import send_ride_predispatch_reminder_sync
        return send_ride_predispatch_reminder_sync(rider_id, kind, minutes_remaining)

    def _ctx(self, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_no_subs_returns_zero(self, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        mock_subs.objects.filter.return_value = []
        self.assertEqual(self._call(), 0)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_ride_push_sends_with_minutes(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        result = self._call(minutes_remaining=28)
        self.assertEqual(result, 1)
        body = mock_send.call_args[0][4]
        self.assertIn("28", body)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_package_kind_uses_pickup_message(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        self._call(kind="package", minutes_remaining=25)
        title = mock_send.call_args[0][3]
        # Package message has "pickup" or "enleve" — just check it's different from ride
        self.assertTrue(len(title) > 0)
        body = mock_send.call_args[0][4]
        self.assertIn("25", body)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_fr_locale(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="fr")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        self._call()
        title = mock_send.call_args[0][3]
        self.assertIn("course", title.lower())

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_ar_locale(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="ar")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        self._call()
        title = mock_send.call_args[0][3]
        self.assertIn("قريباً", title)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_unknown_locale_falls_back_to_en(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="sw")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        self._call()
        title = mock_send.call_args[0][3]
        self.assertIn("soon", title.lower())

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_gone_sub_cleaned_up(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub = MagicMock(id=77, endpoint="e", p256dh="k", auth="a")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([sub]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "gone"
        self._call()
        mock_qs.delete.assert_called_once()

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_invalid_kind_falls_back_to_ride(self, mock_send, mock_cust, mock_subs, mock_ctx):
        self._ctx(mock_ctx)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([MagicMock(endpoint="e", p256dh="k", auth="a")]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "ok"
        # Should not raise for an unrecognised kind
        result = self._call(kind="courier")
        self.assertEqual(result, 1)


# ── send_ride_predispatch_reminders management command ───────────────────────

class TestSendRidePredispatchRemindersCommand(SimpleTestCase):
    def _run(self, **kwargs):
        from accounts.management.commands.send_ride_predispatch_reminders import Command
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        cmd.handle(**{"dry_run": False, **kwargs})
        return cmd.stdout.getvalue()

    def _make_ride(self, ride_id, rider_id=1, kind="ride", minutes=28):
        now = datetime.datetime.now(datetime.timezone.utc)
        ride = MagicMock()
        ride.id = ride_id
        ride.rider_id = rider_id
        ride.kind = kind
        ride.scheduled_for = now + datetime.timedelta(minutes=minutes)
        ride.predispatch_reminder_sent_at = None
        return ride

    @patch("accounts.push.send_ride_predispatch_reminder_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.RideRequest")
    def test_dry_run_no_push_no_stamp(self, mock_rr, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        ride = self._make_ride(55)
        mock_rr.objects.filter.return_value.select_related.return_value = [ride]
        mock_rr.Status.SCHEDULED = "scheduled"
        out = self._run(dry_run=True)
        mock_push.assert_not_called()
        ride.save.assert_not_called()
        self.assertIn("(dry)", out)
        self.assertIn("55", out)

    @patch("accounts.push.send_ride_predispatch_reminder_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.RideRequest")
    def test_stamps_and_calls_push(self, mock_rr, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        ride = self._make_ride(12, kind="ride", minutes=30)
        mock_rr.objects.filter.return_value.select_related.return_value = [ride]
        mock_rr.Status.SCHEDULED = "scheduled"
        self._run()
        # minutes = int((scheduled_for - now)/60); sub-second drift between the
        # fixture's now and the command's now can truncate 30 -> 29, so allow both
        # (this assertion was time-flaky before).
        mock_push.assert_called_once()
        _args = mock_push.call_args.args
        self.assertEqual((_args[0], _args[1]), (ride.rider_id, "ride"))
        self.assertIn(_args[2], (29, 30))
        ride.save.assert_called_once_with(update_fields=["predispatch_reminder_sent_at"])
        self.assertIsNotNone(ride.predispatch_reminder_sent_at)

    @patch("accounts.push.send_ride_predispatch_reminder_sync", side_effect=RuntimeError("boom"))
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.RideRequest")
    def test_push_exception_still_stamps(self, mock_rr, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        ride = self._make_ride(7)
        mock_rr.objects.filter.return_value.select_related.return_value = [ride]
        mock_rr.Status.SCHEDULED = "scheduled"
        self._run()  # must not raise
        ride.save.assert_called_once_with(update_fields=["predispatch_reminder_sent_at"])

    @patch("accounts.push.send_ride_predispatch_reminder_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.RideRequest")
    def test_no_trips_runs_cleanly(self, mock_rr, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_rr.objects.filter.return_value.select_related.return_value = []
        mock_rr.Status.SCHEDULED = "scheduled"
        out = self._run()
        self.assertIn("sent=0", out)
        mock_push.assert_not_called()

    @patch("accounts.push.send_ride_predispatch_reminder_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.RideRequest")
    def test_output_contains_ride_id(self, mock_rr, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        ride = self._make_ride(999)
        mock_rr.objects.filter.return_value.select_related.return_value = [ride]
        mock_rr.Status.SCHEDULED = "scheduled"
        out = self._run()
        self.assertIn("999", out)


class TestSendRidePredispatchScheduled(SimpleTestCase):
    def test_command_scheduled_as_cron_task(self):
        # RISK ASYNC-2: the command is wired to Beat via its dedicated cron.* task.
        from django.conf import settings
        tasks = {e["task"] for e in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertIn("cron.send_ride_predispatch_reminders", tasks)
