from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand

from store.emails import _failure_hint


class Command(BaseCommand):
    help = "Send a test email using the active DepalNova email configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            "address",
            nargs="?",
            help="Recipient address; defaults to the first owner recipient or the SMTP user.",
        )

    def handle(self, *args, **options):
        recipient = options.get("address") or (
            settings.ORDER_NOTIFICATION_EMAILS[0]
            if settings.ORDER_NOTIFICATION_EMAILS
            else settings.EMAIL_HOST_USER
        )
        if not recipient:
            self.stderr.write(self.style.ERROR("No recipient is configured. Pass an email address explicitly."))
            raise SystemExit(1)

        console_mode = settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
        self.stdout.write(f"Email backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"SMTP host: {getattr(settings, 'EMAIL_HOST', '(console)')}")
        self.stdout.write(f"SMTP port: {getattr(settings, 'EMAIL_PORT', '(console)')}")
        self.stdout.write(f"SMTP user configured: {'yes' if settings.EMAIL_CONFIGURED else 'no'}")
        self.stdout.write(f"SMTP password configured: {'yes' if settings.EMAIL_CONFIGURED else 'no'}")
        self.stdout.write(f"From address configured: {'yes' if settings.DEFAULT_FROM_EMAIL else 'no'}")
        self.stdout.write(f"Owner recipients configured: {len(settings.ORDER_NOTIFICATION_EMAILS)}")
        self.stdout.write(f"Test recipient domain: {recipient.rsplit('@', 1)[-1] if '@' in recipient else 'unknown'}")

        if console_mode:
            self.stdout.write(self.style.WARNING(
                "WARNING: console mode is active. The email will be printed here and NOT delivered; configure .env."
            ))

        try:
            EmailMessage(
                subject="DepalNova test email",
                body="This is a test email from DepalNova.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Test email failed: {_failure_hint(error)}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Test email sent successfully."))