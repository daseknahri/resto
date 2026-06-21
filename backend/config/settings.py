import os
from pathlib import Path
from urllib.parse import urlparse

from celery.schedules import crontab

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_or_none(var_name: str):
    """Return the env var's value, or None if it is absent OR empty/whitespace.

    Coolify (and docker-compose `${VAR}` interpolation generally) passes unset
    variables as an empty string rather than omitting them, so
    `os.getenv(name, default)` returns "" instead of the default. Treating an
    empty value as absent restores the intended default-fallback behavior and
    avoids crashes like int("").
    """
    value = os.getenv(var_name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def parse_csv_env(var_name: str, default: str) -> list[str]:
    raw = _env_or_none(var_name)
    source = raw if raw is not None else default
    return [item.strip() for item in source.split(",") if item.strip()]


def parse_bool_env(var_name: str, default: bool = False) -> bool:
    value = _env_or_none(var_name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def parse_int_env(var_name: str, default: int) -> int:
    value = _env_or_none(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def hostname_from_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").strip().lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


_raw_secret = os.getenv("DJANGO_SECRET_KEY", "").strip()
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

# Known placeholder / template values that must never be used in production.
_INSECURE_SECRET_KEYS = frozenset({
    "", "change-me", "changeme", "secret", "django-insecure",
    "your-secret-key", "your_secret_key", "example",
})

if not _raw_secret or _raw_secret in _INSECURE_SECRET_KEYS:
    if DEBUG:
        # Dev convenience: auto-generate a temporary key so the server starts
        # without env configuration.  A warning is printed so it's obvious.
        import secrets as _secrets
        _raw_secret = _secrets.token_hex(50)
        import warnings as _warnings
        _warnings.warn(
            "DJANGO_SECRET_KEY is not set (or is a placeholder) — using a "
            "temporary random key.  Sessions will be invalidated on every "
            "restart.  Set DJANGO_SECRET_KEY in production.",
            stacklevel=2,
        )
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY must be set to a strong random value in "
            "production (DEBUG=False).  The current value is missing or is a "
            "known placeholder.  Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_hex(50))\""
        )
SECRET_KEY = _raw_secret
MEDIA_STORAGE_BACKEND = os.getenv("DJANGO_MEDIA_STORAGE_BACKEND", "local").strip().lower()
USE_S3_MEDIA_STORAGE = MEDIA_STORAGE_BACKEND in {"s3", "s3boto3", "object"}
allowed_hosts = set(parse_csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost"))
# In dev always allow localhost variants; in production the env var should list
# the real domains and .localhost is stripped out automatically (it must not
# appear in production ALLOWED_HOSTS to prevent host-header injection from
# bypassing any per-domain routing logic).
if DEBUG:
    allowed_hosts.update({"localhost", "127.0.0.1", ".localhost"})
else:
    allowed_hosts.update({"localhost", "127.0.0.1"})
ALLOWED_HOSTS = sorted(allowed_hosts)

csrf_trusted_origins = set(
    parse_csv_env(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://*.localhost:5173",
    )
)
csrf_trusted_origins.update(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://*.localhost:5173",
    }
)
CSRF_TRUSTED_ORIGINS = sorted(csrf_trusted_origins)

SHARED_APPS = [
    "django_tenants",
    # R5: enables django.contrib.postgres.operations.AddIndexConcurrently so hot-table
    # index migrations can build without an ACCESS EXCLUSIVE lock (no models → adds no
    # migrations). See backend/MIGRATIONS.md for the atomic=False/CONCURRENTLY pattern.
    "django.contrib.postgres",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "accounts",
    "tenancy",
    "sales",
]
if USE_S3_MEDIA_STORAGE:
    SHARED_APPS.append("storages")

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "menu",
]

# ── Real-time (Django Channels) — optional, activates only when installed ──────
# Keeping it conditional means the HTTP app and the existing polling keep working
# whether or not channels/daphne are present (e.g. before the WS infra is deployed).
try:
    import channels  # noqa: F401
    HAS_CHANNELS = True
except Exception:  # pragma: no cover
    HAS_CHANNELS = False

if HAS_CHANNELS:
    # daphne must precede staticfiles (its runserver command); django_tenants stays first.
    if "channels" not in SHARED_APPS:
        SHARED_APPS.insert(1, "channels")
    if "daphne" not in SHARED_APPS:
        SHARED_APPS.insert(1, "daphne")

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

if HAS_CHANNELS:
    ASGI_APPLICATION = "config.asgi.application"

MIDDLEWARE = [
    "config.middleware.TenantAwareMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
PUBLIC_SCHEMA_URLCONF = "config.public_urls"
TENANT_URLCONF = "config.urls"
TENANT_MODEL = "tenancy.Tenant"
TENANT_DOMAIN_MODEL = "tenancy.Domain"
PUBLIC_SCHEMA_NAME = "public"

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", "postgres://user:pass@localhost:5432/resto"),
        conn_max_age=600,
    )
}
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DATABASE_ROUTERS = (
    "django_tenants.routers.TenantSyncRouter",
)

