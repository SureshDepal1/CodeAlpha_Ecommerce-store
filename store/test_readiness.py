import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core import checks
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import SimpleTestCase, override_settings

from config.settings import (
    DEVELOPMENT_SECRET_KEY,
    parse_csrf_trusted_origins,
    parse_database_url,
    parse_proxy_settings,
    resolve_secret_key,
)
from store.checks import deployment_checks


class SettingsHelperTests(SimpleTestCase):
    def test_production_secret_key_is_required(self):
        with self.assertRaises(ImproperlyConfigured) as raised:
            resolve_secret_key(False, {})
        self.assertIn("python -c", str(raised.exception))

    def test_development_secret_key_remains_available_only_in_debug(self):
        self.assertEqual(resolve_secret_key(True, {}), DEVELOPMENT_SECRET_KEY)
        self.assertEqual(resolve_secret_key(False, {"DJANGO_SECRET_KEY": "x" * 60}), "x" * 60)

    def test_proxy_and_csrf_settings_are_parsed(self):
        environ = {
            "DJANGO_BEHIND_PROXY": "true",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://shop.example, https://admin.example",
        }
        self.assertEqual(parse_proxy_settings(environ), ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(parse_csrf_trusted_origins(environ), ["https://shop.example", "https://admin.example"])
        self.assertIsNone(parse_proxy_settings({}))

    def test_postgres_url_is_parsed_without_connecting(self):
        config = parse_database_url("postgresql://user:pass@example.test:5433/shop?sslmode=require")
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "shop")
        self.assertEqual(config["USER"], "user")
        self.assertEqual(config["PASSWORD"], "pass")
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})
        self.assertEqual(config["CONN_MAX_AGE"], 60)


class DeploymentCheckTests(SimpleTestCase):
    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        EMAIL_HOST_USER="your-email@gmail.com",
        EMAIL_HOST_PASSWORD="PASTE_APP_PASSWORD_HERE",
    )
    def test_production_checks_only_run_with_deploy_flag(self):
        normal_output = tempfile.TemporaryFile(mode="w+")
        call_command("check", stdout=normal_output)
        normal_output.seek(0)
        self.assertNotIn("store.E001", normal_output.read())

        normal_ids = {
            message.id
            for message in checks.run_checks(include_deployment_checks=False)
            if message.id == "store.E001"
        }
        deploy_ids = {
            message.id
            for message in checks.run_checks(include_deployment_checks=True)
            if message.id == "store.E001"
        }
        self.assertEqual(normal_ids, set())
        self.assertEqual(deploy_ids, {"store.E001"})

        deploy_output = tempfile.TemporaryFile(mode="w+")
        with self.assertRaises(SystemCheckError):
            call_command("check", deploy=True, stdout=deploy_output)
        deploy_output.seek(0)

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        EMAIL_HOST_USER="your-email@gmail.com",
        EMAIL_HOST_PASSWORD="PASTE_APP_PASSWORD_HERE",
        SITE_URL="http://127.0.0.1:8000",
        ALLOWED_HOSTS=["localhost"],
        STATIC_ROOT=Path(tempfile.gettempdir()) / "depalnova-missing-static-root",
    )
    def test_production_checks_report_each_launch_blocker(self):
        ids = {message.id for message in deployment_checks(None)}
        self.assertEqual(ids, {"store.E001", "store.W001", "store.W002", "store.W003"})

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="sender@example.test",
        EMAIL_HOST_PASSWORD="fake-app-password",
        SITE_URL="https://shop.example.test",
        ALLOWED_HOSTS=["shop.example.test"],
        STATIC_ROOT=Path(tempfile.gettempdir()),
    )
    def test_production_checks_are_clear_for_configured_values(self):
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "iterdir", return_value=[Path("style.css")]):
            self.assertEqual(deployment_checks(None), [])


class StaticFilesTests(SimpleTestCase):
    def test_collectstatic_writes_css_to_a_temp_root(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(STATIC_ROOT=Path(directory)):
                call_command("collectstatic", interactive=False, verbosity=0, clear=True)
                css = Path(directory) / "css" / "style.css"
                self.assertTrue(css.exists())
                self.assertIn("body", css.read_text(encoding="utf-8"))
