import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from .models import EmailVerification, Order


User = get_user_model()


OTP_TEST_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "DepalNova <no-reply@example.com>",
    "OTP_EXPIRY_SECONDS": 600,
    "OTP_RESEND_COOLDOWN_SECONDS": 60,
    "OTP_MAX_SENDS": 3,
    "OTP_MAX_ATTEMPTS": 3,
    "OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR": 20,
    "OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR": 20,
    "UNVERIFIED_ACCOUNT_LIFETIME_MINUTES": 60,
}


@override_settings(**OTP_TEST_SETTINGS)
class EmailOTPTests(TestCase):
    registration_data = {
        "username": "otpuser",
        "email": "otpuser@example.com",
        "password1": "A-strong-registration-password-123!",
        "password2": "A-strong-registration-password-123!",
    }

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def register(self, data=None):
        response = self.client.post(reverse("store:register"), data or self.registration_data)
        user = User.objects.get(username=(data or self.registration_data)["username"])
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
        return response, user, code

    def verify(self, code):
        return self.client.post(reverse("store:verify_email"), {"code": code}, follow=True)

    def test_full_registration_verification_logs_user_in(self):
        response, user, code = self.register()

        self.assertRedirects(response, reverse("store:verify_email"))
        response = self.verify(code)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(response, reverse("store:home"))
        self.assertContains(response, "Account created successfully.")

    def test_wrong_code_decrements_attempts_and_locks(self):
        _, user, _ = self.register()

        for expected_remaining in (2, 1):
            response = self.client.post(reverse("store:verify_email"), {"code": "000000"})
            self.assertContains(response, f"{expected_remaining} attempts left.")
        response = self.client.post(reverse("store:verify_email"), {"code": "000000"})
        self.assertContains(response, "Too many incorrect attempts. Request a new code.")
        self.assertEqual(EmailVerification.objects.get(user=user).attempts, 3)

    def test_expired_code_is_rejected(self):
        _, user, code = self.register()
        verification = EmailVerification.objects.get(user=user)
        verification.expires_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=("expires_at",))

        response = self.verify(code)

        self.assertContains(response, "This code has expired. Request a new one.")
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_resend_cooldown_and_max_sends_are_enforced(self):
        _, user, _ = self.register()
        response = self.client.post(reverse("store:verify_email"), {"action": "resend"}, follow=True)
        self.assertContains(response, "Please wait before requesting another code.")
        verification = EmailVerification.objects.get(user=user)
        verification.code_sent_at = timezone.now() - timedelta(seconds=61)
        verification.save(update_fields=("code_sent_at",))
        self.client.post(reverse("store:verify_email"), {"action": "resend"}, follow=True)
        verification.refresh_from_db()
        self.assertEqual(verification.send_count, 2)
        verification.code_sent_at = timezone.now() - timedelta(seconds=61)
        verification.save(update_fields=("code_sent_at",))
        self.client.post(reverse("store:verify_email"), {"action": "resend"}, follow=True)
        response = self.client.post(reverse("store:verify_email"), {"action": "resend"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailVerification.objects.get(user=user).send_count, 3)

    def test_new_code_invalidates_old_code(self):
        _, user, old_code = self.register()
        verification = EmailVerification.objects.get(user=user)
        verification.code_sent_at = timezone.now() - timedelta(seconds=61)
        verification.save(update_fields=("code_sent_at",))
        self.client.post(reverse("store:verify_email"), {"action": "resend"}, follow=True)
        new_code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()

        response = self.verify(old_code)
        self.assertContains(response, "Incorrect code.")
        response = self.verify(new_code)
        self.assertRedirects(response, reverse("store:home"))

    def test_code_is_hashed_and_not_in_session_or_page_or_logs(self):
        with self.assertLogs("store", level="INFO") as logs:
            response, user, code = self.register()
            response = self.client.get(reverse("store:verify_email"))
        verification = EmailVerification.objects.get(user=user)

        self.assertNotEqual(verification.code_hash, code)
        self.assertNotIn(code, str(self.client.session.items()))
        self.assertNotContains(response, code)
        self.assertNotIn(code, "\n".join(logs.output))

    def test_email_uniqueness_allows_pending_but_rejects_verified(self):
        _, first_user, first_code = self.register()
        second_data = self.registration_data | {"username": "second", "email": "OTPUSER@example.com"}
        response = self.client.post(reverse("store:register"), second_data)
        self.assertEqual(response.status_code, 302)
        second_user = User.objects.get(username="second")
        self.assertNotEqual(first_user.pk, second_user.pk)
        session = self.client.session
        session["pending_verification_user_id"] = first_user.pk
        session.save()
        self.client.post(reverse("store:verify_email"), {"code": first_code})
        self.client.logout()
        rejected = self.client.post(reverse("store:register"), self.registration_data | {"username": "third"})
        self.assertContains(rejected, "An account with this email already exists. Try logging in.")

    def test_verification_deletes_other_pending_accounts_with_same_email(self):
        _, first_user, first_code = self.register()
        second = User.objects.create_user(username="second", email=first_user.email, password="AnotherPassword123!", is_active=False)
        EmailVerification.objects.create(
            user=second,
            code_hash="unused",
            code_sent_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.verify(first_code)
        self.assertRedirects(response, reverse("store:home"))
        self.assertFalse(User.objects.filter(pk=second.pk).exists())

    def test_old_account_without_verification_can_log_in(self):
        User.objects.create_user(username="olduser", email="old@example.com", password="OldPassword123!")
        response = self.client.post(reverse("store:login"), {"username": "olduser", "password": "OldPassword123!"})
        self.assertRedirects(response, reverse("store:home"))

    def test_pending_login_with_right_password_goes_to_verification(self):
        self.register()
        self.client.logout()
        response = self.client.post(reverse("store:login"), {"username": "otpuser", "password": self.registration_data["password1"]})
        self.assertRedirects(response, reverse("store:verify_email"))

    def test_pending_login_with_wrong_password_keeps_generic_error(self):
        self.register()
        self.client.logout()
        response = self.client.post(reverse("store:login"), {"username": "otpuser", "password": "wrong-password"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password.")

    def test_verify_without_pending_session_redirects_to_register(self):
        response = self.client.get(reverse("store:verify_email"))
        self.assertRedirects(response, reverse("store:register"))

    @patch("store.views.send_verification_code", side_effect=RuntimeError("mail unavailable"))
    def test_email_failure_leaves_no_orphan_account(self, send_code):
        response = self.client.post(reverse("store:register"), self.registration_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We couldn")
        self.assertFalse(User.objects.filter(username="otpuser").exists())
        self.assertFalse(EmailVerification.objects.exists())

    @override_settings(OTP_MAX_EMAILS_PER_ADDRESS_PER_HOUR=1)
    def test_per_address_throttle(self):
        self.register()
        data = self.registration_data | {"username": "second"}
        response = self.client.post(reverse("store:register"), data)
        self.assertContains(response, "Too many attempts, please try again later.")

    @override_settings(OTP_MAX_REGISTRATIONS_PER_IP_PER_HOUR=1)
    def test_per_ip_throttle(self):
        self.register()
        data = self.registration_data | {"username": "second", "email": "second@example.com"}
        response = self.client.post(reverse("store:register"), data)
        self.assertContains(response, "Too many attempts, please try again later.")


@override_settings(**OTP_TEST_SETTINGS)
class PurgeAndAdminOTPTests(TestCase):
    def test_purge_command_keeps_orders_verified_old_and_admin_disabled_users(self):
        old = timezone.now() - timedelta(minutes=120)
        pending = User.objects.create_user(username="pending", email="pending@example.com", is_active=False)
        pending_verification = EmailVerification.objects.create(user=pending, code_hash="x", code_sent_at=old, expires_at=old)
        EmailVerification.objects.filter(pk=pending_verification.pk).update(created_at=old)
        with_order = User.objects.create_user(username="ordered", email="ordered@example.com", is_active=False)
        ordered_verification = EmailVerification.objects.create(user=with_order, code_hash="x", code_sent_at=old, expires_at=old)
        EmailVerification.objects.filter(pk=ordered_verification.pk).update(created_at=old)
        Order.objects.create(user=with_order, full_name="Customer", email=with_order.email, phone="1", address="Street", city="City", state="State", postal_code="1", country="Country", total_amount="1.00")
        verified = User.objects.create_user(username="verified", email="verified@example.com", is_active=True)
        verification = EmailVerification.objects.create(user=verified, code_hash="", code_sent_at=old, expires_at=old, verified_at=timezone.now())
        disabled = User.objects.create_user(username="disabled", email="disabled@example.com", is_active=False)

        output = StringIO()
        call_command("purge_unverified_users", minutes=60, stdout=output)

        self.assertIn("Removed 1 unverified account(s).", output.getvalue())
        self.assertFalse(User.objects.filter(username="pending").exists())
        self.assertTrue(User.objects.filter(username__in=("ordered", "verified", "disabled")).count(), 3)
        self.assertTrue(EmailVerification.objects.filter(pk=verification.pk).exists())

    def test_admin_page_loads(self):
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="AdminPassword123!")
        self.client.force_login(admin)
        response = self.client.get("/admin/store/emailverification/")
        self.assertEqual(response.status_code, 200)