# ── Cache (Redis when REDIS_URL is set; falls back to in-process LocMemCache) ──
# Set REDIS_URL in your .env / Coolify environment to enable shared Redis cache.
# IGNORE_EXCEPTIONS=True lets the site degrade gracefully (DB fallback) if Redis
# is temporarily unreachable — no 500 errors, just a slower cache miss.
_REDIS_URL = os.getenv("REDIS_URL", "").strip()
if _REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "resto",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# ── Channel layer (real-time) ──────────────────────────────────────────────────
# Redis layer when REDIS_URL is set (required for multi-process/multi-worker prod
# so a broadcast from a web worker reaches every connected socket). Without Redis
# we fall back to an in-memory layer (single-process dev only).
if HAS_CHANNELS:
    if _REDIS_URL:
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [_REDIS_URL], "prefix": "resto:ws"},
            }
        }
    else:
        CHANNEL_LAYERS = {
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
        }

# ── Celery (durable task queue for notifications + scheduled jobs) ──────────────
# OPT-IN. Celery is OFF unless CELERY_BROKER_URL is explicitly set — even when REDIS_URL
# is configured for cache/channels. While off, accounts.tasks.enqueue() runs work inline
# in a daemon thread (the historical behaviour), so notifications send fine with NO worker.
#
# To turn the durable queue ON: set CELERY_BROKER_URL (typically to the same value as
# REDIS_URL) AND run a worker (`celery -A config worker`). IMPORTANT: don't set the broker
# without running a worker — tasks would queue in Redis and never be processed (= silently
# dropped notifications). It's broker-set ⇔ worker-running, together.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip() or (CELERY_BROKER_URL or None)
CELERY_TASK_DEFAULT_QUEUE = "notifications"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 120          # hard kill a stuck send after 2 min
CELERY_TASK_SOFT_TIME_LIMIT = 90
CELERY_WORKER_MAX_TASKS_PER_CHILD = 500
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
# Beat schedule — only used if you run `celery -A config beat`. Lets Beat own the cron
# jobs instead of Coolify Scheduled Tasks (either works; don't run both for the same job).
CELERY_BEAT_SCHEDULE = {
    # Observability: stamp the cache key /api/health/ reads so a dead beat/worker becomes
    # visible. Runs every 60s; the probe flags STALE (> 180s) once a broker is configured.
    "write-beat-heartbeat": {
        "task": "accounts.tasks.write_beat_heartbeat",
        "schedule": 60.0,
    },
    "release-scheduled-orders": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 300.0,  # every 5 min
        "args": ("release_scheduled_orders",),
    },
    "escalate-stale-pending-orders": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 180.0,  # every 3 min — catch unconfirmed orders past the tenant SLA
        "args": ("escalate_stale_pending_orders",),
    },
    "send-predispatch-reminders": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 900.0,  # every 15 min — window is 35 min wide so every order is caught
        "args": ("send_predispatch_reminders",),
    },
    "send-ride-predispatch-reminders": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 900.0,  # every 15 min — window is 20 min wide so every trip is caught
        "args": ("send_ride_predispatch_reminders",),
    },
    "check-car-doc-expiry": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily
        "args": ("check_car_doc_expiry",),
    },
    "send-review-prompts": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 900.0,  # every 15 min
        "args": ("send_review_prompts",),
    },
    "send-reservation-reminders": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 3600.0,  # hourly
        "args": ("send_reservation_reminders",),
    },
    "expire-charge-requests": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 600.0,  # every 10 min
        "args": ("expire_charge_requests",),
    },
    "sweep-delivery-jobs": {
        "task": "accounts.tasks.run_management_command",
        # every 60s — advance ranked-offer cascades (60s offer window) + recover stuck jobs.
        "schedule": 60.0,
        "args": ("sweep_delivery_jobs",),
    },
    "sweep-ride-requests": {
        "task": "accounts.tasks.run_management_command",
        # every 120s — re-dispatch, auto-cancel, and release stale-driver ride requests.
        "schedule": 120.0,
        "args": ("sweep_ride_requests",),
    },
    "enforce-subscriptions": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily
        "args": ("enforce_subscriptions",),
        "kwargs": {"apply": True},
    },
    # ── Daily maintenance — bound table growth + keep FX rates fresh ──────────────
    "fetch-currency-rates": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — refresh MAD exchange rates
        "args": ("fetch_currency_rates",),
    },
    "send-daily-summary": {
        "task": "accounts.tasks.run_management_command",
        # 23:30 UTC ≈ 00:30 Morocco (UTC+1) — after the last orders of the day have settled.
        "schedule": crontab(hour=23, minute=30),
        "args": ("send_daily_summary",),
    },
    "auto-reset-availability": {
        "task": "accounts.tasks.run_management_command",
        # Hourly sweep — each tenant's local 05:00 is checked inside the command.
        "schedule": 3600.0,
        "args": ("auto_reset_availability",),
    },
    "send-winback-nudges": {
        "task": "accounts.tasks.run_management_command",
        # Hourly sweep — each tenant's local 11:00 is checked inside the command.
        "schedule": 3600.0,
        "args": ("send_winback_nudges",),
    },
    "prune-analytics-events": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — delete analytics events older than 90 days
        "args": ("prune_analytics_events",),
    },
    "prune-admin-audit-logs": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — honour ADMIN_AUDIT_RETENTION_DAYS (default 180)
        "args": ("prune_admin_audit_logs",),
    },
    # OPS-4 E: retention crons for unbounded shared/tenant tables.
    "prune-notification-logs": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — delete NotificationLog rows older than 180 days
        "args": ("prune_notification_logs",),
    },
    "prune-winback-nudges": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — delete WinbackNudge rows older than 120 days
        "args": ("prune_winback_nudges",),
    },
    "prune-staff-messages": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — delete StaffMessage rows older than 90 days
        "args": ("prune_staff_messages",),
    },
    # OPS-5c item 4: prune consumed/expired auth tokens (PasswordResetToken + ActivationToken)
    "prune-auth-tokens": {
        "task": "accounts.tasks.run_management_command",
        "schedule": 86400.0,  # daily — delete rows older than 30 days
        "args": ("prune_auth_tokens",),
    },
}

