import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


logger = logging.getLogger(__name__)


def _clean_subject_value(value):
    return " ".join(str(value).splitlines())


def _email_context(order):
    return {
        "order": order,
        "items": order.items.all(),
        "order_url": f"{settings.SITE_URL}{reverse('store:order_detail', args=[order.pk])}",
        "admin_order_url": f"{settings.SITE_URL}{reverse('admin:store_order_change', args=[order.pk])}",
    }


def send_customer_confirmation(order):
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


def send_owner_alert(order):
    recipients = getattr(settings, "ORDER_NOTIFICATION_EMAILS", [])
    if not recipients:
        return

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


def send_order_emails(order):
    try:
        send_customer_confirmation(order)
    except Exception:
        logger.exception("Could not send customer confirmation for order %s", order.pk)

    try:
        send_owner_alert(order)
    except Exception:
        logger.exception("Could not send owner alert for order %s", order.pk)