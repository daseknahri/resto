import logging
import os

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("security.throttle")

try:
    import sentry_sdk
except Exception:  # pragma: no cover - optional dependency at runtime
    sentry_sdk = None


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float = 0.0) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


SENTRY_CAPTURE_THROTTLE = _bool_env("DJANGO_SENTRY_CAPTURE_THROTTLE", False)
SENTRY_THROTTLE_MIN_WAIT_SECONDS = _float_env("DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS", 30.0)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if isinstance(exc, Throttled):
        request = context.get("request")
        view = context.get("view")
        user = getattr(request, "user", None) if request else None
        username = user.username if user and user.is_authenticated else "anonymous"
        logger.warning(
            "throttle.blocked scope=%s path=%s method=%s ip=%s user=%s wait=%s",
            getattr(view, "throttle_scope", "unknown"),
            getattr(request, "path", ""),
            getattr(request, "method", ""),
            request.META.get("REMOTE_ADDR") if request else "",
            username,
            getattr(exc, "wait", None),
        )
        wait_seconds = float(getattr(exc, "wait", 0) or 0)
        if (
            SENTRY_CAPTURE_THROTTLE
            and sentry_sdk is not None
            and wait_seconds >= SENTRY_THROTTLE_MIN_WAIT_SECONDS
        ):
            scope_name = getattr(view, "throttle_scope", "unknown")
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("security_event", "throttle_blocked")
                scope.set_tag("throttle_scope", scope_name)
                scope.set_context(
                    "throttle",
                    {
                        "scope": scope_name,
                        "path": getattr(request, "path", ""),
                        "method": getattr(request, "method", ""),
                        "ip": request.META.get("REMOTE_ADDR") if request else "",
                        "user": username,
                        "wait_seconds": wait_seconds,
                    },
                )
                sentry_sdk.capture_message("security.throttle.blocked", level="warning")
    return response
