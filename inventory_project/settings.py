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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Serves static files (admin CSS/JS) directly from the WSGI process via
# whitenoise, so the app is self-contained under waitress with no separate
# static-file server needed. Run `python manage.py collectstatic` once
# after each deploy/update -- see README.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
