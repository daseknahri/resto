"""RISK ASYNC-1: durable outbox for the inline (no-broker) task fallback.

``accounts.tasks.enqueue`` persists an ``OutboxMessage`` before running a task on the
in-process inline pool; ``_run_inline`` deletes it on success (leaves it PENDING on
failure); the ``relay_outbox`` command re-dispatches rows left pending past a grace
window. Most tests are mock-based (SimpleTestCase, no DB) — the ORM is patched. One
DB-backed test exercises the relay's real select_for_update loop / grace filter /
max-attempts in CI.
"""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, override_settings

from accounts import tasks
from accounts.management.commands import relay_outbox


class SerializationTests(SimpleTestCase):
    def test_decimal_round_trips_exactly(self):
        enc = tasks._encode_seq((7, "Cafe", Decimal("12.50")))
        self.assertEqual(enc, [7, "Cafe", {"__decimal__": "12.50"}])  # JSON-safe
        dec = tasks._decode_seq(enc)
        self.assertEqual(dec, [7, "Cafe", Decimal("12.50")])
        self.assertIsInstance(dec[2], Decimal)

    def test_none_inputs_are_safe(self):
        self.assertEqual(tasks._decode_seq(None), [])
        self.assertEqual(tasks._decode_map(None), {})

    def test_kwargs_round_trip(self):
        m = {"amount": Decimal("1.00"), "n": 3, "s": "x"}
        self.assertEqual(tasks._decode_map(tasks._encode_map(m)), m)

    def test_plain_dict_arg_not_mistaken_for_a_decimal_tag(self):
        self.assertEqual(tasks._decode_arg({"a": 1}), {"a": 1})
        self.assertEqual(tasks._decode_arg({"__decimal__": "1", "x": 2}), {"__decimal__": "1", "x": 2})


class PersistOutboxTests(SimpleTestCase):
    def _task(self, name="accounts.tasks.sms_order_ready"):
        t = mock.Mock()
        t.name = name
        return t

    def test_persists_encoded_row_in_public_and_returns_pk(self):
        Outbox = mock.Mock()
        Outbox.objects.create.return_value = mock.Mock(pk=42)
        with mock.patch("accounts.models.OutboxMessage", Outbox), \
                mock.patch("accounts.tasks.schema_context") as ctx:
            pk = tasks._persist_outbox(self._task(), (1, Decimal("2.00")), {"k": "v"})
        self.assertEqual(pk, 42)
        ctx.assert_called_once_with("public")
        Outbox.objects.create.assert_called_once_with(
            task_name="accounts.tasks.sms_order_ready",
            args=[1, {"__decimal__": "2.00"}],
            kwargs={"k": "v"},
        )

    def test_unnamed_task_returns_none_without_touching_db(self):
        t = mock.Mock()
        t.name = ""
        with mock.patch("accounts.models.OutboxMessage") as Outbox:
            self.assertIsNone(tasks._persist_outbox(t, (), {}))
            Outbox.objects.create.assert_not_called()

    def test_persist_failure_returns_none_never_raises(self):
        Outbox = mock.Mock()
        Outbox.objects.create.side_effect = RuntimeError("db down")
        with mock.patch("accounts.models.OutboxMessage", Outbox), \
                mock.patch("accounts.tasks.schema_context"):
            self.assertIsNone(tasks._persist_outbox(self._task(), (), {}))


class ClearOutboxTests(SimpleTestCase):
    def test_none_is_a_noop(self):
        with mock.patch("accounts.models.OutboxMessage") as Outbox:
            tasks._clear_outbox(None)
            Outbox.objects.filter.assert_not_called()

    def test_deletes_row_in_public(self):
        Outbox = mock.Mock()
        with mock.patch("accounts.models.OutboxMessage", Outbox), \
                mock.patch("accounts.tasks.schema_context") as ctx:
            tasks._clear_outbox(7)
        ctx.assert_called_once_with("public")
        Outbox.objects.filter.assert_called_once_with(pk=7)
        Outbox.objects.filter.return_value.delete.assert_called_once()


@override_settings(CELERY_BROKER_URL="", DEBUG=False)
class EnqueueInlineProdTests(SimpleTestCase):
    def test_prod_inline_path_persists_then_submits_with_outbox_id(self):
        t = mock.Mock()
        t.name = "accounts.tasks.sms_order_ready"
        with mock.patch("accounts.tasks._persist_outbox", return_value=99) as persist, \
                mock.patch.object(tasks._inline_executor, "submit") as submit:
            tasks.enqueue(t, "a", k=1)
        persist.assert_called_once_with(t, ("a",), {"k": 1})
        submit.assert_called_once_with(tasks._run_inline, t, ("a",), {"k": 1}, 99)


@override_settings(CELERY_BROKER_URL="", DEBUG=True)
class EnqueueInlineDevTests(SimpleTestCase):
    def test_dev_inline_path_skips_the_outbox(self):
        # In dev/tests the durable outbox is intentionally OFF (inline is lossy by
        # design) — no DB write, submit gets outbox_id=None.
        t = mock.Mock()
        t.name = "accounts.tasks.sms_order_ready"
        with mock.patch("accounts.tasks._persist_outbox") as persist, \
                mock.patch.object(tasks._inline_executor, "submit") as submit:
            tasks.enqueue(t, "a", k=1)
        persist.assert_not_called()
        submit.assert_called_once_with(tasks._run_inline, t, ("a",), {"k": 1}, None)


