"""
Tests for the Celery dispatch layer (Phase 4).

Focus on the safety-critical bits with no broker/worker needed:
  - enqueue() routes to the broker when configured, falls back to a BOUNDED inline
    thread pool otherwise (R14: bounded backpressure, not an unbounded raw Thread),
    and falls back if the broker raises.
  - the inline runner closes its DB connection so pooled threads don't leak/accumulate
    idle Postgres connections across reuse.
  - each notification task wraps the right synchronous dispatch function.
"""
from concurrent.futures import ThreadPoolExecutor
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
    @patch("accounts.tasks._inline_executor")
    def test_falls_back_to_bounded_pool_without_broker(self, executor):
        # R14: the no-broker fallback submits to the MODULE-LEVEL bounded
        # ThreadPoolExecutor (backpressure) — NOT a raw unbounded Thread.
        task = MagicMock()
        enqueue(task, "x")
        task.delay.assert_not_called()
        executor.submit.assert_called_once()
        # submitted callable is _run_inline with (task, args, kwargs)
        from accounts.tasks import _run_inline
        args, kwargs = executor.submit.call_args
        self.assertIs(args[0], _run_inline)
        self.assertIs(args[1], task)
        self.assertEqual(args[2], ("x",))

    def test_inline_executor_is_a_bounded_threadpool(self):
        # The pool is a real, bounded ThreadPoolExecutor (not unbounded thread spawning).
        from accounts.tasks import _inline_executor, _INLINE_MAX_WORKERS
        self.assertIsInstance(_inline_executor, ThreadPoolExecutor)
        self.assertEqual(_inline_executor._max_workers, _INLINE_MAX_WORKERS)
        self.assertGreaterEqual(_INLINE_MAX_WORKERS, 1)
        self.assertLessEqual(_INLINE_MAX_WORKERS, 8)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0")
    @patch("accounts.tasks._inline_executor")
    def test_falls_back_to_pool_when_broker_raises(self, executor):
        task = MagicMock()
        task.delay.side_effect = RuntimeError("broker down")
        enqueue(task, "x")
        executor.submit.assert_called_once()

    @override_settings(CELERY_BROKER_URL="")
    def test_inline_run_executes_task_body(self):
        # With no broker, enqueue runs the task on the pool; verify the _run_inline
        # path actually invokes task.run.
        from accounts.tasks import _run_inline
        task = MagicMock()
        _run_inline(task, ("a",), {"b": 2})
        task.run.assert_called_once_with("a", b=2)

    @override_settings(CELERY_BROKER_URL="")
    @patch("django.db.connection")
    def test_inline_run_closes_db_connection(self, connection):
        # CRITICAL: pooled threads are reused; each inline task must close its Django
        # DB connection so idle Postgres connections don't accumulate per pool thread.
        from accounts.tasks import _run_inline
        task = MagicMock()
        _run_inline(task, (), {})
        connection.close.assert_called_once_with()

    @override_settings(CELERY_BROKER_URL="")
    @patch("django.db.connection")
    def test_inline_run_swallows_errors_but_still_closes_conn(self, connection):
        # A failing notification must not crash the pool, and the connection must still
        # be closed (close is in a finally).
        from accounts.tasks import _run_inline
        task = MagicMock()
        task.run.side_effect = RuntimeError("boom")
        _run_inline(task, (), {})  # must not raise
        connection.close.assert_called_once_with()


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

    @patch("menu.sms.send_order_ready_sms")
    def test_sms_task_propagates_sms_provider_error(self, sms):
        """SmsProviderError (transient Twilio/network failure) must propagate so
        Celery's autoretry_for=(Exception,) retries the task automatically."""
        from accounts.tasks import sms_order_ready
        from menu.sms import SmsProviderError
        sms.side_effect = SmsProviderError("Twilio returned 503")
        with self.assertRaises(SmsProviderError):
            sms_order_ready.run("+212600", "Acme", "ORD-1", tenant_id=7)

    @patch("menu.sms.send_order_ready_sms")
    def test_sms_task_succeeds_on_permanent_failure(self, sms):
        """Permanent failures (return False, don't raise) must NOT propagate — the
        task should complete successfully so Celery doesn't retry a no-op."""
        from accounts.tasks import sms_order_ready
        sms.return_value = False  # no credentials / invalid phone
        sms_order_ready.run("+invalid", "Acme", "ORD-1")  # should not raise

    @patch("accounts.push.notify_online_drivers_new_job_sync")
    def test_driver_dispatch_calls_sync(self, notify):
        from accounts.tasks import driver_dispatch
        driver_dispatch.run("Acme")
        notify.assert_called_once_with("Acme")

    @patch("accounts.push._send_charge_request_sync")
    def test_charge_request_calls_sync(self, send):
        # R14b FIX1: the charge_request task wraps the existing synchronous sender so the
        # money-adjacent nudge dispatches via the bounded enqueue pool / Celery.
        from accounts.tasks import charge_request
        charge_request.run(42, "Acme Bistro", "150.00")
        send.assert_called_once_with(42, "Acme Bistro", "150.00")

    @patch("django.core.management.call_command")
    def test_run_management_command(self, call_command):
        from accounts.tasks import run_management_command
        run_management_command.run("release_scheduled_orders")
        call_command.assert_called_once_with("release_scheduled_orders")


class ChargeRequestDispatchTests(SimpleTestCase):
    """R14b FIX1: push_charge_request now routes through accounts.tasks.enqueue (bounded
    pool / .delay()) instead of spawning a raw threading.Thread."""

    @patch("accounts.tasks.enqueue")
    def test_push_charge_request_enqueues_task(self, enqueue):
        from accounts.push import push_charge_request
        from accounts.tasks import charge_request
        push_charge_request(7, "Acme", "99.50")
        enqueue.assert_called_once()
        args = enqueue.call_args[0]
        self.assertIs(args[0], charge_request)
        self.assertEqual(args[1], 7)
        self.assertEqual(args[2], "Acme")
        self.assertEqual(args[3], "99.50")

    @patch("accounts.tasks.enqueue")
    @patch("threading.Thread")
    def test_push_charge_request_does_not_spawn_raw_thread(self, thread, enqueue):
        from accounts.push import push_charge_request
        push_charge_request(7, "Acme", "99.50")
        thread.assert_not_called()  # no raw unbounded daemon thread anymore
