"""Django settings for the Simple E-commerce Store project."""

import os
from urllib.parse import parse_qs, unquote, urlparse
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
DEVELOPMENT_SECRET_KEY = "development-only-key-change-in-production-use-an-environment-secret"


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


load_dotenv(os.environ.get("DJANGO_DOTENV_PATH", BASE_DIR / ".env"))


def _env_bool(name, default=False, environ=None):
    environ = os.environ if environ is None else environ
    return str(environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _is_placeholder(value):
    return value.strip().lower() in {
        "paste_app_password_here",
        "your-email@gmail.com",
        "owner@example.com",
        "your-store@gmail.com",
    }


def _env_int(name, default, environ=None):
    environ = os.environ if environ is None else environ
    try:
        return int(str(environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _normalize_password(value):
    return "".join(value.split())


def _email_transport(environ=None):
    environ = os.environ if environ is None else environ
    use_ssl = _env_bool("EMAIL_USE_SSL", False, environ)
    use_tls = _env_bool("EMAIL_USE_TLS", not use_ssl, environ)
    if use_ssl:
        use_tls = False
    port = _env_int("EMAIL_PORT", 465 if use_ssl else 587, environ)
    return use_ssl, use_tls, port


def email_settings(environ=None):
    environ = os.environ if environ is None else environ
    host_user = environ.get("EMAIL_HOST_USER", "").strip()
    host_password = _normalize_password(environ.get("EMAIL_HOST_PASSWORD", ""))
    use_ssl, use_tls, port = _email_transport(environ)
    configured = bool(host_user and host_password and not _is_placeholder(host_user) and not _is_placeholder(host_password))
    return {
        "EMAIL_HOST_USER": host_user,
        "EMAIL_HOST_PASSWORD": host_password,
        "EMAIL_USE_SSL": use_ssl,
        "EMAIL_USE_TLS": use_tls,
        "EMAIL_PORT": port,
        "EMAIL_HOST": environ.get("EMAIL_HOST", "smtp.gmail.com"),
        "EMAIL_CONFIGURED": configured,
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend" if configured else "django.core.mail.backends.console.EmailBackend",
    }


def resolve_secret_key(debug, environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
    if not debug and (not value or len(value) < 50 or value == DEVELOPMENT_SECRET_KEY or value.startswith("django-insecure-")):
        raise ImproperlyConfigured(
            'Production requires DJANGO_SECRET_KEY with at least 50 characters that is not a development key. '
            'Generate one with: python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"'
        )
    return value


def _csv_values(name, environ=None):
    environ = os.environ if environ is None else environ
    return [value.strip() for value in environ.get(name, "").split(",") if value.strip()]


def parse_proxy_settings(environ=None):
    return ("HTTP_X_FORWARDED_PROTO", "https") if _env_bool("DJANGO_BEHIND_PROXY", False, environ) else None


def parse_csrf_trusted_origins(environ=None):
    return _csv_values("DJANGO_CSRF_TRUSTED_ORIGINS", environ)


def parse_database_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ImproperlyConfigured("DATABASE_URL must use postgres:// or postgresql:// and include a hostname.")
    options = {}
    query = parse_qs(parsed.query)
    if query.get("sslmode"):
        options["sslmode"] = query["sslmode"][0]
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": str(parsed.port or "5432"),
        "CONN_MAX_AGE": 60,
    }
    if options:
        config["OPTIONS"] = options
    return config


DEBUG = _env_bool("DJANGO_DEBUG", True)
SECRET_KEY = resolve_secret_key(DEBUG)
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "store.context_processors.store_info",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATABASES = {"default": parse_database_url(DATABASE_URL)} if DATABASE_URL else {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
        "CONN_MAX_AGE": 60,
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
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_EMAIL_SETTINGS = email_settings()
EMAIL_HOST_USER = _EMAIL_SETTINGS["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = _EMAIL_SETTINGS["EMAIL_HOST_PASSWORD"]
EMAIL_USE_SSL = _EMAIL_SETTINGS["EMAIL_USE_SSL"]
EMAIL_USE_TLS = _EMAIL_SETTINGS["EMAIL_USE_TLS"]
EMAIL_PORT = _EMAIL_SETTINGS["EMAIL_PORT"]
EMAIL_HOST = _EMAIL_SETTINGS["EMAIL_HOST"]
EMAIL_CONFIGURED = _EMAIL_SETTINGS["EMAIL_CONFIGURED"]
if EMAIL_CONFIGURED:
    EMAIL_BACKEND = _EMAIL_SETTINGS["EMAIL_BACKEND"]
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
SERVE_MEDIA = _env_bool("SERVE_MEDIA", DEBUG)
STORE_NAME = os.environ.get("STORE_NAME", "DepalNova").strip() or "DepalNova"
STORE_CONTACT_EMAIL = os.environ.get("STORE_CONTACT_EMAIL", "").strip()
STORE_PHONE = os.environ.get("STORE_PHONE", "").strip()
STORE_ADDRESS = os.environ.get("STORE_ADDRESS", "").strip()
RETURN_POLICY_SUMMARY = os.environ.get("RETURN_POLICY_SUMMARY", "").strip()
DELIVERY_TIME_SUMMARY = os.environ.get("DELIVERY_TIME_SUMMARY", "").strip()
LEGAL_JURISDICTION = os.environ.get("LEGAL_JURISDICTION", "").strip()
LEGAL_LAST_UPDATED = os.environ.get("LEGAL_LAST_UPDATED", "2026-09-21").strip()

OTP_LENGTH = _env_int("OTP_LENGTH", 6)
OTP_EXPIRY_SECONDS = _env_int("OTP_EXPIRY_SECONDS", 600)
OTP_MAX_ATTEMPTS = _env_int("OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = _env_int("OTP_RESEND_COOLDOWN_SECONDS", 60)
OTP_MAX_SENDS = _env_int("OTP_MAX_SENDS", 5)
UNVERIFIED_ACCOUNT_LIFETIME_MINUTES = _env_int("UNVERIFIED_ACCOUNT_LIFETIME_MINUTES", 60)
OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR = _env_int("OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR", 3)
OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR = _env_int("OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR", 10)
PASSWORD_RESET_TIMEOUT = 3600
PASSWORD_RESET_EMAIL_LIMIT = 3
PASSWORD_RESET_IP_LIMIT = 5
LOGIN_MAX_FAILED_PER_USER_IP = _env_int("LOGIN_MAX_FAILED_PER_USER_IP", 5)
LOGIN_MAX_FAILED_PER_IP = _env_int("LOGIN_MAX_FAILED_PER_IP", 20)
LOGIN_LOCKOUT_SECONDS = _env_int("LOGIN_LOCKOUT_SECONDS", 900)

CACHE_BACKEND = os.environ.get("DJANGO_CACHE_BACKEND", "locmem").strip().lower()
if CACHE_BACKEND == "database":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "depalnova-cache"}}

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
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SSL_REDIRECT", not DEBUG)
SECURE_PROXY_SSL_HEADER = parse_proxy_settings()
CSRF_TRUSTED_ORIGINS = parse_csrf_trusted_origins()
SECURE_HSTS_SECONDS = 31536000 if SECURE_DEPLOYMENT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_DEPLOYMENT
SECURE_HSTS_PRELOAD = SECURE_DEPLOYMENT
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
