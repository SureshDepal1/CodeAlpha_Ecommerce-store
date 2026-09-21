import logging
import socket
import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


logger = logging.getLogger(__name__)


def _clean_subject_value(value):
    return " ".join(str(value).splitlines())


def _recipient_domain(address):
    return address.rsplit("@", 1)[-1] if "@" in address else "unknown"


def _warn_if_console_backend():
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        logger.warning("Email backend is console: emails are printed here and NOT delivered; configure .env")


def _failure_hint(error):
    if isinstance(error, smtplib.SMTPAuthenticationError) or getattr(error, "smtp_code", None) == 535:
        return "Authentication failed (535): use a Gmail App Password with 2-Step Verification."
    if isinstance(error, (TimeoutError, socket.timeout, smtplib.SMTPConnectError, ConnectionError, OSError)):
        return "Connection failed or timed out: port 587 may be blocked, try EMAIL_PORT=465 with EMAIL_USE_SSL=True."
    return f"Email could not be sent: {error}"


def _log_send_failure(label, error):
    logger.warning("Could not send %s email: %s", label, _failure_hint(error))
    logger.exception("Email send failure traceback (%s)", label)


def _email_context(order):
    return {
        "order": order,
        "items": order.items.all(),
        "order_url": f"{settings.SITE_URL}{reverse('store:order_detail', args=[order.pk])}",
        "admin_order_url": f"{settings.SITE_URL}{reverse('admin:store_order_change', args=[order.pk])}",
    }


def send_customer_confirmation(order):
    _warn_if_console_backend()
    context = _email_context(order)
    subject = f"Your DepalNova order #{_clean_subject_value(order.pk)} has been placed"
    text_body = render_to_string("emails/order_confirmation.txt", context)
    html_body = render_to_string("emails/order_confirmation.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    logger.info("Sent customer confirmation email to %s", _recipient_domain(order.email))


def send_owner_alert(order):
    recipients = getattr(settings, "ORDER_NOTIFICATION_EMAILS", [])
    if not recipients:
        logger.warning("Owner alert skipped: ORDER_NOTIFICATION_EMAILS is empty")
        return

    _warn_if_console_backend()
    context = _email_context(order)
    subject = (
        f"New order #{_clean_subject_value(order.pk)} - "
        f"${_clean_subject_value(order.total_amount)} from "
        f"{_clean_subject_value(order.full_name)}"
    )
    text_body = render_to_string("emails/order_owner_alert.txt", context)
    html_body = render_to_string("emails/order_owner_alert.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    domains = ", ".join(sorted({_recipient_domain(recipient) for recipient in recipients}))
    logger.info("Sent owner alert email to recipient domain(s): %s", domains)


def send_order_emails(order):
    try:
        send_customer_confirmation(order)
    except Exception as error:
        _log_send_failure("customer confirmation", error)

    try:
        send_owner_alert(order)
    except Exception as error:
        _log_send_failure("owner alert", error)


def send_verification_code(user, code):
    _warn_if_console_backend()
    context = {"code": code, "expiry_minutes": max(1, settings.OTP_EXPIRY_SECONDS // 60)}
    subject = f"{_clean_subject_value(code)} is your DepalNova verification code"
    text_body = render_to_string("emails/verification_code.txt", context)
    html_body = render_to_string("emails/verification_code.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as error:
        _log_send_failure("verification", error)
        raise
    logger.info("Sent verification email to %s", _recipient_domain(user.email))