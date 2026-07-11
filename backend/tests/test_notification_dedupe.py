"""ASYNC-4: notification-send dedupe.

CELERY_TASK_ACKS_LATE is global + a 120s hard time-limit, so a worker killed mid-send
gets its task REDELIVERED and re-run — a duplicate SMS/WhatsApp/push the customer sees
and we pay for. autoretry_for can re-run a task the same way. The tasks now claim a
one-time cache key before dispatching so a redelivered/retried duplicate skips, while a
genuine transient-failure retry still re-sends (the claim is released on exception).

Mock-based (SimpleTestCase, no DB): the dedupe claim lives in the default cache; the
sync senders are patched, and task bodies are driven directly via ``.run()``.
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from accounts import tasks


class NotificationDedupeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()  # dedupe claims are cache-backed; isolate each test

    # ── The duplicate-send class dies ───────────────────────────────────────

    def test_second_identical_send_is_deduped(self):
        """A redelivered/retried task with the same identity must NOT re-send."""
        with patch("menu.sms.send_order_ready_sms") as send:
            tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-1", tenant_id=1)
            tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-1", tenant_id=1)
        self.assertEqual(send.call_count, 1)

    def test_whatsapp_new_order_deduped(self):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)
        with patch("django_tenants.utils.schema_context", return_value=cm), \
             patch("menu.models.Order") as order_model, \
             patch("menu.views._notify_restaurant_new_order") as notify:
            order_model.objects.prefetch_related.return_value.filter.return_value.first.return_value = MagicMock()
            tasks.whatsapp_new_order.run("resto_a", 7, "Resto", "+212600000000", tenant_id=1)
            tasks.whatsapp_new_order.run("resto_a", 7, "Resto", "+212600000000", tenant_id=1)
        self.assertEqual(notify.call_count, 1)

    def test_customer_milestone_deduped(self):
        with patch("accounts.push.notify_customer_order_milestone_sync") as send:
            tasks.customer_order_milestone.run("ORD-1", 1, "ready")
            tasks.customer_order_milestone.run("ORD-1", 1, "ready")
        self.assertEqual(send.call_count, 1)

    # ── Distinct notifications are NOT collapsed ────────────────────────────

    def test_different_orders_not_deduped(self):
        with patch("menu.sms.send_order_ready_sms") as send:
            tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-1", tenant_id=1)
            tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-2", tenant_id=1)
        self.assertEqual(send.call_count, 2)

    def test_same_order_number_different_tenant_not_deduped(self):
        """order_number is only tenant-unique; the key embeds tenant_id so two tenants'
        ORD-1 sends do not collide on the shared cache."""
        with patch("menu.sms.send_order_ready_sms") as send:
            tasks.sms_order_ready.run("+212600000000", "A", "ORD-1", tenant_id=1)
            tasks.sms_order_ready.run("+212600000000", "B", "ORD-1", tenant_id=2)
        self.assertEqual(send.call_count, 2)

    def test_different_milestone_events_not_deduped(self):
        with patch("accounts.push.notify_customer_order_milestone_sync") as send:
            tasks.customer_order_milestone.run("ORD-1", 1, "accepted")
            tasks.customer_order_milestone.run("ORD-1", 1, "ready")
        self.assertEqual(send.call_count, 2)

    # ── Retries are preserved ───────────────────────────────────────────────

    def test_transient_failure_releases_claim_so_retry_resends(self):
        """A raising send (transient Twilio/network failure → autoretry) must release the
        claim so the retry actually re-sends rather than being deduped into a no-op."""
        with patch("menu.sms.send_order_ready_sms", side_effect=RuntimeError("twilio 503")):
            with self.assertRaises(RuntimeError):
                tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-1", tenant_id=1)
        with patch("menu.sms.send_order_ready_sms") as send_retry:
            tasks.sms_order_ready.run("+212600000000", "Resto", "ORD-1", tenant_id=1)
        self.assertEqual(send_retry.call_count, 1)

    # ── Fail-open: a cache blip must never drop a notification ──────────────

    def test_claim_fails_open_when_cache_unavailable(self):
        with patch("django.core.cache.cache", MagicMock(add=MagicMock(side_effect=Exception("redis down")))):
            self.assertTrue(tasks._claim_send("notif-dedupe:x"))

    def test_release_is_best_effort(self):
        with patch("django.core.cache.cache", MagicMock(delete=MagicMock(side_effect=Exception("redis down")))):
            tasks._release_send("notif-dedupe:x")  # must not raise
