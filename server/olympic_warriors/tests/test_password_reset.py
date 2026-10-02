import re

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from olympic_warriors.models import UserProfile
from olympic_warriors.tests.test_claims import INVALID, PRIVATE_CACHE, ClaimSetup, parts

GOOD = "violet-harbour-lantern"


@PRIVATE_CACHE
@override_settings(PUBLIC_URL="https://ow.example")
class TestPasswordReset(ClaimSetup, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
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

    def test_a_person_gets_a_link(self):
        response = self.ask("LEA@mail.example")
        self.assertEqual((response.status_code, response.data), (200, {}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["lea@mail.example"])
        uidb64, token = self.mailed_link()
        self.assertEqual(self.reset(uidb64, token).status_code, 200)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))

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
