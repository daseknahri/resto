import os
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def parse_csv_env(var_name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(var_name, default).split(",") if item.strip()]


def parse_bool_env(var_name: str, default: bool = False) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
allowed_hosts.update({"localhost", "127.0.0.1", ".localhost"})
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

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

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
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE") or 60 * 60 * 24 * 90)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

AUTH_USER_MODEL = "accounts.User"

from .rest_framework import REST_FRAMEWORK  # noqa: E402

cors_origins = set(
    parse_csv_env(
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://demo.localhost:5173",
    )
)
cors_origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
CORS_ALLOWED_ORIGINS = sorted(cors_origins)
cors_origin_regexes = set(
    parse_csv_env(
        "DJANGO_CORS_ALLOWED_ORIGIN_REGEXES",
        r"^http://[a-z0-9-]+\.localhost:5173$",
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
RESERVATION_SLA_NEW_MINUTES = int(os.getenv("RESERVATION_SLA_NEW_MINUTES", "30"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-12b-it:free").strip()
RESERVATION_SLA_DUE_SOON_MINUTES = int(os.getenv("RESERVATION_SLA_DUE_SOON_MINUTES", "10"))
# Google OAuth client ID for customer Google One-Tap auth.
# Set GOOGLE_OAUTH_CLIENT_ID in your .env to enable Google sign-in.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()

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
    AWS_QUERYSTRING_EXPIRE = int(os.getenv("AWS_QUERYSTRING_EXPIRE", "900"))
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
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "noreply@restomenu.local")
SERVER_EMAIL = os.getenv("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = parse_bool_env("DJANGO_EMAIL_USE_TLS", False)
EMAIL_USE_SSL = parse_bool_env("DJANGO_EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.getenv("DJANGO_EMAIL_TIMEOUT", "10"))
EMAIL_FAIL_SILENTLY = parse_bool_env("DJANGO_EMAIL_FAIL_SILENTLY", DEBUG)

# ── Twilio — OTP SMS delivery ──────────────────────────────────────────────────
# Set these in Coolify after getting your credentials from console.twilio.com
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")  # E.164, e.g. +12015551234

SESSION_COOKIE_SECURE = parse_bool_env("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = parse_bool_env("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = parse_bool_env("DJANGO_SESSION_COOKIE_HTTPONLY", True)
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

# HSTS: tell browsers to only ever use HTTPS for this domain.
# Start with 1 hour in staging, bump to 1 year (31536000) once confident.
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 3600))
SECURE_HSTS_INCLUDE_SUBDOMAINS = parse_bool_env("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = parse_bool_env("DJANGO_SECURE_HSTS_PRELOAD", False)

# X-Frame-Options: DENY prevents clickjacking (XFrameOptionsMiddleware uses this).
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")

# Referrer-Policy: send origin only on same-origin requests to avoid leaking
# URLs with tokens in query strings to third-party analytics.
SECURE_REFERRER_POLICY = os.getenv("DJANGO_REFERRER_POLICY", "strict-origin-when-cross-origin")

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
    },
}

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

# ── Sentry error tracking ──────────────────────────────────────────────────────
# Activated when DJANGO_SENTRY_DSN is set in the environment.
# Safe to call unconditionally — init_sentry() is a no-op when DSN is absent.
from config.sentry import init_sentry as _init_sentry  # noqa: E402
_init_sentry()
