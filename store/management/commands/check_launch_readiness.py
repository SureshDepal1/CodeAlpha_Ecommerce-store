import os
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import checks
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count

from store.models import Order, Product


class Command(BaseCommand):
    help = "Check production launch readiness without changing application data."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
        parser.add_argument("--send-test", action="store_true", help="Send one test email using configured SMTP.")

    def handle(self, *args, **options):
        self.failures = 0
        self.warnings = 0
        self.strict = options["strict"]
        self.check_runtime()
        self.check_files_and_database()
        self.check_catalog_and_orders()
        self.check_users()
        self.check_store_configuration()
        self.check_git_hygiene()
        if options["send_test"]:
            self.send_test_email()

        self.stdout.write("")
        self.stdout.write(f"Summary: {self.failures} FAIL, {self.warnings} WARN")
        if self.failures or (self.strict and self.warnings):
            raise SystemExit(1)

    def report(self, level, message):
        if level == "FAIL":
            self.failures += 1
            styled = self.style.ERROR(level)
        elif level == "WARN":
            self.warnings += 1
            styled = self.style.WARNING(level)
        else:
            styled = self.style.SUCCESS(level)
        self.stdout.write(f"{styled}: {message}")

    def check_runtime(self):
        self.report("FAIL" if settings.DEBUG else "PASS", "DEBUG is off" if not settings.DEBUG else "DEBUG is enabled")
        secret_ok = bool(settings.SECRET_KEY) and len(settings.SECRET_KEY) >= 50 and not settings.SECRET_KEY.startswith("django-insecure-")
        self.report("PASS" if secret_ok else "FAIL", "secret key meets production length requirements" if secret_ok else "secret key is missing or too weak")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        public_hosts = [host for host in settings.ALLOWED_HOSTS if host not in local_hosts]
        self.report("PASS" if public_hosts else "FAIL", "ALLOWED_HOSTS includes a public host" if public_hosts else "ALLOWED_HOSTS contains only local hosts")
        parsed_url = urlparse(settings.SITE_URL)
        site_ok = parsed_url.scheme == "https" and parsed_url.hostname not in local_hosts
        self.report("PASS" if site_ok else "FAIL", "SITE_URL is a public HTTPS URL" if site_ok else "SITE_URL is not a public HTTPS URL")
        smtp_ok = bool(getattr(settings, "EMAIL_CONFIGURED", False)) and "console.EmailBackend" not in settings.EMAIL_BACKEND
        self.report("PASS" if smtp_ok else "FAIL", "real SMTP email is configured" if smtp_ok else "real SMTP email is not configured")
        if getattr(settings, "CACHE_BACKEND", "locmem") != "database" and not settings.DEBUG:
            self.report("WARN", "production uses a per-process cache; set DJANGO_CACHE_BACKEND=database for multiple processes")

    def check_files_and_database(self):
        static_files = settings.STATIC_ROOT.exists() and any(settings.STATIC_ROOT.rglob("*"))
        self.report("PASS" if static_files else "FAIL", "static files are collected" if static_files else "static files are not collected")
        media_ready = settings.MEDIA_ROOT.exists() and os.access(settings.MEDIA_ROOT, os.W_OK)
        self.report("PASS" if media_ready else "FAIL", "media directory exists and is writable" if media_ready else "media directory is missing or not writable")
        if connection.vendor == "sqlite":
            self.report("WARN", "SQLite is active; production storage must use a persistent disk")
        else:
            self.report("PASS", f"database engine is {connection.vendor}")
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.report("PASS" if not pending else "FAIL", "database migrations are up to date" if not pending else f"{len(pending)} migration(s) are pending")
        superuser_exists = get_user_model().objects.filter(is_superuser=True).exclude(email="").exists()
        self.report("PASS" if superuser_exists else "FAIL", "a superuser with an email exists" if superuser_exists else "no superuser with an email exists")

    def check_catalog_and_orders(self):
        products = Product.objects.all()
        missing_media = products.filter(image="").count()
        missing_description = products.filter(description="").count()
        invalid_prices = products.filter(price__lte=0).count()
        self.report("INFO", f"catalog: {products.count()} products; {missing_media} without images; {missing_description} without descriptions; {invalid_prices} with price <= 0")
        categories = sorted({(value or "").strip() for value in products.values_list("category", flat=True) if (value or "").strip()}, key=str.casefold)
        names = list(products.values_list("name", flat=True).order_by("name"))
        self.report("INFO", f"catalog categories for spelling review: {', '.join(categories) or '(none)'}")
        self.report("INFO", f"catalog product names for spelling review: {', '.join(names) or '(none)'}")
        pending = Order.objects.filter(status=Order.Status.PENDING).count()
        self.report("INFO", f"orders: {Order.objects.count()} total, {pending} pending; review and delete test orders before launch")

    def check_users(self):
        User = get_user_model()
        without_email = User.objects.filter(email="").count()
        duplicate_emails = defaultdict(list)
        for user in User.objects.exclude(email="").values("username", "email"):
            duplicate_emails[user["email"].strip().casefold()].append(user["username"])
        duplicates = [names for names in duplicate_emails.values() if len(names) > 1]
        self.report("WARN" if without_email else "PASS", f"users without email: {without_email}")
        self.report("WARN" if duplicates else "PASS", f"duplicate email groups: {len(duplicates)}")

    def check_store_configuration(self):
        configured_contact = any((settings.STORE_CONTACT_EMAIL, settings.STORE_PHONE, settings.STORE_ADDRESS))
        self.report("PASS" if configured_contact else "WARN", "store contact details are configured" if configured_contact else "store contact details are empty")
        policy_configured = bool(settings.RETURN_POLICY_SUMMARY and settings.DELIVERY_TIME_SUMMARY)
        self.report("PASS" if policy_configured else "WARN", "return and delivery summaries are configured" if policy_configured else "return or delivery summaries are empty")
        self.report("INFO", "price format uses the default dollar format" if settings.STORE_PRICE_FORMAT == "${amount}" else "price format is customized")

    def check_git_hygiene(self):
        try:
            tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
            protected = [
                path for path in tracked
                if path == ".env" or path.endswith(".sqlite3") or ".sqlite3." in path or path.endswith(".backup")
                or path.startswith(("logs/", "media/"))
            ]
            self.report("FAIL" if protected else "PASS", "git hygiene excludes secrets, databases, backups, logs, and media" if not protected else "protected files are tracked")
            history = subprocess.run(["git", "log", "--all", "--name-only", "--pretty="], capture_output=True, text=True, check=True).stdout.splitlines()
            self.report("WARN" if any(path == "db.sqlite3.backup" for path in history) else "PASS", "a database backup exists in git history" if any(path == "db.sqlite3.backup" for path in history) else "no database backup found in git history")
        except (OSError, subprocess.CalledProcessError):
            self.report("WARN", "git is unavailable; repository hygiene was not checked")

    def send_test_email(self):
        if not getattr(settings, "EMAIL_CONFIGURED", False):
            self.report("FAIL", "test email was requested but SMTP is not configured")
            return
        recipient = settings.ORDER_NOTIFICATION_EMAILS[0] if settings.ORDER_NOTIFICATION_EMAILS else settings.EMAIL_HOST_USER
        try:
            EmailMessage(
                subject="DepalNova launch readiness test",
                body="This is a launch-readiness test email.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)
        except Exception:
            self.report("FAIL", "test email could not be sent")
        else:
            domain = recipient.rsplit("@", 1)[-1] if "@" in recipient else "unknown"
            self.report("PASS", f"test email sent to configured recipient domain {domain}")
