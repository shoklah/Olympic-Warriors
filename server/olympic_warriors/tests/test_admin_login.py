"""
The login throttle on the admin login form: every submitted form counts per client IP, in the
same bucket as /auth/token/, and past the limit the form comes back with the "throttled" error
before any password is checked. How the IP is read is covered in depth by test_auth_token.py.
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from olympic_warriors.throttling import LoginRateThrottle

# Attempts allowed per window at the configured rate (LOGIN_THROTTLE_RATE, 5/min by default).
LIMIT = LoginRateThrottle().num_requests


# A private local-memory cache, as in test_auth_token.py, and plain static storage: the
# manifest one needs a collectstatic the tests never run.
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "admin-login-throttle-tests",
        }
    },
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class TestAdminLoginThrottle(TestCase):

    def setUp(self):
        # The counts live in the cache, which no test transaction rolls back.
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(username="ana", password="right-password", is_staff=True)

    def login(self, password, forwarded_for="203.0.113.7", **extra):
        """Submit the admin login form as ana; `forwarded_for` is X-Forwarded-For, None for none."""
        if forwarded_for is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
        return self.client.post(
            "/admin/login/?next=/admin/", {"username": "ana", "password": password}, **extra
        )

    def api_login(self, password):
        return APIClient().post(
            "/auth/token/",
            {"username": "ana", "password": password},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )

    def error_codes(self, response):
        """The codes of the form-wide errors on a re-rendered login page."""
        self.assertEqual(response.status_code, 200)
        return [error.code for error in response.context["form"].non_field_errors().as_data()]

    def assert_logged_in(self, response):
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def exhaust(self, **kwargs):
        for _ in range(LIMIT):
            self.assertEqual(self.error_codes(self.login("guess", **kwargs)), ["invalid_login"])

    def test_a_normal_login_works(self):
        self.assert_logged_in(self.login("right-password"))

    def test_failed_attempts_are_refused_past_the_limit(self):
        self.exhaust()
        response = self.login("guess")
        self.assertEqual(self.error_codes(response), ["throttled"])
        self.assertRegex(
            response.content.decode(),
            r"Trop de tentatives de connexion depuis cette adresse\. Réessayez dans \d+ s\.",
        )

    def test_the_right_password_is_refused_too_once_throttled(self):
        self.exhaust()
        self.assertEqual(self.error_codes(self.login("right-password")), ["throttled"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_viewing_the_login_page_does_not_count(self):
        for _ in range(LIMIT + 1):
            self.client.get("/admin/login/", HTTP_X_FORWARDED_FOR="203.0.113.7")
        self.assert_logged_in(self.login("right-password"))

    def test_each_client_ip_has_its_own_bucket(self):
        self.exhaust(forwarded_for="203.0.113.7")
        self.assert_logged_in(self.login("right-password", forwarded_for="198.51.100.4"))

    def test_a_forged_forwarded_prefix_does_not_open_a_new_bucket(self):
        # NUM_PROXIES = 1, as on the API: only the last entry names the client.
        for i in range(LIMIT):
            response = self.login("guess", forwarded_for=f"10.0.0.{i}, 203.0.113.7")
            self.assertEqual(self.error_codes(response), ["invalid_login"])
        response = self.login("guess", forwarded_for="10.0.0.99, 203.0.113.7")
        self.assertEqual(self.error_codes(response), ["throttled"])

    def test_an_ipv6_client_counts_by_its_64(self):
        # client_key, as on the API.
        self.exhaust(forwarded_for="2001:db8:1:2::1")
        response = self.login("guess", forwarded_for="2001:db8:1:2:ffff:ffff:ffff:ffff")
        self.assertEqual(self.error_codes(response), ["throttled"])

    def test_attempts_on_the_api_count_against_the_admin(self):
        for _ in range(LIMIT):
            self.assertEqual(self.api_login("guess").status_code, 400)
        self.assertEqual(self.error_codes(self.login("right-password")), ["throttled"])

    def test_attempts_on_the_admin_count_against_the_api(self):
        self.exhaust()
        self.assertEqual(self.api_login("right-password").status_code, 429)