# ── Session store ──────────────────────────────────────────────────────────────
# cache backend (Redis): session lives only in Redis.
# NOTE: cached_db is NOT used here because django-tenants switches the DB
# connection to the tenant schema before session save in middleware unwind,
# and django_session only exists in the public schema — writing to a tenant
# schema causes a 500 on every authenticated request.
# Without Redis, Django falls back to database-backed sessions automatically.
if _REDIS_URL:
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

# Keep customers logged in for 90 days unless they explicitly sign out.
# Use `or` so an empty/unset env var falls back to the default safely.
# OPS-5c item 5: Declare TRUSTED_PROXY_COUNT explicitly so it appears in
# Django's settings rather than being silently defaulted in two separate places
# (config/middleware.py and sales/audit.py both read it via getattr default 1).
#
# Coolify topology: Traefik (edge load-balancer) → nginx (app proxy) → Django.
# That is 2 proxy hops, BUT Traefik rewrites X-Forwarded-For itself and
# presents only the real client IP to nginx, so nginx sees 1 hop.  Set this
# to 1 for the single nginx proxy in front of Django; bump to 2 if/when you add
# a second trusted proxy tier (e.g. a CDN that keeps the original XFF chain).
TRUSTED_PROXY_COUNT = parse_int_env("TRUSTED_PROXY_COUNT", 1)

# OPS-5c item 6: Sliding session window — reset the 90-day cookie on every
# request so active staff/customers are never logged out mid-shift.  The cost
# is one Redis SETEX per authenticated request (negligible at current volume).
# Works because SESSION_ENGINE = "django.contrib.sessions.backends.cache" uses
# Redis — a per-request DB write would be heavy but Redis is fast.
SESSION_SAVE_EVERY_REQUEST = True

