from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, Product


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="DepalNova <no-reply@example.com>",
    ORDER_NOTIFICATION_EMAILS=["owner@example.com"],
    SITE_URL="https://shop.example.com",
)
class OrderEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="emailuser",
            password="StrongPassword123!",
            email="user@example.com",
        )
        self.product = Product.objects.create(
            name="Email Test Product",
            description="Email test product.",
            price="25.00",
            category="General",
            stock=5,
            is_available=True,
        )
        self.checkout_data = {
            "full_name": "Email Customer",
            "email": "customer@example.com",
            "phone": "03001234567",
            "address": "123 Test Street",
            "city": "Karachi",
            "state": "Sindh",
            "postal_code": "74000",
            "country": "Pakistan",
            "review_only": "1",
        }

    def post_checkout(self, quantity=1, data=None):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): quantity}
        session.save()
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("store:checkout"), data or self.checkout_data)

    def test_successful_order_sends_customer_and_owner_emails(self):
        response = self.post_checkout(quantity=2)

        self.assertRedirects(response, reverse("store:order_confirmation", args=[1]))
        self.assertEqual(len(mail.outbox), 2)
        customer_email = next(message for message in mail.outbox if message.to == ["customer@example.com"])
        owner_email = next(message for message in mail.outbox if message.to == ["owner@example.com"])
        self.assertIn("order #1", customer_email.subject)
        self.assertIn("Email Test Product", customer_email.body)
        self.assertIn("$50.00", customer_email.body)
        self.assertIn("New order #1", owner_email.subject)
        self.assertIn("Email Test Product", owner_email.body)
        self.assertIn("$50.00", owner_email.body)

    @override_settings(ORDER_NOTIFICATION_EMAILS=[])
    def test_empty_owner_recipient_list_skips_owner_email(self):
        self.post_checkout()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["customer@example.com"])

    def test_empty_cart_sends_no_email(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("store:checkout"), self.checkout_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox, [])

    def test_invalid_form_sends_no_email(self):
        response = self.post_checkout(data=self.checkout_data | {"email": "invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_out_of_stock_order_sends_no_email(self):
        response = self.post_checkout(quantity=6)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(mail.outbox, [])

    def test_email_failure_does_not_break_checkout(self):
        with patch("store.emails.EmailMultiAlternatives.send", side_effect=RuntimeError("SMTP unavailable")):
            response = self.post_checkout()

        self.assertRedirects(response, reverse("store:order_confirmation", args=[1]))
        self.assertEqual(Order.objects.count(), 1)

    def test_confirmation_reload_does_not_send_extra_email(self):
        response = self.post_checkout()
        email_count = len(mail.outbox)

        self.assertEqual(self.client.get(response.url).status_code, 200)
        self.assertEqual(self.client.get(response.url).status_code, 200)
        self.assertEqual(len(mail.outbox), email_count)

    def test_customer_html_escapes_dynamic_name(self):
        self.post_checkout(data=self.checkout_data | {"full_name": "<script>alert(1)</script>"})

        customer_email = next(message for message in mail.outbox if message.to == ["customer@example.com"])
        html_body = customer_email.alternatives[0][0]
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_body)
        self.assertNotIn("<script>alert(1)</script>", html_body)