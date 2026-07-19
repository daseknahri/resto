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
    def setUp(self):
        # ASYNC-4: several notification tasks now claim a one-time cache key to dedupe
        # redelivered/retried sends. These tests reuse identical args (same key), so a
        # claim from one test would dedupe the next into a no-op — reset per test.
        from django.core.cache import cache
        cache.clear()

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
    def test_cron_task_calls_its_command(self, call_command):
        # RISK ASYNC-2: each Beat entry now has a DEDICATED named task that bakes in its
        # own command name (no caller-supplied name), instead of one generic runner.
        from accounts.tasks import release_scheduled_orders
        release_scheduled_orders.run()
        call_command.assert_called_once_with("release_scheduled_orders")

    @patch("django.core.management.call_command")
    def test_enforce_subscriptions_task_bakes_apply_flag(self, call_command):
        # apply=True used to be a Beat kwarg; it's now baked into the task body so no
        # broker message field controls it.
        from accounts.tasks import enforce_subscriptions
        enforce_subscriptions.run()
        call_command.assert_called_once_with("enforce_subscriptions", apply=True)


class CronTaskRetryTests(SimpleTestCase):
    """RISK ASYNC-2: the sweep/reconcile tasks must retry a TRANSIENT DB error with
    backoff so a brief Postgres blip during a tick retries instead of dropping it."""

    def test_sweeps_retry_on_transient_db_error(self):
        from django.db import InterfaceError, OperationalError
        from accounts.tasks import (
            sweep_delivery_jobs, sweep_ride_requests, reconcile_driver_earnings,
        )
        for task in (sweep_delivery_jobs, sweep_ride_requests, reconcile_driver_earnings):
            with self.subTest(task=task.name):
                self.assertIn(OperationalError, task.autoretry_for)
                self.assertIn(InterfaceError, task.autoretry_for)
                self.assertEqual(task.retry_kwargs.get("max_retries"), 3)
                self.assertTrue(task.retry_backoff)

    def test_sweeps_do_not_retry_on_arbitrary_exception(self):
        # A genuine bug in a command must fail fast, not re-run 3x — only transient DB
        # errors are in autoretry_for.
        from accounts.tasks import sweep_delivery_jobs
        self.assertNotIn(Exception, sweep_delivery_jobs.autoretry_for)
        self.assertNotIn(ValueError, sweep_delivery_jobs.autoretry_for)


class TaskQueueRoutingTests(SimpleTestCase):
    """RISK ASYNC-2: the cron/sweep tasks must be routed off the notifications queue
    so a slow sweep can't starve customer-facing SMS/WhatsApp/push sends. Uses
    Celery's own router (no broker/DB needed) so this fails if CELERY_TASK_ROUTES
    or CELERY_TASK_DEFAULT_QUEUE ever regresses."""

    def test_cron_task_routes_to_cron_queue(self):
        from config.celery import app
        route = app.amqp.router.route({}, "cron.sweep_delivery_jobs")
        self.assertEqual(route["queue"].name, "cron")

    def test_notification_task_routes_to_default_queue(self):
        from config.celery import app
        route = app.amqp.router.route({}, "accounts.tasks.sms_order_ready")
        self.assertEqual(route["queue"].name, "notifications")

    def test_every_scheduled_cron_task_is_registered_and_routes_to_cron(self):
        """The task NAME is the allowlist: every cron.* task Beat schedules must be a
        registered Celery task (a typo'd/removed task would fail loudly at dispatch) and
        must route to the dedicated cron queue."""
        from django.conf import settings
        from config.celery import app
        cron_tasks = {
            e["task"]
            for e in settings.CELERY_BEAT_SCHEDULE.values()
            if e["task"].startswith("cron.")
        }
        self.assertTrue(cron_tasks)  # sanity: the schedule has cron entries
        for name in cron_tasks:
            with self.subTest(task=name):
                self.assertIn(name, app.tasks, f"{name} is scheduled but not registered")
                route = app.amqp.router.route({}, name)
                self.assertEqual(route["queue"].name, "cron")

    def test_generic_runner_and_allowlist_are_gone(self):
        """RISK ASYNC-2: no task accepts an arbitrary command name off the broker, and
        the drift-prone parallel allowlist is deleted."""
        import accounts.tasks as tasks
        self.assertFalse(hasattr(tasks, "run_management_command"))
        self.assertFalse(hasattr(tasks, "_MANAGEMENT_COMMAND_ALLOWLIST"))


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