SESSION_COOKIE_AGE = parse_int_env("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 24 * 90)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

AUTH_USER_MODEL = "accounts.User"

# Defines the REST_FRAMEWORK Django setting (consumed by DRF, not by Python code in
# this module) — so it reads as "unused" to a linter but removing it reverts DRF to
# defaults and breaks auth/permissions/throttling. Keep the noqa.
from .rest_framework import REST_FRAMEWORK  # noqa: F401, E402

cors_origins = set(
    parse_csv_env(
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://demo.localhost:5173",
    )
)
cors_origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
CORS_ALLOWED_ORIGINS = sorted(cors_origins)
# OPS-5d A: the in-code default localhost regex must NOT stay active in
# production.  parse_csv_env falls back to the default whenever the env var is
# unset/blank, and Coolify passes unset vars as "" — so a blank
# DJANGO_CORS_ALLOWED_ORIGIN_REGEXES would otherwise grant credentialed
# cross-origin access to ANY *.localhost:5173 origin in prod.  Gate the default
# behind DEBUG: dev (DEBUG=True) keeps the convenient *.localhost regex, while
# prod (DEBUG=False) with a blank env var yields an EMPTY regex list.  An
# explicit env value is always honoured in either mode.
_cors_regex_default = r"^http://[a-z0-9-]+\.localhost:5173$" if DEBUG else ""
cors_origin_regexes = set(
    parse_csv_env(
        "DJANGO_CORS_ALLOWED_ORIGIN_REGEXES",
        _cors_regex_default,
    )
)
CORS_ALLOWED_ORIGIN_REGEXES = sorted(cors_origin_regexes)
CORS_ALLOW_CREDENTIALS = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

# OPS-5d B: serving /media through django.views.static.serve in production is a
# liability (no security headers, holds an fd, historically traversal-risky) and
# is redundant — nginx (frontend/nginx.conf) already serves /media end to end.
# In DEBUG (dev) we always serve media via Django for convenience.  In prod the
# route is only registered if an operator explicitly opts in via this flag
# (defaults False), so a normal prod deploy never registers it.
SERVE_MEDIA_FROM_DJANGO = parse_bool_env("SERVE_MEDIA_FROM_DJANGO", False)

# Peer-to-peer wallet gifting (one customer sends wallet credit to another, on-platform
# only — no cash-out). OFF by default: this is regulated money transmission in most
# markets and must not go live without a license + KYC/AML controls. The transfer
# engine and endpoint exist but stay inert until this flag is explicitly enabled.
WALLET_P2P_ENABLED = parse_bool_env("WALLET_P2P_ENABLED", False)
# Default dial code (digits only, e.g. "212" for Morocco) used to normalize local
# recipient numbers like "0612…" into E.164 "+212612…" for P2P transfers. Empty means
# strict mode: senders must type the full international "+…" number (no guessing).
WALLET_DEFAULT_DIAL_CODE = os.getenv("WALLET_DEFAULT_DIAL_CODE", "").strip()
# Wallet charges at or below this amount debit instantly when the owner/staff scans the
# customer's QR pay-code (the scan is consent for a small tap). Charges ABOVE it become a
# pending request the customer must approve in their app before any money moves. Set to 0
# to require approval for every charge. In the platform's base currency (MAD).
WALLET_CHARGE_APPROVAL_THRESHOLD = os.getenv("WALLET_CHARGE_APPROVAL_THRESHOLD", "50").strip() or "50"
# How long a pending charge request stays approvable before it auto-expires (seconds).
WALLET_CHARGE_REQUEST_TTL = parse_int_env("WALLET_CHARGE_REQUEST_TTL", 300)
PUBLIC_MENU_BASE_URL = os.getenv("PUBLIC_MENU_BASE_URL", "").strip()
TENANT_DOMAIN_SUFFIX = hostname_from_url(os.getenv("TENANT_DOMAIN_SUFFIX", "")) or hostname_from_url(PUBLIC_MENU_BASE_URL)
if TENANT_DOMAIN_SUFFIX:
    csrf_trusted_origins.add(f"https://{TENANT_DOMAIN_SUFFIX}")
    csrf_trusted_origins.add(f"https://*.{TENANT_DOMAIN_SUFFIX}")
    CSRF_TRUSTED_ORIGINS = sorted(csrf_trusted_origins)
public_schema_hosts = set(parse_csv_env("DJANGO_PUBLIC_SCHEMA_HOSTS", "localhost,127.0.0.1"))
public_schema_hosts.update({"localhost", "127.0.0.1"})
for inferred_host in (
    hostname_from_url(PUBLIC_MENU_BASE_URL),
    hostname_from_url(os.getenv("SERVICE_FQDN_FRONTEND", "")),
    hostname_from_url(os.getenv("SERVICE_FQDN_ADMIN", "")),
):
    if inferred_host:
        public_schema_hosts.add(inferred_host)
PUBLIC_SCHEMA_HOSTS = sorted(public_schema_hosts)
RESERVATION_SLA_NEW_MINUTES = parse_int_env("RESERVATION_SLA_NEW_MINUTES", 30)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-12b-it:free").strip()
RESERVATION_SLA_DUE_SOON_MINUTES = parse_int_env("RESERVATION_SLA_DUE_SOON_MINUTES", 10)
# Google OAuth client ID for customer Google One-Tap auth.
# Set GOOGLE_OAUTH_CLIENT_ID in your .env to enable Google sign-in.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()

# ── R7b: TOTP MFA ─────────────────────────────────────────────────────────────
# PLATFORM_NAME is used as the issuer in the TOTP provisioning URI (shows in
# authenticator apps next to the account).
PLATFORM_NAME = os.getenv("PLATFORM_NAME", "Kepoli").strip() or "Kepoli"
# MFA_REQUIRED_ROLES: CSV of role strings for which MFA is MANDATORY at login,
# regardless of whether the user has enrolled a device.
# Example:  DJANGO_MFA_REQUIRED_ROLES=platform_superadmin,tenant_owner
# Default EMPTY → purely opt-in: MFA is only triggered for users who have an
# already-confirmed TOTP device. With the flag empty AND no enrolled device,
# LoginView behaves byte-for-byte as before this feature landed (no MFA gate).
MFA_REQUIRED_ROLES: list[str] = parse_csv_env("DJANGO_MFA_REQUIRED_ROLES", "")

# ── Web Push (VAPID) ──────────────────────────────────────────────────────────
# Generate a key pair once with:  python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print('PRIVATE:', v.private_pem().decode()); print('PUBLIC:', v.public_key.public_bytes_raw().hex())"
# Or use:  vapid --gen  (installs with pywebpush)
# Store in Coolify env as VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY (PEM / URL-safe base64 respectively).
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").strip().replace("\\n", "\n")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
VAPID_ADMIN_EMAIL = os.getenv("VAPID_ADMIN_EMAIL", "admin@example.com").strip()

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
if USE_S3_MEDIA_STORAGE:
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "").strip()
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "").strip() or None
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip()
    AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "auto").strip().lower() or "auto"
    AWS_QUERYSTRING_AUTH = parse_bool_env("AWS_QUERYSTRING_AUTH", False)
    AWS_QUERYSTRING_EXPIRE = parse_int_env("AWS_QUERYSTRING_EXPIRE", 900)
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = os.getenv("AWS_S3_SIGNATURE_VERSION", "").strip() or None
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": os.getenv("AWS_S3_OBJECT_CACHE_CONTROL", "public, max-age=31536000"),
    }
    AWS_MEDIA_LOCATION = os.getenv("AWS_MEDIA_LOCATION", "media").strip().strip("/") or "media"

    missing_s3 = []
    for env_name, env_value in (
        ("AWS_STORAGE_BUCKET_NAME", AWS_STORAGE_BUCKET_NAME),
        ("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID),
        ("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY),
    ):
        if not env_value:
            missing_s3.append(env_name)
    if missing_s3:
        raise RuntimeError(
            "DJANGO_MEDIA_STORAGE_BACKEND=s3 but required variables are missing: "
            + ", ".join(missing_s3)
        )
    if AWS_QUERYSTRING_EXPIRE <= 0:
        raise RuntimeError("AWS_QUERYSTRING_EXPIRE must be a positive integer.")

    s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "location": AWS_MEDIA_LOCATION,
        "default_acl": AWS_DEFAULT_ACL,
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "querystring_expire": AWS_QUERYSTRING_EXPIRE,
        "file_overwrite": AWS_S3_FILE_OVERWRITE,
        "object_parameters": AWS_S3_OBJECT_PARAMETERS,
    }
    if AWS_ACCESS_KEY_ID:
        s3_options["access_key"] = AWS_ACCESS_KEY_ID
    if AWS_SECRET_ACCESS_KEY:
        s3_options["secret_key"] = AWS_SECRET_ACCESS_KEY
    if AWS_S3_REGION_NAME:
        s3_options["region_name"] = AWS_S3_REGION_NAME
    if AWS_S3_ENDPOINT_URL:
        s3_options["endpoint_url"] = AWS_S3_ENDPOINT_URL
    if AWS_S3_ADDRESSING_STYLE and AWS_S3_ADDRESSING_STYLE != "auto":
        s3_options["addressing_style"] = AWS_S3_ADDRESSING_STYLE
    if AWS_S3_SIGNATURE_VERSION:
        s3_options["signature_version"] = AWS_S3_SIGNATURE_VERSION
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": s3_options,
    }

    media_location_prefix = f"{AWS_MEDIA_LOCATION}/" if AWS_MEDIA_LOCATION else ""
    if AWS_S3_CUSTOM_DOMAIN:
        custom_domain = AWS_S3_CUSTOM_DOMAIN.strip().rstrip("/")
        if custom_domain.startswith(("http://", "https://")):
            MEDIA_URL = f"{custom_domain}/{media_location_prefix}"
        else:
            MEDIA_URL = f"https://{custom_domain}/{media_location_prefix}"
    elif AWS_S3_ENDPOINT_URL:
        endpoint = AWS_S3_ENDPOINT_URL.rstrip("/")
        MEDIA_URL = f"{endpoint}/{AWS_STORAGE_BUCKET_NAME}/{media_location_prefix}"
    else:
        if AWS_S3_REGION_NAME:
            MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{media_location_prefix}"
        else:
            MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{media_location_prefix}"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "Kepoli <noreply@kepoli.app>")
