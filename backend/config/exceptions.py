import logging

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("security.throttle")


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
    return response
