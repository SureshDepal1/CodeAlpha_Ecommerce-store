from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register


PLACEHOLDERS = {
    "paste_app_password_here",
    "your-email@gmail.com",
    "owner@example.com",
    "your-store@gmail.com",
}


@register("deploy")
def deployment_checks(app_configs, **kwargs):
    if settings.DEBUG:
        return []

    errors = []
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend" or any(
        not value or value.strip().lower() in PLACEHOLDERS
        for value in (settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    ):
        errors.append(
            Error(
                "Production email is not configured for delivery.",
                hint="Set real EMAIL_HOST_USER and EMAIL_HOST_PASSWORD values; OTP and order emails must use SMTP.",
                id="store.E001",
            )
        )

    parsed_site_url = urlparse(settings.SITE_URL)
    if parsed_site_url.hostname in {"localhost", "127.0.0.1", "::1"} or parsed_site_url.scheme != "https":
        errors.append(
            Warning(
                "SITE_URL is not a production HTTPS URL.",
                hint="Set SITE_URL to the public https:// URL used in customer and admin email links.",
                id="store.W001",
            )
        )

    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if not settings.ALLOWED_HOSTS or set(settings.ALLOWED_HOSTS).issubset(local_hosts):
        errors.append(
            Warning(
                "ALLOWED_HOSTS contains no public production host.",
                hint="Set DJANGO_ALLOWED_HOSTS to the deployed hostname(s), without a scheme or path.",
                id="store.W002",
            )
        )

    if not settings.STATIC_ROOT or not settings.STATIC_ROOT.exists() or not any(settings.STATIC_ROOT.iterdir()):
        errors.append(
            Warning(
                "STATIC_ROOT is missing or empty.",
                hint="Run python manage.py collectstatic --noinput during deployment.",
                id="store.W003",
            )
        )
    return errors