SERVER_EMAIL = os.getenv("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# OPS-5f: server-authoritative canonical host for tenant-less links (e.g. the
# password-reset link for an owner with no tenant). Used by build_frontend_base_url
# INSTEAD of the spoofable request Host header. Falls back to PUBLIC_MENU_BASE_URL /
# TENANT_DOMAIN_SUFFIX when unset; set this in production to the real frontend host.
BRAND_DOMAIN = hostname_from_url(os.getenv("DJANGO_BRAND_DOMAIN", "")) or os.getenv("DJANGO_BRAND_DOMAIN", "").strip()
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = parse_int_env("DJANGO_EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = parse_bool_env("DJANGO_EMAIL_USE_TLS", False)
EMAIL_USE_SSL = parse_bool_env("DJANGO_EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = parse_int_env("DJANGO_EMAIL_TIMEOUT", 10)
EMAIL_FAIL_SILENTLY = parse_bool_env("DJANGO_EMAIL_FAIL_SILENTLY", DEBUG)

# ── Twilio — OTP SMS delivery ──────────────────────────────────────────────────
# Set these in Coolify after getting your credentials from console.twilio.com
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")  # E.164, e.g. +12015551234

SESSION_COOKIE_SECURE = parse_bool_env("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = parse_bool_env("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = parse_bool_env("DJANGO_SESSION_COOKIE_HTTPONLY", True)
# CSRF_COOKIE_HTTPONLY MUST stay False: the SPA uses Django's double-submit defence —
# it reads the `csrftoken` cookie via JS (frontend/src/lib/api.js, adminApi.js) and echoes
# it in the X-CSRFToken header on unsafe requests. Setting this True would hide the cookie
# from JS and 403 every POST/PATCH/DELETE. The header echo is itself the CSRF protection,
# so a JS-readable cookie is the intended design here — do not "harden" this to True.
CSRF_COOKIE_HTTPONLY = parse_bool_env("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
def normalize_cookie_domain(value: str | None):
    raw = (value or "").strip()
    if not raw:
        return None
    if raw in {"localhost", "127.0.0.1"}:
        return raw
    if raw.startswith("."):
        return raw
    return f".{raw}"


SESSION_COOKIE_DOMAIN = normalize_cookie_domain(os.getenv("DJANGO_SESSION_COOKIE_DOMAIN"))
CSRF_COOKIE_DOMAIN = normalize_cookie_domain(os.getenv("DJANGO_CSRF_COOKIE_DOMAIN"))
if TENANT_DOMAIN_SUFFIX:
    if not SESSION_COOKIE_DOMAIN:
        SESSION_COOKIE_DOMAIN = f".{TENANT_DOMAIN_SUFFIX}"
    if not CSRF_COOKIE_DOMAIN:
        CSRF_COOKIE_DOMAIN = f".{TENANT_DOMAIN_SUFFIX}"
USE_X_FORWARDED_HOST = parse_bool_env("DJANGO_USE_X_FORWARDED_HOST", not DEBUG)
if parse_bool_env("DJANGO_SECURE_PROXY_SSL_HEADER", not DEBUG):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── HTTPS / SecurityMiddleware hardening ──────────────────────────────────────
# X-Content-Type-Options: nosniff — prevents MIME-type sniffing attacks.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Redirect plain HTTP → HTTPS in production.  Disabled in dev so the Vite dev
# server (http://localhost) keeps working.
SECURE_SSL_REDIRECT = parse_bool_env("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)

# Never redirect the container health-check endpoint.  The Docker/Coolify
# health check hits http://127.0.0.1:8000/api/health/ directly (plain HTTP,
# no X-Forwarded-Proto header), so with SECURE_SSL_REDIRECT=True it would be
# 301'd to https:// — which has no listener on that internal port — making the
# check fail and the container report "unhealthy".  SecurityMiddleware strips
# the leading slash before matching, so the pattern has none.
SECURE_REDIRECT_EXEMPT = [r"^api/health/?$"]

# HSTS: tell browsers to only ever use HTTPS for this domain.
# Start with 1 hour in staging, bump to 1 year (31536000) once confident.
SECURE_HSTS_SECONDS = parse_int_env("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = parse_bool_env("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = parse_bool_env("DJANGO_SECURE_HSTS_PRELOAD", False)

# X-Frame-Options: DENY prevents clickjacking (XFrameOptionsMiddleware uses this).
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")

# Referrer-Policy: send origin only on same-origin requests to avoid leaking
# URLs with tokens in query strings to third-party analytics.
# Validate the env value (a single policy OR a comma-separated list) against the
# set Django's security.E023 check accepts. An invalid value would otherwise make
# `manage.py check --deploy --fail-level ERROR` (the entrypoint deploy gate) fail
# and crash-loop the whole deploy — so a bad/typo'd env var falls back to the safe
# default with a warning instead of taking the app down.
_VALID_REFERRER_POLICIES = {
    "no-referrer", "no-referrer-when-downgrade", "origin",
    "origin-when-cross-origin", "same-origin", "strict-origin",
    "strict-origin-when-cross-origin", "unsafe-url",
}
_referrer_raw = os.getenv("DJANGO_REFERRER_POLICY", "strict-origin-when-cross-origin").strip()
_referrer_tokens = [t.strip() for t in _referrer_raw.split(",") if t.strip()]
if _referrer_tokens and all(t in _VALID_REFERRER_POLICIES for t in _referrer_tokens):
    SECURE_REFERRER_POLICY = ",".join(_referrer_tokens)
else:
    import warnings as _referrer_warn
    _referrer_warn.warn(
        f"DJANGO_REFERRER_POLICY={_referrer_raw!r} is not a valid Referrer-Policy "
        "(security.E023); falling back to 'strict-origin-when-cross-origin'. Valid "
        "values: " + ", ".join(sorted(_VALID_REFERRER_POLICIES)),
        stacklevel=2,
    )
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ── Django admin URL ──────────────────────────────────────────────────────────
# Change DJANGO_ADMIN_URL in production to an unguessable path (no trailing slash
# needed — Django's path() adds it). Example: "internal-management-abc123/"
# Keep it ending in "/" so Django resolves it correctly.
ADMIN_URL_PREFIX = os.getenv("DJANGO_ADMIN_URL", "admin/")

SECURITY_LOG_LEVEL = os.getenv("DJANGO_SECURITY_LOG_LEVEL", "WARNING")
SECURITY_LOG_FILE = os.getenv("DJANGO_SECURITY_LOG_FILE", "")
LOG_FORMAT = os.getenv("DJANGO_LOG_FORMAT", "text").strip().lower()
REQUEST_LOG_LEVEL = os.getenv("DJANGO_REQUEST_LOG_LEVEL", "INFO").strip().upper()
PROVISIONING_LOG_LEVEL = os.getenv("DJANGO_PROVISIONING_LOG_LEVEL", "INFO").strip().upper()
EMAIL_LOG_LEVEL = os.getenv("DJANGO_EMAIL_LOG_LEVEL", "INFO").strip().upper()
# R15: dedicated channel for money-mutation failures (wallet/charge/commission/
# cash-out/float). Kept at INFO so error/warning money events always emit; it is a
# named logger so a failure can be alerted on as its own rate, separate from the
# general ERROR firehose. It still reaches Sentry (sentry-sdk's LoggingIntegration
# captures via logging.Logger.callHandlers, which fires regardless of propagate).
PAYMENT_LOG_LEVEL = os.getenv("DJANGO_PAYMENT_LOG_LEVEL", "INFO").strip().upper()

# ── PSP top-up seam (Stripe Checkout, dormant until PSP_TOPUP_ENABLED=1) ─────
# Set PSP_TOPUP_ENABLED=1 + PSP_STRIPE_SECRET_KEY + PSP_STRIPE_WEBHOOK_SECRET in
# production env to activate. PSP_SITE_URL sets the Stripe redirect base URL
# (success/cancel); falls back to PUBLIC_MENU_BASE_URL.
PSP_TOPUP_ENABLED = os.getenv("PSP_TOPUP_ENABLED", "").strip().lower() in ("1", "true", "yes")
PSP_STRIPE_SECRET_KEY = os.getenv("PSP_STRIPE_SECRET_KEY", "")
PSP_STRIPE_WEBHOOK_SECRET = os.getenv("PSP_STRIPE_WEBHOOK_SECRET", "")
PSP_SITE_URL = os.getenv("PSP_SITE_URL", PUBLIC_MENU_BASE_URL).rstrip("/")

# ── Email suppression webhook (bounce / spam-complaint ingest) ─────────────
# Set EMAIL_SUPPRESSION_WEBHOOK_SECRET to a random shared secret and configure
# your ESP's bounce/complaint webhook to POST to /api/public/email/suppression/
# with `Authorization: Bearer <secret>`. Without a secret the endpoint is disabled.
EMAIL_SUPPRESSION_WEBHOOK_SECRET = os.getenv("EMAIL_SUPPRESSION_WEBHOOK_SECRET", "")

# ── Platform verticals gate ───────────────────────────────────────────────────
# CSV of enabled platform verticals. "rides" is excluded from the default
# because it requires a separate licensed-car-driver supply and carries live
# security obligations while not operationally active. Set
# DJANGO_VERTICALS_ENABLED=food,shops,pharmacy,courier,driver,rides in env
# to re-enable the rides vertical.
_verticals_raw = os.getenv("DJANGO_VERTICALS_ENABLED", "food,shops,pharmacy,courier,driver")
VERTICALS_ENABLED: frozenset = frozenset(
    v.strip().lower() for v in _verticals_raw.split(",") if v.strip()
)

ACTIVE_LOG_FORMATTER = "json" if LOG_FORMAT == "json" else "standard"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "json": {
            "()": "config.logging_utils.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": ACTIVE_LOG_FORMATTER,
        },
    },
    "loggers": {
        "security.throttle": {
            "handlers": ["console"],
            "level": SECURITY_LOG_LEVEL,
            "propagate": False,
        },
        "app.request": {
            "handlers": ["console"],
            "level": REQUEST_LOG_LEVEL,
            "propagate": False,
        },
        "sales.provisioning": {
            "handlers": ["console"],
            "level": PROVISIONING_LOG_LEVEL,
            "propagate": False,
        },
        "app.email": {
            "handlers": ["console"],
            "level": EMAIL_LOG_LEVEL,
            "propagate": False,
        },
        # R15: money-failure channel (wallet/charge/commission/cash-out/float).
        # propagate=False mirrors the other named loggers; Sentry capture is via the
        # SDK's callHandlers patch, not log propagation, so events still reach Sentry.
        "payments": {
            "handlers": ["console"],
            "level": PAYMENT_LOG_LEVEL,
            "propagate": False,
        },
    },
}

# NOTE (R13 non-root): the container runs as UID 10001, so if DJANGO_SECURITY_LOG_FILE
# is set its path MUST be writable by that UID (use a path under /tmp or a volume
# pre-chowned to 10001:10001). A root-owned target makes the first security-log write
# raise. Leave unset to log to stdout/stderr (the default, collected by the platform).
if SECURITY_LOG_FILE:
    LOGGING["handlers"]["security_file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": SECURITY_LOG_FILE,
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "formatter": ACTIVE_LOG_FORMATTER,
    }
    LOGGING["loggers"]["security.throttle"]["handlers"].append("security_file")
    LOGGING["loggers"]["app.request"]["handlers"].append("security_file")
    LOGGING["loggers"]["sales.provisioning"]["handlers"].append("security_file")
    LOGGING["loggers"]["app.email"]["handlers"].append("security_file")
    LOGGING["loggers"]["payments"]["handlers"].append("security_file")

# ── Sentry error tracking ──────────────────────────────────────────────────────
# Activated when DJANGO_SENTRY_DSN is set in the environment.
# Safe to call unconditionally — init_sentry() is a no-op when DSN is absent.
from config.sentry import init_sentry as _init_sentry  # noqa: E402
_init_sentry()
