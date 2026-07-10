# ADR-0009: Async & realtime — Celery-optional, generic cron task, Channels-as-hints

- **Status:** Accepted — thoughtful and degrades well; growth-limiting choices to fix before volume
- **Date:** documented 2026-07-10
- **Related risk:** [ASYNC-1](../RISK_REGISTER.md), [ASYNC-2](../RISK_REGISTER.md), [ASYNC-3](../RISK_REGISTER.md), [ASYNC-4](../RISK_REGISTER.md), [OPS-3](../RISK_REGISTER.md)

## Context
Kepoli needs background work (notifications, delivery sweeps, reconciliation), scheduled jobs, and
live order updates for kitchen/customer screens — while staying runnable in dev with minimal infra.

## Decision
- **Celery is opt-in.** `CELERY_BROKER_URL` gates it. `accounts/tasks.py` `enqueue()` uses
  `task.delay()` when set; when unset it runs the task **inline on a bounded in-process
  `ThreadPoolExecutor(max_workers=4)`** (closing the DB connection in `finally`).
- **Scheduled jobs go through ONE generic task**, `run_management_command`, gated by a hardcoded
  23-entry allowlist, wired to ~23 `CELERY_BEAT_SCHEDULE` cron entries. A `write_beat_heartbeat`
  task + `/api/health/` gives beat-liveness observability.
- **Realtime = hints, not data.** Channels 4 + `channels_redis`; `_broadcast_order_change` sends
  only `{order_number, status, payment_status}`; clients refetch over authenticated HTTP.
  `CustomerOrderConsumer` has a real ownership gate.

## Consequences

### Good
- **Realtime is correctly a hint channel** — a lost/dup/reordered frame is harmless because the
  client reconciles over HTTP. This is the right invariant and it's held consistently.
- The inline fallback's connection-exhaustion risk was **anticipated and mitigated** (bounded pool +
  `connection.close()`), not naive.
- Sweep commands are **idempotent and concurrency-safe** (`select_for_update` re-validation, capped
  redispatch, cache-throttled pushes).
- Beat liveness is observable via the heartbeat→health-check pattern.

### Bad / honest tradeoffs
- **ASYNC-1: inline fallback isn't durable.** When the broker is unset (a likely default), `.run()`
  bypasses `autoretry_for` and any queued work evaporates on the rolling restart every deploy does —
  a dropped SMS/nudge with no record.
- **ASYNC-2: one generic cron task on a single 2-worker queue.** No per-job retry/routing/metrics; a
  slow `sweep_delivery_jobs` starves notification delivery because they share the queue; the
  allowlist is a second list that drifts from the beat schedule.
- **ASYNC-3: WS + full-rate polling both run.** `OrderStatus` polls 15s even when the socket is live;
  `OwnerOrders` doesn't even use the (already-built) `useOwnerRealtime`. You pay for realtime and
  keep the polling load — cost without the savings.
- **ASYNC-4: `acks_late` without `task_reject_on_worker_lost`, dedupe, or a DLQ** → a worker killed
  mid-send redelivers and re-runs → duplicate SMS/email (cost + trust), exactly under load.
- **OPS-3: one Redis** for cache + sessions + Channels + broker (see [ADR-0007](0007-single-node-deploy.md)).

## Alternatives considered
- **Named `@shared_task`s + `task_routes`** (sweeps → `cron` queue, notifications → their own) with
  per-task retry, deleting the allowlist (the task name *is* the allowlist). The recommended target.
- **Broker required in prod** (fail-closed if unset) so "durable" is actually durable.
- **WS-primary with polling gated on `connectionState !== 'live'`** to make realtime substitutive.

## When to revisit
Before onboarding volume: fix ASYNC-1 (require broker / durable outbox), ASYNC-2 (named tasks +
routing + retry), ASYNC-3 (gate polling on WS state). ASYNC-4 and OPS-3 (Redis split) are the next
wall after that. Drop the unused `daphne` dep ([OPS-4](../RISK_REGISTER.md)) while you're here.
