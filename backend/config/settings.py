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


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
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
RESERVATION_SLA_DUE_SOON_MINUTES = int(os.getenv("RESERVATION_SLA_DUE_SOON_MINUTES", "10"))

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
    AWS_QUERYSTRING_AUTH = parse_bool_env("AWS_QUERYSTRING_AUTH", True)
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

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "location": AWS_MEDIA_LOCATION,
            "default_acl": AWS_DEFAULT_ACL,
            "querystring_auth": AWS_QUERYSTRING_AUTH,
            "querystring_expire": AWS_QUERYSTRING_EXPIRE,
            "file_overwrite": AWS_S3_FILE_OVERWRITE,
            "object_parameters": AWS_S3_OBJECT_PARAMETERS,
        },
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
