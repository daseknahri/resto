import os


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value < 0:
        return default
    return value


def init_sentry() -> None:
    dsn = (os.getenv("DJANGO_SENTRY_DSN", "") or "").strip()
    if not dsn:
        return

    from sentry_sdk import init as sentry_init
    from sentry_sdk.integrations.django import DjangoIntegration

    release = (os.getenv("DJANGO_SENTRY_RELEASE", "") or "").strip() or None
    environment = (os.getenv("DJANGO_SENTRY_ENVIRONMENT", "") or "").strip()
    if not environment:
        environment = (os.getenv("APP_ENV", "") or "").strip() or "production"

    sentry_init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=environment,
        release=release,
        traces_sample_rate=_float_env("DJANGO_SENTRY_TRACES_SAMPLE_RATE", 0.0),
        send_default_pii=_bool_env("DJANGO_SENTRY_SEND_PII", False),
    )
