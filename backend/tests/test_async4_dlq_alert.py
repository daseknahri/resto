"""RISK ASYNC-4 residual: alert when a customer-notification task exhausts its retries.

The dedupe half of ASYNC-4 is already shipped; this covers the DLQ residual — a paid /
customer-facing send that fails terminally (autoretry exhausted) must not vanish silently into a
`NotificationLog(status=failed)` row, it must raise a loud, PII-free ops alert.

Mock-free / DB-free: `on_failure` is Celery's terminal-failure hook; we invoke it directly.
"""
from django.test import SimpleTestCase

from accounts.tasks import (
    _NotificationTask,
    customer_order_milestone,
    recipient_track_sms,
    sms_order_ready,
    whatsapp_new_order,
)


class NotificationRetryExhaustionAlertTests(SimpleTestCase):
    # (task, representative args) — some args carry PII (phone numbers) that must NEVER be logged.
    _TASKS = [
        (sms_order_ready, ("+212600112233", "Tacos House", "ORD-9", 7)),
        (whatsapp_new_order, ("t_demo", 42, "Tacos House", "+212600112233", 7)),
        (customer_order_milestone, ("ORD-9", 7, "ready")),
        (recipient_track_sms, (99, "picked_up")),
    ]

    def test_all_four_notification_tasks_alert_on_terminal_failure(self):
        for task, args in self._TASKS:
            with self.assertLogs("accounts.tasks", level="ERROR") as cm:
                task.on_failure(RuntimeError("provider 500"), "task-id-1", args=args, kwargs={}, einfo=None)
            out = "\n".join(cm.output)
            self.assertIn(task.name, out, f"{task.name}: alert must name the dropped task")
            self.assertIn("RuntimeError", out, f"{task.name}: alert must name the exception type")

    def test_alert_never_logs_pii_from_args(self):
        with self.assertLogs("accounts.tasks", level="ERROR") as cm:
            sms_order_ready.on_failure(
                RuntimeError("boom"), "task-id-2",
                args=("+212600112233", "Tacos House", "ORD-9", 7), kwargs={"phone": "+212600112233"},
                einfo=None,
            )
        out = "\n".join(cm.output)
        self.assertNotIn("+212600112233", out)   # phone number (PII) must not appear
        self.assertNotIn("Tacos House", out)     # no raw args echoed at all

    def test_only_terminal_failure_alerts_not_intermediate_retries(self):
        # on_failure is Celery's TERMINAL hook; the base deliberately does NOT override on_retry,
        # so an intermediate autoretry stays silent (no false alert on every attempt).
        self.assertIn("on_failure", _NotificationTask.__dict__)
        self.assertNotIn("on_retry", _NotificationTask.__dict__)
