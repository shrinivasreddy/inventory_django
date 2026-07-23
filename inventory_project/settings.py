"""
Django settings for the Inventory Web project.

Every value that shouldn't be hardcoded (secret key, debug mode, allowed
hosts) is read from the environment / a .env file -- see .env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is not set. Add it to your .env file "
        "(any long random string works, e.g. generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\")"
    )

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in ("1", "true", "yes")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


# Comma-separated in .env, e.g. DJANGO_ALLOWED_HOSTS=inventory.mycompany.com,10.0.0.5
_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "inventory",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "inventory.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "inventory.middleware.SessionExpiryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "inventory_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "inventory.context_processors.admin_inventory_records",
            ],
        },
    },
]

WSGI_APPLICATION = "inventory_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        # A longer busy-timeout means concurrent writes wait for each other
        # instead of immediately failing with "database is locked" -- our
        # per-tab locks already serialize writes within this process, but
        # this is cheap extra insurance at a 50-user scale.
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Uploaded inventory images are application data and are served through an
# authenticated view, not by WhiteNoise.
_inventory_upload_root = Path(os.environ.get("DJANGO_INVENTORY_UPLOAD_ROOT", "uploads"))
INVENTORY_UPLOAD_ROOT = (
    _inventory_upload_root
    if _inventory_upload_root.is_absolute()
    else BASE_DIR / _inventory_upload_root
)
_configured_image_limit = int(
    os.environ.get("DJANGO_MAX_INVENTORY_IMAGE_BYTES", str(20 * 1024 * 1024))
)
# Twenty MB is the product requirement and therefore the minimum effective
# value. This also neutralizes stale Windows service environment overrides
# that still contain the former 10 MB value.
MAX_INVENTORY_IMAGE_BYTES = max(20 * 1024 * 1024, _configured_image_limit)
MAX_INVENTORY_IMAGE_PIXELS = int(os.environ.get("DJANGO_MAX_INVENTORY_IMAGE_PIXELS", "25000000"))
# Serves static files (admin CSS/JS) directly from the WSGI process via
# whitenoise, so the app is self-contained under waitress with no separate
# static-file server needed. Run `python manage.py collectstatic` once
# after each deploy/update -- see README.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MANIFEST_STRICT = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Explicit request/workbook limits protect the single-process service from
# oversized bodies and highly compressed XLSX archive bombs.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_MAX_REQUEST_BYTES", 25 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_MAX_FILE_MEMORY_BYTES", 5 * 1024 * 1024))
MAX_XLSX_UPLOAD_BYTES = int(
    os.environ.get("DJANGO_MAX_XLSX_UPLOAD_BYTES", 20 * 1024 * 1024)
)
MAX_XLSX_UNCOMPRESSED_BYTES = int(
    os.environ.get("DJANGO_MAX_XLSX_UNCOMPRESSED_BYTES", 100 * 1024 * 1024)
)
MAX_XLSX_ARCHIVE_ENTRIES = int(
    os.environ.get("DJANGO_MAX_XLSX_ARCHIVE_ENTRIES", 10_000)
)

# Use one consistent presentation format throughout Django-rendered pages.
# Database values remain proper date/datetime types.
DATE_FORMAT = "m-d-Y"
DATETIME_FORMAT = "m-d-Y"
SHORT_DATE_FORMAT = "m-d-Y"
SHORT_DATETIME_FORMAT = "m-d-Y"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Sessions expire after eight hours without activity and when the browser is
# closed. The custom middleware also rejects legacy sessions created under
# Django's former two-week default.
SESSION_COOKIE_AGE = int(os.environ.get("DJANGO_SESSION_COOKIE_AGE", str(8 * 60 * 60)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", True)
SESSION_SAVE_EVERY_REQUEST = True

# Password-reset email delivery. The console backend is safe for local
# development: it prints the reset link in the server terminal. Set
# DJANGO_EMAIL_BACKEND to SMTP and provide the SMTP variables in production.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "Inventory Web <no-reply@localhost>",
)
EMAIL_TIMEOUT = int(os.environ.get("DJANGO_EMAIL_TIMEOUT", "10"))
APP_BASE_URL = os.environ.get("DJANGO_APP_BASE_URL", "http://localhost:8000")

# Prompt-to-inventory assistant. The API key is server-side only and is never
# exposed in HTML or JavaScript.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_ASSISTANT_MODEL = os.environ.get("OPENAI_ASSISTANT_MODEL", "gpt-5.6-luna")
OPENAI_TRANSCRIPTION_MODEL = os.environ.get(
    "OPENAI_TRANSCRIPTION_MODEL",
    "gpt-4o-mini-transcribe",
)
OPENAI_ASSISTANT_TIMEOUT = int(os.environ.get("OPENAI_ASSISTANT_TIMEOUT", "30"))

# Admin URL path is configurable so it can be changed from the well-known
# default ("admin/") if you want to reduce automated-scanner noise.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin/")

# Only needed if Django's CSRF checks ever see a mismatched Origin header --
# e.g. if the app is reverse-proxied under HTTPS at a specific domain.
# Comma-separated, must include scheme, e.g. https://inventory.mycompany.com
_csrf_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]

# Safe to set regardless of HTTP/HTTPS -- unlike SECURE_SSL_REDIRECT etc.
# (left to the reverse proxy, see README), these don't require HTTPS to be
# already in place.
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# HTTPS settings are opt-in so local HTTP deployments keep working. Enable
# all of them when TLS terminates at Django or a trusted reverse proxy.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD")
if env_bool("DJANGO_TRUST_PROXY_SSL_HEADER"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CONTENT_TYPE_NOSNIFF = True
REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Basic production logging: warnings and above go to console (captured by
# the Windows Service / systemd logs already configured in deploy/), errors
# also get written to a rotating file so they survive a service restart.
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "django_errors.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "WARNING",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
    },
}
