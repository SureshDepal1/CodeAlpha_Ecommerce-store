from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings


class LaunchReadinessCommandTests(TestCase):
    def test_default_configuration_fails_without_exposing_secret(self):
        output = StringIO()
        with self.assertRaises(SystemExit) as raised:
            call_command("check_launch_readiness", stdout=output)

        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn("development-only-key", output.getvalue())
        self.assertIn("FAIL", output.getvalue())

    @override_settings(
        DEBUG=False,
        SECRET_KEY="x" * 60,
        ALLOWED_HOSTS=["shop.example.com"],
        SITE_URL="https://shop.example.com",
        EMAIL_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        CACHE_BACKEND="database",
        STORE_CONTACT_EMAIL="hello@shop.example.com",
        RETURN_POLICY_SUMMARY="Contact the store about returns.",
        DELIVERY_TIME_SUMMARY="Delivery details are provided by the store.",
    )
    @patch("store.management.commands.check_launch_readiness.Command.check_git_hygiene")
    @patch("store.management.commands.check_launch_readiness.connection.vendor", "postgresql")
    def test_strict_passes_with_production_configuration(self, check_git_hygiene):
        User = get_user_model()
        User.objects.create_superuser("launch-admin", "admin@shop.example.com", "StrongPassword123!")
        output = StringIO()

        call_command("check_launch_readiness", "--strict", stdout=output)

        self.assertIn("Summary: 0 FAIL", output.getvalue())
        check_git_hygiene.assert_called_once()

    @override_settings(
        DEBUG=False,
        SECRET_KEY="x" * 60,
        ALLOWED_HOSTS=["shop.example.com"],
        SITE_URL="https://shop.example.com",
        EMAIL_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        ORDER_NOTIFICATION_EMAILS=["owner@shop.example.com"],
    )
    @patch("store.management.commands.check_launch_readiness.Command.check_git_hygiene")
    @patch("store.management.commands.check_launch_readiness.EmailMessage.send", return_value=1)
    def test_send_test_uses_configured_email(self, send, check_git_hygiene):
        get_user_model().objects.create_superuser("email-admin", "admin@shop.example.com", "StrongPassword123!")
        output = StringIO()

        call_command("check_launch_readiness", "--send-test", stdout=output)

        send.assert_called_once()
        self.assertIn("test email sent", output.getvalue())
