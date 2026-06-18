"""
Unit tests for the pre-dispatch reminder feature.

Covers:
  - send_predispatch_reminder_sync: no-subs / opt-out / sends + records
  - send_predispatch_reminders management command: dry-run, stamps DB, skips already-stamped
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone


# ── push helper ──────────────────────────────────────────────────────────────

class TestSendPredispatchReminderSync(SimpleTestCase):
    """Exercises accounts.push.send_predispatch_reminder_sync in isolation.

    All heavy imports inside the function are lazy, so we patch them at their
    source modules (the pattern learned from C6 privacy tests).
    """

    def _call(self, customer_id=1, restaurant_name="Resto", order_number="ORD-1"):
        from accounts.push import send_predispatch_reminder_sync
        return send_predispatch_reminder_sync(customer_id, restaurant_name, order_number)

    def _make_patches(self, subs, cust_locale="en", notify_order_updates=True):
        """Return a dict of mock objects with standard DB setup."""
        cust = MagicMock()
        cust.notify_order_updates = notify_order_updates
        cust.locale = cust_locale

        mock_cust_cls = MagicMock()
        mock_cust_cls.objects.filter.return_value.first.return_value = cust

        mock_sub_qs = MagicMock()
        mock_sub_qs.__iter__ = MagicMock(return_value=iter(subs))
        mock_sub_cls = MagicMock()
        mock_sub_cls.objects.filter.return_value = mock_sub_qs

        return {"cust": cust, "mock_cust_cls": mock_cust_cls, "mock_sub_cls": mock_sub_cls, "mock_sub_qs": mock_sub_qs}

    def test_no_subscriptions_returns_zero(self):
        mocks = self._make_patches(subs=[])

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = self._call()

        self.assertEqual(result, 0)

    def test_opt_out_returns_zero(self):
        sub = MagicMock(endpoint="https://ep", p256dh="a", auth="b")
        mocks = self._make_patches(subs=[sub], notify_order_updates=False)

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = self._call()

        self.assertEqual(result, 0)

    def test_sends_and_returns_count(self):
        sub = MagicMock(endpoint="https://ep", p256dh="a", auth="b")
        mocks = self._make_patches(subs=[sub], cust_locale="en")

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("menu.push._send_one", return_value="ok") as mock_send:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = self._call(restaurant_name="PizzaHut", order_number="ORD-42")

        self.assertEqual(result, 1)
        mock_send.assert_called_once()
        call_args = mock_send.call_args.args
        # body should contain the restaurant name
        self.assertIn("PizzaHut", call_args[4])
        # url should contain order number
        self.assertIn("ORD-42", call_args[5])

    def test_french_locale_used(self):
        sub = MagicMock(endpoint="https://ep", p256dh="a", auth="b")
        mocks = self._make_patches(subs=[sub], cust_locale="fr")

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("menu.push._send_one", return_value="ok") as mock_send:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            self._call()

        title = mock_send.call_args.args[3]
        # French title should contain "arrive"
        self.assertIn("arrive", title)

    def test_arabic_locale_used(self):
        sub = MagicMock(endpoint="https://ep", p256dh="a", auth="b")
        mocks = self._make_patches(subs=[sub], cust_locale="ar")

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("menu.push._send_one", return_value="ok") as mock_send:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            self._call()

        title = mock_send.call_args.args[3]
        self.assertIn("طلبك", title)

    def test_unknown_locale_falls_back_to_en(self):
        sub = MagicMock(endpoint="https://ep", p256dh="a", auth="b")
        mocks = self._make_patches(subs=[sub], cust_locale="sw")  # Swahili — not in messages

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("menu.push._send_one", return_value="ok") as mock_send:
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = self._call()

        self.assertEqual(result, 1)
        # Should fall back to English title
        title = mock_send.call_args.args[3]
        self.assertIn("coming up", title)

    def test_gone_sub_not_counted(self):
        sub = MagicMock(id=99, endpoint="https://gone", p256dh="x", auth="y")
        mocks = self._make_patches(subs=[sub])

        with patch("accounts.models.Customer", mocks["mock_cust_cls"]), \
             patch("accounts.models.CustomerPushSubscription", mocks["mock_sub_cls"]), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("menu.push._send_one", return_value="gone"):
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = self._call()

        self.assertEqual(result, 0)


# ── management command ───────────────────────────────────────────────────────

class TestSendPredispatchRemindersCommand(SimpleTestCase):
    """Exercises send_predispatch_reminders management command logic (no real DB)."""

    def _run_command(self, **kwargs):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("send_predispatch_reminders", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def _make_tenant(self, slug="test", name="Test Restaurant", schema_name="test"):
        t = MagicMock()
        t.slug = slug
        t.name = name
        t.schema_name = schema_name
        return t

    def _make_order(self, order_number="ORD-1", customer_id=5, minutes_ahead=65):
        o = MagicMock()
        o.order_number = order_number
        o.customer_id = customer_id
        o.scheduled_for = timezone.now() + timedelta(minutes=minutes_ahead)
        return o

    def test_dry_run_does_not_save(self):
        """--dry-run prints orders but never calls order.save()."""
        tenant = self._make_tenant()
        order = self._make_order()

        with patch("menu.management.commands.send_predispatch_reminders.Tenant") as mock_t, \
             patch("menu.management.commands.send_predispatch_reminders.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("accounts.push.send_predispatch_reminder_sync") as mock_push:

            mock_t.objects.filter.return_value.exclude.return_value = [tenant]
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_order_cls.Status.SCHEDULED = "scheduled"
            mock_order_cls.objects.filter.return_value.only.return_value = [order]

            output = self._run_command(dry_run=True)

        order.save.assert_not_called()
        mock_push.assert_not_called()
        self.assertIn("DRY RUN", output)

    def test_stamps_predispatch_reminder_sent_at(self):
        """On a real run, saves predispatch_reminder_sent_at on each eligible order."""
        tenant = self._make_tenant()
        order = self._make_order()

        with patch("menu.management.commands.send_predispatch_reminders.Tenant") as mock_t, \
             patch("menu.management.commands.send_predispatch_reminders.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("accounts.push.send_predispatch_reminder_sync", return_value=1):

            mock_t.objects.filter.return_value.exclude.return_value = [tenant]
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_order_cls.Status.SCHEDULED = "scheduled"
            mock_order_cls.objects.filter.return_value.only.return_value = [order]

            self._run_command()

        order.save.assert_called_once()
        update_fields = order.save.call_args.kwargs.get("update_fields", [])
        self.assertIn("predispatch_reminder_sent_at", update_fields)
        self.assertIsNotNone(order.predispatch_reminder_sent_at)

    def test_push_exception_still_stamps(self):
        """If push raises, the command still stamps predispatch_reminder_sent_at."""
        tenant = self._make_tenant()
        order = self._make_order()

        with patch("menu.management.commands.send_predispatch_reminders.Tenant") as mock_t, \
             patch("menu.management.commands.send_predispatch_reminders.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("accounts.push.send_predispatch_reminder_sync", side_effect=RuntimeError("boom")):

            mock_t.objects.filter.return_value.exclude.return_value = [tenant]
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_order_cls.Status.SCHEDULED = "scheduled"
            mock_order_cls.objects.filter.return_value.only.return_value = [order]

            self._run_command()  # must not raise

        order.save.assert_called_once()

    def test_no_tenants_exits_cleanly(self):
        with patch("menu.management.commands.send_predispatch_reminders.Tenant") as mock_t:
            mock_t.objects.filter.return_value.exclude.return_value = []
            output = self._run_command()
        self.assertIn("Done", output)
        self.assertIn("0 order(s)", output)

    def test_output_contains_order_number(self):
        tenant = self._make_tenant()
        order = self._make_order(order_number="ORD-XYZ")

        with patch("menu.management.commands.send_predispatch_reminders.Tenant") as mock_t, \
             patch("menu.management.commands.send_predispatch_reminders.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("accounts.push.send_predispatch_reminder_sync", return_value=1):

            mock_t.objects.filter.return_value.exclude.return_value = [tenant]
            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_order_cls.Status.SCHEDULED = "scheduled"
            mock_order_cls.objects.filter.return_value.only.return_value = [order]

            output = self._run_command()

        self.assertIn("ORD-XYZ", output)


# ── allowlist guard ──────────────────────────────────────────────────────────

class TestAllowlistContainsSendPredispatch(SimpleTestCase):
    def test_command_in_allowlist(self):
        from accounts.tasks import _MANAGEMENT_COMMAND_ALLOWLIST
        self.assertIn("send_predispatch_reminders", _MANAGEMENT_COMMAND_ALLOWLIST)
