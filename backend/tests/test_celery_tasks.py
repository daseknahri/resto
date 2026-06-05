"""
Tests for the Celery dispatch layer (Phase 4).

Focus on the safety-critical bits with no broker/worker needed:
  - enqueue() routes to the broker when configured, falls back to a daemon thread
    otherwise, and falls back if the broker raises.
  - each notification task wraps the right synchronous dispatch function.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from accounts.tasks import enqueue


class EnqueueRoutingTests(SimpleTestCase):
    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    def test_uses_broker_when_configured(self):
        task = MagicMock()
        enqueue(task, "a", 1)
        task.delay.assert_called_once_with("a", 1)

    @override_settings(CELERY_BROKER_URL="")
    @patch("accounts.tasks.threading.Thread")
    def test_falls_back_to_thread_without_broker(self, Thread):
        task = MagicMock()
        enqueue(task, "x")
        task.delay.assert_not_called()
        Thread.assert_called_once()
        self.assertTrue(Thread.return_value.start.called)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    @patch("accounts.tasks.threading.Thread")
    def test_falls_back_to_thread_when_broker_raises(self, Thread):
        task = MagicMock()
        task.delay.side_effect = RuntimeError("broker down")
        enqueue(task, "x")
        Thread.assert_called_once()

    @override_settings(CELERY_BROKER_URL="")
    def test_inline_run_executes_task_body(self):
        # With no broker, enqueue runs the task synchronously via a thread; verify the
        # _run_inline path actually invokes task.run.
        from accounts.tasks import _run_inline
        task = MagicMock()
        _run_inline(task, ("a",), {"b": 2})
        task.run.assert_called_once_with("a", b=2)

    @override_settings(CELERY_BROKER_URL="")
    def test_inline_run_swallows_errors(self):
        from accounts.tasks import _run_inline
        task = MagicMock()
        task.run.side_effect = RuntimeError("boom")
        _run_inline(task, (), {})  # must not raise


class TaskWrapperTests(SimpleTestCase):
    @patch("menu.push._push_to_tenant")
    def test_web_push_tenant_calls_sync(self, push):
        from accounts.tasks import web_push_tenant
        web_push_tenant.run("acme", "Title", "Body", "/owner/orders")
        push.assert_called_once_with("acme", "Title", "Body", "/owner/orders")

    @patch("menu.sms.send_order_ready_sms")
    def test_sms_task_calls_sync(self, sms):
        from accounts.tasks import sms_order_ready
        sms_order_ready.run("+212600", "Acme", "ORD-1", tenant_id=7)
        sms.assert_called_once_with("+212600", "Acme", "ORD-1", tenant_id=7)

    @patch("accounts.push.notify_online_drivers_new_job_sync")
    def test_driver_dispatch_calls_sync(self, notify):
        from accounts.tasks import driver_dispatch
        driver_dispatch.run("Acme")
        notify.assert_called_once_with("Acme")

    @patch("django.core.management.call_command")
    def test_run_management_command(self, call_command):
        from accounts.tasks import run_management_command
        run_management_command.run("release_scheduled_orders")
        call_command.assert_called_once_with("release_scheduled_orders")