@override_settings(CELERY_BROKER_URL="redis://x")
class EnqueueBrokerTests(SimpleTestCase):
    def test_broker_path_never_persists_or_runs_inline(self):
        t = mock.Mock()
        t.name = "x"
        with mock.patch("accounts.tasks._persist_outbox") as persist, \
                mock.patch.object(tasks._inline_executor, "submit") as submit:
            tasks.enqueue(t, 1)
        t.delay.assert_called_once_with(1)
        persist.assert_not_called()
        submit.assert_not_called()


class RunInlineTests(SimpleTestCase):
    def test_success_clears_the_outbox_row(self):
        t = mock.Mock()
        t.name = "x"
        with mock.patch("accounts.tasks._clear_outbox") as clear:
            tasks._run_inline(t, (1,), {}, outbox_id=5)
        t.run.assert_called_once_with(1)
        clear.assert_called_once_with(5)

    def test_failure_leaves_the_outbox_row_pending(self):
        t = mock.Mock()
        t.name = "x"
        t.run.side_effect = RuntimeError("boom")
        with mock.patch("accounts.tasks._clear_outbox") as clear:
            tasks._run_inline(t, (), {}, outbox_id=5)  # must not raise
        clear.assert_not_called()


class RelayDispatchTests(SimpleTestCase):
    def _row(self, name="accounts.tasks.sms_order_ready", args=None, kwargs=None):
        return mock.Mock(task_name=name, args=args or [], kwargs=kwargs or {})

    @override_settings(CELERY_BROKER_URL="redis://x")
    def test_broker_up_uses_delay_and_decodes_decimal(self):
        task = mock.Mock()
        with mock.patch.object(relay_outbox.current_app, "tasks", {"t": task}):
            ok, err = relay_outbox._dispatch(self._row(name="t", args=[1, {"__decimal__": "2.00"}]))
        self.assertTrue(ok)
        task.delay.assert_called_once_with(1, Decimal("2.00"))
        task.run.assert_not_called()

    @override_settings(CELERY_BROKER_URL="")
    def test_no_broker_runs_inline(self):
        task = mock.Mock()
        with mock.patch.object(relay_outbox.current_app, "tasks", {"t": task}):
            ok, _ = relay_outbox._dispatch(self._row(name="t"))
        self.assertTrue(ok)
        task.run.assert_called_once()

    def test_unknown_task_reports_failure(self):
        with mock.patch.object(relay_outbox.current_app, "tasks", {}):
            ok, err = relay_outbox._dispatch(self._row(name="gone"))
        self.assertFalse(ok)
        self.assertIn("gone", err)

    @override_settings(CELERY_BROKER_URL="redis://x")
    def test_task_exception_is_reported_not_raised(self):
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker flap")
        with mock.patch.object(relay_outbox.current_app, "tasks", {"t": task}):
            ok, err = relay_outbox._dispatch(self._row(name="t"))
        self.assertFalse(ok)
        self.assertIn("broker flap", err)


# ── DB-backed relay loop (runs in CI; errors locally without Postgres, per the
# known no-DB baseline) — exercises the real select_for_update / grace / max-attempts. ──
from datetime import timedelta  # noqa: E402

from django.core.management import call_command  # noqa: E402
from django.test import TransactionTestCase  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import OutboxMessage  # noqa: E402


class RelayLoopDBTests(TransactionTestCase):
    """The relay's real select_for_update / grace filter / max-attempts loop."""

    def _make(self, age_seconds, *, status=OutboxMessage.Status.PENDING, attempts=0):
        row = OutboxMessage.objects.create(
            task_name="accounts.tasks.sms_order_ready", args=[1], status=status, attempts=attempts
        )
        # created_at is auto_now_add; backdate it to simulate an aged row.
        OutboxMessage.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(seconds=age_seconds)
        )
        return row.pk

    def test_dispatches_old_pending_and_skips_young(self):
        old = self._make(age_seconds=relay_outbox.RELAY_GRACE_SECONDS + 60)
        young = self._make(age_seconds=10)  # inside the grace window
        with mock.patch.object(relay_outbox, "_dispatch", return_value=(True, "")):
            call_command("relay_outbox")
        self.assertFalse(OutboxMessage.objects.filter(pk=old).exists())   # relayed → deleted
        self.assertTrue(OutboxMessage.objects.filter(pk=young).exists())  # too young → untouched

    def test_failure_bumps_attempts_then_marks_failed(self):
        pk = self._make(age_seconds=relay_outbox.RELAY_GRACE_SECONDS + 60,
                        attempts=relay_outbox.RELAY_MAX_ATTEMPTS - 1)
        with mock.patch.object(relay_outbox, "_dispatch", return_value=(False, "boom")):
            call_command("relay_outbox")
        row = OutboxMessage.objects.get(pk=pk)
        self.assertEqual(row.status, OutboxMessage.Status.FAILED)
        self.assertEqual(row.attempts, relay_outbox.RELAY_MAX_ATTEMPTS)
        self.assertIn("boom", row.last_error)

    def test_transient_failure_stays_pending_with_bumped_attempts(self):
        pk = self._make(age_seconds=relay_outbox.RELAY_GRACE_SECONDS + 60, attempts=0)
        with mock.patch.object(relay_outbox, "_dispatch", return_value=(False, "flap")):
            call_command("relay_outbox")
        row = OutboxMessage.objects.get(pk=pk)
        self.assertEqual(row.status, OutboxMessage.Status.PENDING)
        self.assertEqual(row.attempts, 1)
