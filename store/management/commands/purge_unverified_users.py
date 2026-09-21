from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete expired inactive accounts that have not verified their email."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=None)

    def handle(self, *args, **options):
        minutes = options["minutes"]
        if minutes is None:
            minutes = settings.UNVERIFIED_ACCOUNT_LIFETIME_MINUTES
        cutoff = timezone.now() - timedelta(minutes=minutes)
        users = User.objects.filter(
            is_active=False,
            is_staff=False,
            is_superuser=False,
            email_verification__isnull=False,
            email_verification__verified_at__isnull=True,
            email_verification__created_at__lt=cutoff,
            orders__isnull=True,
        ).distinct()
        count = users.count()
        users.delete()
        self.stdout.write(f"Removed {count} unverified account(s).")
