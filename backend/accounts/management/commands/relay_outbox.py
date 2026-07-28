"""Re-dispatch durable outbox tasks left pending by a crashed/restarted inline run.

RISK ASYNC-1. ``accounts.tasks.enqueue`` persists an ``OutboxMessage`` before running a
task on the in-process inline pool (the no-broker / broker-outage fallback); the row is
deleted on success. If the process dies mid-run the row stays ``pending`` — this command,
run at boot from ``docker/entrypoint.sh`` (before the server starts serving), re-dispatches
those rows: via the broker if one is now configured (durable), else inline again.

Safety:
  * Only rows older than ``RELAY_GRACE_SECONDS`` are touched, so a task still running in a
    live process (this container just booted, but a sibling container may be mid-run) is not
    prematurely re-sent.
  * Each row is claimed with ``select_for_update(skip_locked=True)`` so concurrent relays
    across containers never grab the same row.
  * One dispatch attempt per row per run; after ``RELAY_MAX_ATTEMPTS`` a row is marked
    ``failed`` and logged loudly rather than retried forever.
  * Re-dispatch is at-least-once; the notification tasks are idempotent via their ASYNC-4
    dedup keys, so a duplicate relay does not double-send.
"""
import logging
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

RELAY_GRACE_SECONDS = 300   # leave rows younger than this alone (may be running live)
RELAY_MAX_ATTEMPTS = 5      # give up (→ failed) after this many relay attempts
RELAY_BATCH = 500           # cap rows handled per invocation


def _dispatch(row):
    """Re-dispatch one outbox row. Returns (ok, error_str). Never raises."""
    from accounts.tasks import _decode_map, _decode_seq

    task = current_app.tasks.get(row.task_name)
    if task is None:
        return False, f"unknown task {row.task_name!r}"
    args, kwargs = _decode_seq(row.args), _decode_map(row.kwargs)
    try:
        if getattr(settings, "CELERY_BROKER_URL", ""):
            task.delay(*args, **kwargs)     # broker back up → durable re-dispatch
        else:
            task.run(*args, **kwargs)       # still no broker → run it inline now
        return True, ""
    except Exception as exc:  # noqa: BLE001 — report, don't crash the relay
        return False, repr(exc)


class Command(BaseCommand):
    help = "Re-dispatch outbox tasks left pending by a crashed inline run (RISK ASYNC-1)."

    def handle(self, *args, **options):
        from accounts.models import OutboxMessage

        cutoff = timezone.now() - timedelta(seconds=RELAY_GRACE_SECONDS)
        with schema_context("public"):
            ids = list(
                OutboxMessage.objects.filter(
                    status=OutboxMessage.Status.PENDING, created_at__lt=cutoff
                )
                .order_by("created_at")
                .values_list("pk", flat=True)[:RELAY_BATCH]
            )

        relayed = failed = skipped = 0
        for pk in ids:
            with transaction.atomic(), schema_context("public"):
                row = (
                    OutboxMessage.objects.select_for_update(skip_locked=True)
                    .filter(pk=pk, status=OutboxMessage.Status.PENDING)
                    .first()
                )
                if row is None:
                    skipped += 1  # another relay/container claimed it
                    continue
                ok, err = _dispatch(row)
                row.attempts += 1
                if ok:
                    row.delete()
                    relayed += 1
                elif row.attempts >= RELAY_MAX_ATTEMPTS:
                    row.status = OutboxMessage.Status.FAILED
                    row.last_error = err[:500]
                    row.save(update_fields=["attempts", "status", "last_error", "updated_at"])
                    failed += 1
                    logger.error(
                        "ASYNC-1 outbox message %s (%s) FAILED after %s attempts: %s",
                        row.pk, row.task_name, row.attempts, err,
                    )
                else:
                    row.last_error = err[:500]
                    row.save(update_fields=["attempts", "last_error", "updated_at"])

        self.stdout.write(
            f"relay_outbox: relayed={relayed} failed={failed} skipped={skipped} "
            f"scanned={len(ids)}"
        )
