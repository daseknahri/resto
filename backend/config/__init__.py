"""resto config package.

Import the Celery app so the @shared_task decorator + `celery -A config` discover it.
Guarded so a Celery import problem can never stop Django from booting.
"""
try:
    from .celery import app as celery_app  # noqa: F401

    __all__ = ("celery_app",)
except Exception:  # pragma: no cover - defensive: never block Django startup
    celery_app = None
    __all__ = ()
