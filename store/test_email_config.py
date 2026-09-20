import io
import os
import smtplib
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from config.settings import _email_transport, _normalize_password, load_dotenv
import config.settings as project_settings
from django.contrib.auth import get_user_model

from .models import Product


User = get_user_model()


class DotEnvLoaderTests(TestCase):
    def test_loader_supports_comments_quotes_spaces_bom_and_does_not_override_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "\ufeff# comment\nQUOTED=\"value with spaces\"\nANGLE=DepalNova <me@gmail.com>\nREAL=from-file\nBLANK=\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"REAL": "from-environment"}, clear=True):
                load_dotenv(path)
                self.assertEqual(os.environ["QUOTED"], "value with spaces")
                self.assertEqual(os.environ["ANGLE"], "DepalNova <me@gmail.com>")
                self.assertEqual(os.environ["REAL"], "from-environment")
                self.assertEqual(os.environ["BLANK"], "")

    def test_password_whitespace_is_removed(self):
        self.assertEqual(_normalize_password(" ab cd\t ef "), "abcdef")

    def test_placeholders_use_console_mode(self):
        self.assertFalse(project_settings.EMAIL_CONFIGURED)
        self.assertEqual(project_settings.EMAIL_BACKEND, "django.core.mail.backends.console.EmailBackend")

    def test_ssl_and_tls_are_never_enabled_together(self):
        with patch.dict(os.environ, {"EMAIL_USE_SSL": "True", "EMAIL_USE_TLS": "True", "EMAIL_PORT": "465"}, clear=False):
            use_ssl, use_tls, port = _email_transport()

        self.assertTrue(use_ssl)
        self.assertFalse(use_tls)
        self.assertEqual(port, 465)


class SendTestEmailCommandTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
        DEFAULT_FROM_EMAIL="DepalNova <no-reply@example.com>",
        ORDER_NOTIFICATION_EMAILS=[],
    )
    def test_console_mode_warns_and_sends_to_console_backend(self):
        output = io.StringIO()
        call_command("send_test_email", "test@example.com", stdout=output)

        self.assertIn("console.EmailBackend", output.getvalue())
        self.assertIn("NOT delivered", output.getvalue())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="DepalNova <no-reply@example.com>",
        ORDER_NOTIFICATION_EMAILS=[],
    )
    def test_locmem_mode_sends_test_email(self):
        call_command("send_test_email", "test@example.com", stdout=io.StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="DepalNova <no-reply@example.com>",
        EMAIL_HOST_USER="sender@example.com",
        EMAIL_HOST_PASSWORD="placeholder",
        ORDER_NOTIFICATION_EMAILS=[],
    )
    def test_authentication_failure_shows_gmail_hint_and_nonzero_exit(self):
        error = smtplib.SMTPAuthenticationError(535, b"authentication failed")
        output = io.StringIO()
        errors = io.StringIO()
        with patch("django.core.mail.EmailMessage.send", side_effect=error), self.assertRaises(SystemExit) as raised:
            call_command("send_test_email", "test@example.com", stdout=output, stderr=errors)

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Gmail App Password", errors.getvalue())


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    DEFAULT_FROM_EMAIL="DepalNova <no-reply@example.com>",
    ORDER_NOTIFICATION_EMAILS=[],
)
class ConsoleOrderLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="consoleuser", password="StrongPassword123!")
        self.product = Product.objects.create(
            name="Console Log Product",
            description="Product for console logging.",
            price="12.00",
            category="General",
            stock=2,
            is_available=True,
        )

    def test_order_placement_logs_console_warning(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()
        data = {
            "full_name": "Console Customer",
            "email": "customer@example.com",
            "phone": "03001234567",
            "address": "123 Test Street",
            "city": "Karachi",
            "state": "Sindh",
            "postal_code": "74000",
            "country": "Pakistan",
            "review_only": "1",
        }

        with self.assertLogs("store", level="WARNING") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("store:checkout"), data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(any("NOT delivered" in line for line in logs.output))
