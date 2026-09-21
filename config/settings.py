"""Django settings for the Simple E-commerce Store project."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path):
    """Load simple KEY=VALUE pairs without replacing real environment values."""
    try:
        contents = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return

    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / ".env")


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _is_placeholder(value):
    return value.strip().lower() in {
        "paste_app_password_here",
        "your-email@gmail.com",
        "owner@example.com",
        "your-store@gmail.com",
    }


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _normalize_password(value):
    return "".join(value.split())


def _email_transport():
    use_ssl = _env_bool("EMAIL_USE_SSL", False)
    use_tls = _env_bool("EMAIL_USE_TLS", not use_ssl)
    if use_ssl:
        use_tls = False
    port = _env_int("EMAIL_PORT", 465 if use_ssl else 587)
    return use_ssl, use_tls, port


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "development-only-key-change-in-production-use-an-environment-secret",
)
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
SECURE_DEPLOYMENT = _env_bool("DJANGO_SECURE_DEPLOYMENT", not DEBUG)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "store.context_processors.cart_count",
                "store.context_processors.nav_categories",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = _normalize_password(os.environ.get("EMAIL_HOST_PASSWORD", ""))
EMAIL_USE_SSL, EMAIL_USE_TLS, EMAIL_PORT = _email_transport()
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_CONFIGURED = bool(
    EMAIL_HOST_USER
    and EMAIL_HOST_PASSWORD
    and not _is_placeholder(EMAIL_HOST_USER)
    and not _is_placeholder(EMAIL_HOST_PASSWORD)
)
if EMAIL_CONFIGURED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"DepalNova <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER.strip() else "DepalNova <no-reply@localhost>",
)
ORDER_NOTIFICATION_EMAILS = [
    email.strip()
    for email in os.environ.get("ORDER_NOTIFICATION_EMAILS", "").split(",")
    if email.strip()
]
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

OTP_LENGTH = _env_int("OTP_LENGTH", 6)
OTP_EXPIRY_SECONDS = _env_int("OTP_EXPIRY_SECONDS", 600)
OTP_MAX_ATTEMPTS = _env_int("OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = _env_int("OTP_RESEND_COOLDOWN_SECONDS", 60)
OTP_MAX_SENDS = _env_int("OTP_MAX_SENDS", 5)
UNVERIFIED_ACCOUNT_LIFETIME_MINUTES = _env_int("UNVERIFIED_ACCOUNT_LIFETIME_MINUTES", 60)
OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR = _env_int("OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR", 3)
OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR = _env_int("OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR", 10)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "email": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "email_console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "email",
        },
        "email_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "email.log"),
            "maxBytes": 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
            "level": "INFO",
            "formatter": "email",
        },
    },
    "loggers": {
        "store": {
            "handlers": ["email_console", "email_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if SECURE_DEPLOYMENT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_DEPLOYMENT
SECURE_HSTS_PRELOAD = SECURE_DEPLOYMENT
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
