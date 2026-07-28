"""
Celery application for resto.

Broker + result backend come from CELERY_BROKER_URL / CELERY_RESULT_BACKEND (which
default to REDIS_URL — see settings). When no broker is configured the app still
imports fine; the dispatch layer (accounts.tasks.enqueue) detects the missing broker
and runs work inline in a daemon thread instead, so dev/local and any no-Redis deploy
keep working exactly as before.

Run in production (Coolify "Scheduled Tasks" / extra processes):
    celery -A config worker -l info -Q notifications,cron
    celery -A config beat   -l info     # only if you want Beat to own the cron jobs

RISK ASYNC-2: every Beat cron/sweep entry dispatches a dedicated ``cron.<command>``
``@shared_task`` (accounts/tasks.py) — the task name IS the allowlist (no task takes an
arbitrary command name off the broker). The whole ``cron.*`` namespace is routed to the
"cron" queue (CELERY_TASK_ROUTES in settings.py) so a slow sweep can't starve
customer-facing notification tasks, which stay on the default "notifications" queue. The
sweep tasks also carry retry/backoff on a transient DB error so a Postgres blip during a
tick retries instead of dropping it.

A production worker MUST consume BOTH queues (``-Q notifications,cron`` as above), or —
better for isolation — run a SECOND worker dedicated to the "cron" queue so a slow sweep
never occupies a notification worker slot. The worker in docker-compose.coolify.yml is
set to ``-Q notifications,cron``.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("resto")
# All CELERY_* settings are read from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")
# Discover tasks.py in every installed app (accounts.tasks, etc.).
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):  # pragma: no cover - smoke task
    return f"request: {self.request!r}"
