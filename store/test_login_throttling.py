from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(LOGIN_MAX_FAILED_PER_USER_IP=5, LOGIN_MAX_FAILED_PER_IP=20, LOGIN_LOCKOUT_SECONDS=900)
class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="throttle-user", password="CorrectPassword123!")
        self.url = reverse("store:login")

    def post_login(self, username="throttle-user", password="wrong", ip="10.0.0.1"):
        return self.client.post(self.url, {"username": username, "password": password}, REMOTE_ADDR=ip)

    def test_five_wrong_passwords_block_correct_password(self):
        for _ in range(5):
            self.assertEqual(self.post_login().status_code, 200)
        response = self.post_login(password="CorrectPassword123!")
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many login attempts. Please try again in", status_code=429)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_other_ip_is_unaffected_and_success_resets_user_counter(self):
        for _ in range(4):
            self.post_login(ip="10.0.0.1")
        self.assertEqual(self.post_login(password="CorrectPassword123!", ip="10.0.0.2").status_code, 302)
        cache.clear()
        for _ in range(4):
            self.post_login(ip="10.0.0.1")
        self.assertEqual(self.post_login(password="CorrectPassword123!", ip="10.0.0.1").status_code, 302)

    def test_unknown_user_is_counted(self):
        for _ in range(5):
            self.post_login(username="unknown-user")
        self.assertEqual(self.post_login(username="unknown-user", password="anything").status_code, 429)

    def test_cache_failure_fails_open(self):
        with patch("store.throttle.cache.get", side_effect=RuntimeError("cache down")), patch(
            "store.throttle.cache.set", side_effect=RuntimeError("cache down")
        ):
            response = self.post_login(password="CorrectPassword123!")
        self.assertEqual(response.status_code, 302)

    def test_expiry_allows_login_after_counter_is_cleared(self):
        for _ in range(5):
            self.post_login()
        self.assertEqual(self.post_login(password="CorrectPassword123!").status_code, 429)
        cache.clear()
        self.assertEqual(self.post_login(password="CorrectPassword123!").status_code, 302)