import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerification


User = get_user_model()


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="OldPassword123!",
        )

    def request_reset(self, email, ip="10.0.0.1"):
        return self.client.post(
            reverse("store:password_reset"),
            {"email": email},
            REMOTE_ADDR=ip,
        )

    def test_full_flow_changes_password_and_old_password_fails(self):
        response = self.request_reset(self.user.email)
        self.assertRedirects(response, reverse("store:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"/reset/([^/]+)/([^/]+)/", mail.outbox[0].body)
        self.assertIsNotNone(match)

        response = self.client.get(reverse("store:password_reset_confirm", args=match.groups()))
        self.assertEqual(response.status_code, 302)
        confirm_url = response.url
        response = self.client.post(confirm_url, {"new_password1": "NewPassword123!", "new_password2": "NewPassword123!"})
        self.assertRedirects(response, reverse("store:password_reset_complete"))
        self.assertTrue(self.client.login(username=self.user.username, password="NewPassword123!"))
        self.client.logout()
        self.assertFalse(self.client.login(username=self.user.username, password="OldPassword123!"))

    def test_unknown_email_is_indistinguishable_and_sends_nothing(self):
        response = self.request_reset("missing@example.com")
        self.assertRedirects(response, reverse("store:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_user_receives_nothing(self):
        pending = User.objects.create_user(username="pending-reset", email="pending@example.com", password="OldPassword123!")
        pending.is_active = False
        pending.save(update_fields=("is_active",))
        EmailVerification.objects.create(
            user=pending,
            code_hash="hash",
            code_sent_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.request_reset(pending.email)
        self.assertEqual(len(mail.outbox), 0)

    def test_shared_email_gets_a_link_for_each_active_account(self):
        User.objects.create_user(username="reset-user-two", email=self.user.email, password="OldPassword123!")
        self.request_reset(self.user.email)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(PASSWORD_RESET_EMAIL_LIMIT=1, PASSWORD_RESET_IP_LIMIT=5)
    def test_email_throttle_still_returns_same_done_page(self):
        self.request_reset(self.user.email)
        response = self.request_reset(self.user.email, ip="10.0.0.2")
        self.assertRedirects(response, reverse("store:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_token_shows_friendly_message(self):
        self.request_reset(self.user.email)
        match = re.search(r"/reset/([^/]+)/([^/]+)/", mail.outbox[0].body)
        with patch("django.contrib.auth.tokens.PasswordResetTokenGenerator.check_token", return_value=False):
            response = self.client.get(reverse("store:password_reset_confirm", args=match.groups()))
        self.assertContains(response, "invalid or has expired")