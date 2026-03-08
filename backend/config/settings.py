import os
from pathlib import Path

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

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
allowed_hosts = set(parse_csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost"))
# Keep local wildcard host support available for tenant subdomains in dev.
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
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://[a-z0-9-]+\.localhost:5173$",
]
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
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PUBLIC_MENU_BASE_URL = os.getenv("PUBLIC_MENU_BASE_URL", "").strip()
RESERVATION_SLA_NEW_MINUTES = int(os.getenv("RESERVATION_SLA_NEW_MINUTES", "30"))
RESERVATION_SLA_DUE_SOON_MINUTES = int(os.getenv("RESERVATION_SLA_DUE_SOON_MINUTES", "10"))

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

#
# Email delivery (use SMTP/API gateway in production).
#
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

#
# Session/cookie security. In production set secure cookies and proper domains.
#
SESSION_COOKIE_SECURE = parse_bool_env("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = parse_bool_env("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = parse_bool_env("DJANGO_SESSION_COOKIE_HTTPONLY", True)
CSRF_COOKIE_HTTPONLY = parse_bool_env("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_DOMAIN = os.getenv("DJANGO_SESSION_COOKIE_DOMAIN") or None
CSRF_COOKIE_DOMAIN = os.getenv("DJANGO_CSRF_COOKIE_DOMAIN") or None

#
# Security monitoring logs (throttle blocks and other security events).
#
SECURITY_LOG_LEVEL = os.getenv("DJANGO_SECURITY_LOG_LEVEL", "WARNING")
SECURITY_LOG_FILE = os.getenv("DJANGO_SECURITY_LOG_FILE", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "security.throttle": {
            "handlers": ["console"],
            "level": SECURITY_LOG_LEVEL,
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
        "formatter": "standard",
    }
    LOGGING["loggers"]["security.throttle"]["handlers"].append("security_file")
