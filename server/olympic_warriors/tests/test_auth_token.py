"""
The login throttle on /auth/token/: attempts counted per client IP, whatever their outcome
and whatever token the caller carries; the rest of the API is never throttled, but for a
claim link's POST, which shares the bucket (test_claims.py).
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import Edition
from olympic_warriors.throttling import LoginRateThrottle

# Attempts allowed per window at the configured rate (LOGIN_THROTTLE_RATE, 5/min by default).
LIMIT = LoginRateThrottle().num_requests


# A private local-memory cache: the configured one is a directory in the temp dir, which a
# server running in the same container shares and a test must neither read nor wipe.
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "login-throttle-tests",
        }
    }
)
class TestLoginThrottle(APITestCase):

    def setUp(self):
        # The counts live in the cache, which no test transaction rolls back.
        cache.clear()
        self.addCleanup(cache.clear)
        self.organiser = User.objects.create_user(
            username="ana", password="right-password", is_staff=True
        )
        self.client = APIClient()

    def login(self, password, forwarded_for="203.0.113.7", **extra):
        """POST ana's credentials; `forwarded_for` is the X-Forwarded-For header, None for none."""
        if forwarded_for is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
        return self.client.post(
            "/auth/token/", {"username": "ana", "password": password}, format="json", **extra
        )

    def exhaust(self, **kwargs):
        for _ in range(LIMIT):
            self.assertEqual(self.login("guess", **kwargs).status_code, 400)

    def test_a_normal_login_gets_the_token(self):
        response = self.login("right-password")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"token": Token.objects.get(user=self.organiser).key})

    def test_failed_attempts_get_429_past_the_limit(self):
        self.exhaust()
        response = self.login("guess")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_the_right_password_is_refused_too_once_throttled(self):
        self.exhaust()
        self.assertEqual(self.login("right-password").status_code, 429)

    def test_each_client_ip_has_its_own_bucket(self):
        self.exhaust(forwarded_for="203.0.113.7")
        response = self.login("right-password", forwarded_for="198.51.100.4")
        self.assertEqual(response.status_code, 200)

    def test_a_forged_forwarded_prefix_does_not_open_a_new_bucket(self):
        # A client controls every X-Forwarded-For entry but the last, which the proxy in
        # front of Django appends: NUM_PROXIES = 1 keys on that one alone.
        for i in range(LIMIT):
            self.login("guess", forwarded_for=f"10.0.0.{i}, 203.0.113.7")
        response = self.login("guess", forwarded_for="10.0.0.99, 203.0.113.7")
        self.assertEqual(response.status_code, 429)

    def test_without_forwarded_for_the_socket_address_is_the_bucket(self):
        self.exhaust(forwarded_for=None, REMOTE_ADDR="192.0.2.1")
        same = self.login("guess", forwarded_for=None, REMOTE_ADDR="192.0.2.1")
        other = self.login("guess", forwarded_for=None, REMOTE_ADDR="192.0.2.2")
        self.assertEqual((same.status_code, other.status_code), (429, 400))

    def test_an_ipv6_client_counts_by_its_64(self):
        self.exhaust(forwarded_for="2001:db8:1:2::1")
        same_64 = self.login("guess", forwarded_for="2001:db8:1:2:ffff:ffff:ffff:ffff")
        other_64 = self.login("guess", forwarded_for="2001:db8:1:3::1")
        self.assertEqual((same_64.status_code, other_64.status_code), (429, 400))

    def test_an_ipv4_written_as_ipv6_counts_as_that_ipv4(self):
        self.exhaust(forwarded_for="::ffff:203.0.113.7")
        same = self.login("guess", forwarded_for="203.0.113.7")
        # Not one /64 for every IPv4 client.
        other = self.login("guess", forwarded_for="::ffff:198.51.100.4")
        self.assertEqual((same.status_code, other.status_code), (429, 400))

    def test_a_token_does_not_exempt_the_caller(self):
        player = User.objects.create_user(username="player", password="x")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get(user=player).key}")
        self.exhaust()
        self.assertEqual(self.login("guess").status_code, 429)

    def test_the_rest_of_the_api_is_not_throttled(self):
        Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        token = Token.objects.get(user=self.organiser).key
        self.exhaust()
        for _ in range(LIMIT + 1):
            self.assertEqual(
                self.client.get("/editions/", HTTP_X_FORWARDED_FOR="203.0.113.7").status_code, 200
            )
            self.assertEqual(
                self.client.get(
                    "/user/current/",
                    HTTP_X_FORWARDED_FOR="203.0.113.7",
                    HTTP_AUTHORIZATION=f"Token {token}",
                ).status_code,
                200,
            )
