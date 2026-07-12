"""RISK ASYNC-1: guard the silent inline-task fallback (mock/DB-free).

accounts.tasks.enqueue() falls back to an in-process ThreadPoolExecutor whenever
no Celery broker is configured — durable-looking but actually lossy on every
deploy/restart. Two independent nets:

  1. A deploy-only Django system check (config/checks.py,
     celery_broker_configured_for_durability, id kepoli.E002) that ERRORs when
     DEBUG=False and CELERY_BROKER_URL is unset, so `manage.py check --deploy`
     (run by docker/entrypoint.sh with --fail-level ERROR) refuses to ship a
     production build onto the lossy fallback. It is registered with
     ``deploy=True`` so it does NOT run on plain `manage.py check` or in the test
     suite's own Django checks — only when `--deploy` is passed explicitly.
  2. A loud logger.error() from enqueue() itself when the inline fallback actually
     runs with DEBUG=False, so a broker that dies mid-flight (after a clean boot)
     still screams into prod logs instead of silently dropping work.
"""
from django.core.checks import Error
from django.test import SimpleTestCase, override_settings

from config.checks import celery_broker_configured_for_durability


class BrokerDeployCheckTests(SimpleTestCase):
    """kepoli.E002: deploy check for a durable Celery broker in production."""

    @override_settings(DEBUG=False, CELERY_BROKER_URL="")
    def test_errors_when_debug_false_and_broker_missing(self):
        issues = celery_broker_configured_for_durability(None)
        self.assertEqual(len(issues), 1)
        self.assertIsInstance(issues[0], Error)
        self.assertEqual(issues[0].id, "kepoli.E002")
        self.assertIn("CELERY_BROKER_URL", issues[0].msg)

    @override_settings(DEBUG=True, CELERY_BROKER_URL="")
    def test_returns_nothing_when_debug_true(self):
        # Dev/local/test: the inline fallback is the intended, documented behaviour.
        issues = celery_broker_configured_for_durability(None)
        self.assertEqual(issues, [])

    @override_settings(DEBUG=False, CELERY_BROKER_URL="redis://:pw@localhost:6379/0")
    def test_returns_nothing_when_broker_url_set(self):
        issues = celery_broker_configured_for_durability(None)
        self.assertEqual(issues, [])

    @override_settings(DEBUG=True, CELERY_BROKER_URL="redis://:pw@localhost:6379/0")
    def test_returns_nothing_when_debug_true_and_broker_set(self):
        issues = celery_broker_configured_for_durability(None)
        self.assertEqual(issues, [])


class InlineFallbackLoudLogTests(SimpleTestCase):
    """enqueue() must scream (logger.error) when it runs the lossy inline fallback
    with DEBUG=False, and must NOT do so in the normal dev/test (DEBUG=True) path —
    that fallback is expected/quiet there."""

    @override_settings(CELERY_BROKER_URL="", DEBUG=False)
    def test_logs_error_on_inline_fallback_when_debug_false(self):
        from unittest.mock import MagicMock, patch
        from accounts.tasks import enqueue

        task = MagicMock()
        with patch("accounts.tasks._inline_executor") as executor, \
                patch("accounts.tasks.logger") as logger:
            enqueue(task, "x")
            executor.submit.assert_called_once()
            logger.error.assert_called_once()
            # message names the task and mentions the broker setting
            args = logger.error.call_args[0]
            self.assertIn("PROD inline task fallback", args[0])

    @override_settings(CELERY_BROKER_URL="", DEBUG=True)
    def test_no_error_log_on_inline_fallback_when_debug_true(self):
        from unittest.mock import MagicMock, patch
        from accounts.tasks import enqueue

        task = MagicMock()
        with patch("accounts.tasks._inline_executor") as executor, \
                patch("accounts.tasks.logger") as logger:
            enqueue(task, "x")
            executor.submit.assert_called_once()
            logger.error.assert_not_called()

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/0", DEBUG=False)
    def test_no_error_log_when_broker_dispatch_succeeds(self):
        from unittest.mock import MagicMock, patch
        from accounts.tasks import enqueue

        task = MagicMock()
        with patch("accounts.tasks.logger") as logger:
            enqueue(task, "x")
            task.delay.assert_called_once_with("x")
            logger.error.assert_not_called()
