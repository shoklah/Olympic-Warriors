import re
import threading
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from olympic_warriors import password_reset
from olympic_warriors.throttling import LoginRateThrottle
from olympic_warriors.models import UserProfile
from olympic_warriors.tests.test_claims import INVALID, PRIVATE_CACHE, ClaimSetup, parts

REAL_DISPATCH = password_reset.dispatch
GOOD = "violet-harbour-lantern"


@PRIVATE_CACHE
@override_settings(PUBLIC_URL="https://ow.example")
class TestPasswordReset(ClaimSetup, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # Mail leaves on a thread in production; run it inline so the outbox is filled.
        patcher = mock.patch(
            "olympic_warriors.password_reset.dispatch", lambda func, *args: func(*args)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for user, email in (
            (self.lea, "lea@mail.example"),
            (self.staff, "ana@mail.example"),
            (self.gone, "gone@mail.example"),
            (self.stranger, "sam@mail.example"),
        ):
            user.email = email
            user.save(update_fields=["email"])

    def ask(self, email):
        return self.client.post("/password-reset/", {"email": email}, format="json")

    def reset(self, uidb64, token, password=GOOD):
        return self.client.post(
            f"/password-reset/{uidb64}/{token}/", {"password": password}, format="json"
        )

    def mailed_link(self):
        link = re.search(r"https://ow\.example/reset/([\w-]+)/([\w-]+)", mail.outbox[-1].body)
        self.assertIsNotNone(link)
        return link.groups()

    def logged(self, email):
        """The INFO+ lines `send_reset(email)` logs, as one string (never the address)."""
        with self.assertLogs("olympic_warriors.password_reset", "INFO") as logs:
            self.ask(email)
        text = "\n".join(logs.output)
        if isinstance(email, str) and email:
            self.assertNotIn(email.lower(), text.lower())
        return text

    def test_every_outcome_logs_why_without_the_address(self):
        self.stranger.email = "twin@mail.example"
        self.stranger.save(update_fields=["email"])
        self.benched.email = "twin@mail.example"
        self.benched.save(update_fields=["email"])
        cases = (
            ("", "no usable email"),
            (5, "no usable email"),
            ("nobody@mail.example", "no account has that address"),
            ("twin@mail.example", "several accounts share that address"),
            ("ana@mail.example", f"user {self.staff.pk} is not claimable (staff)"),
            ("gone@mail.example", f"user {self.gone.pk} is not claimable (inactive)"),
            ("sam@mail.example", "no account has that address"),
        )
        for email, expected in cases:
            with self.subTest(email=email):
                cache.clear()
                if email == "sam@mail.example":
                    # sam's address was reused above: this one is the not-a-person branch
                    self.stranger.email = "sam@mail.example"
                    self.stranger.save(update_fields=["email"])
                    expected = f"user {self.stranger.pk} is not claimable (not_a_person)"
                self.assertIn(expected, self.logged(email))

    def test_a_sent_mail_logs_the_hand_over_to_the_smtp_server(self):
        text = self.logged("lea@mail.example")
        self.assertIn(f"mail for user {self.lea.pk} queued", text)
        self.assertIn(f"mail for user {self.lea.pk} accepted by the mail server", text)

    def test_a_person_gets_a_link(self):
        response = self.ask("LEA@mail.example")
        self.assertEqual((response.status_code, response.data), (200, {}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["lea@mail.example"])
        uidb64, token = self.mailed_link()
        self.assertEqual(self.reset(uidb64, token).status_code, 200)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))

    def test_the_mail_states_the_link_lifetime_from_the_setting(self):
        for seconds, words in ((7 * 86400, "valable 7 jours"), (86400, "valable 1 jour"), (3600, "valable 1 jour")):
            with self.subTest(seconds=seconds), override_settings(PASSWORD_RESET_TIMEOUT=seconds):
                mail.outbox.clear()
                cache.clear()
                self.ask("lea@mail.example")
                self.assertIn(f"({words})", mail.outbox[0].body)

    def test_everyone_else_gets_the_same_answer_and_no_mail(self):
        # Not about the throttle: each attempt gets a fresh per-IP budget (cache cleared),
        # since 7 calls from one test client would pass the 5/min login limit.
        for email in (
            "nobody@mail.example", "ana@mail.example", "gone@mail.example",
            "sam@mail.example", "", None, 5,
        ):
            with self.subTest(email=email):
                cache.clear()
                response = self.ask(email)
                self.assertEqual((response.status_code, response.data), (200, {}))
        self.assertEqual(mail.outbox, [])

    def test_two_users_sharing_an_email_get_nothing(self):
        self.stranger.email = "lea@mail.example"
        self.stranger.save(update_fields=["email"])
        self.ask("lea@mail.example")
        self.assertEqual(mail.outbox, [])

    @override_settings(PUBLIC_URL="")
    def test_no_public_url_no_mail_and_still_200(self):
        self.assertEqual(self.ask("lea@mail.example").status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_the_mail_leaves_on_a_thread_after_the_request(self):
        started, release = threading.Event(), threading.Event()
        sent = []

        def slow_send(*args, **kwargs):
            started.set()
            release.wait(5)
            sent.append(args)

        with mock.patch("olympic_warriors.password_reset.dispatch", REAL_DISPATCH), \
                mock.patch("olympic_warriors.password_reset.send_mail", slow_send):
            before = set(threading.enumerate())
            self.assertTrue(password_reset.send_reset("lea@mail.example"))
            self.assertEqual(sent, [])  # returned before the send finished
            self.assertTrue(started.wait(5))
            release.set()
            for thread in set(threading.enumerate()) - before:
                thread.join(5)
        self.assertEqual(len(sent), 1)

    def test_a_failing_send_is_logged_not_raised(self):
        with self.assertLogs("olympic_warriors.password_reset", "ERROR"):
            before = set(threading.enumerate())
            with mock.patch("olympic_warriors.password_reset.dispatch", REAL_DISPATCH), \
                    mock.patch("olympic_warriors.password_reset.send_mail", side_effect=OSError):
                password_reset.send_reset("lea@mail.example")
                for thread in set(threading.enumerate()) - before:
                    thread.join(5)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST=""
    )
    def test_smtp_backend_without_a_host_logs_and_sends_nothing(self):
        with self.assertLogs("olympic_warriors.password_reset", "ERROR") as logs:
            self.assertEqual(self.ask("lea@mail.example").status_code, 200)
        self.assertIn("EMAIL_HOST is not set", logs.output[0])
        self.assertEqual(mail.outbox, [])

    def test_a_reset_request_draws_on_the_per_ip_login_bucket(self):
        limit = LoginRateThrottle().num_requests
        for number in range(limit):
            self.assertEqual(self.ask(f"nobody{number}@mail.example").status_code, 200)
        self.assertEqual(self.ask("another@mail.example").status_code, 429)

    def test_the_address_is_throttled(self):
        for _ in range(3):
            self.assertEqual(self.ask("lea@mail.example").status_code, 200)
        self.assertEqual(self.ask("lea@mail.example").status_code, 429)

    def test_the_reset_link_page_contract(self):
        uidb64, token = parts(self.lea)
        self.assertEqual(self.client.get(f"/password-reset/{uidb64}/{token}/").status_code, 200)
        dead = self.client.get("/password-reset/x/y/")
        self.assertEqual((dead.status_code, dead.data), (404, INVALID))

    def test_a_reset_keeps_the_first_claimed_at(self):
        self.assertEqual(self.reset(*parts(self.lea)).status_code, 200)
        first = UserProfile.objects.get(user=self.lea).claimed_at
        self.assertIsNotNone(first)
        self.lea.refresh_from_db()  # the first reset changed the hash the token is made from
        second = self.reset(*parts(self.lea), password="another-long-phrase-7")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(UserProfile.objects.get(user=self.lea).claimed_at, first)

    def test_a_link_dies_when_its_user_stops_being_claimable(self):
        for change in ({"is_staff": True}, {"is_active": False}):
            with self.subTest(change=change):
                uidb64, token = parts(self.lea)
                for key, value in change.items():
                    setattr(self.lea, key, value)
                self.lea.save()
                for response in (
                    self.client.get(f"/password-reset/{uidb64}/{token}/"),
                    self.reset(uidb64, token),
                ):
                    self.assertEqual((response.status_code, response.data), (404, INVALID))
                self.lea.is_staff = False
                self.lea.is_active = True
                self.lea.save()
