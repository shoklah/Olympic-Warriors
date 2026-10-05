"""An invited newcomer (no Player yet): they may claim an account, reset a password, use
/account's email and password, and see can_register on /me/; photo and showcase stay for
people only."""
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import claims
from olympic_warriors.claims import (
    INACTIVE,
    NOT_A_PERSON,
    STAFF,
    can_register,
    claim_link,
    unclaimable_reason,
    unresettable_reason,
)
from olympic_warriors.models import Edition, Player, UserProfile
from olympic_warriors.tests.test_me import ME_QUERIES

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invited-tests",
        }
    }
)


@PRIVATE_CACHE
@override_settings(PUBLIC_URL="https://ow.example")
class InvitedSetup(APITestCase):
    def setUp(self):
        cache.clear()
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.newcomer = self.user("newbie", invited=True)
        self.plain = self.user("plain")
        self.player = self.user("ana")
        Player.objects.create(user=self.player, edition=self.edition, rating=5)
        self.invited_staff = self.user("boss", invited=True, is_staff=True)
        self.invited_inactive = self.user("gone", invited=True, is_active=False)

    @staticmethod
    def user(username, invited=False, **flags):
        user = User.objects.create(username=username, first_name=username.title(), **flags)
        if invited:
            UserProfile.objects.create(user=user, invited=True)
        return user

    def client_of(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=user)[0].key}")
        return client


class TestCanRegister(InvitedSetup):
    def test_a_person_or_an_invited_user(self):
        self.assertTrue(can_register(self.player))
        self.assertTrue(can_register(self.newcomer))
        self.assertFalse(can_register(self.plain))

    def test_an_uninvited_profile_does_not_count(self):
        UserProfile.objects.create(user=self.plain)

        self.assertFalse(can_register(self.plain))


class TestClaimRules(InvitedSetup):
    def test_an_invited_newcomer_is_claimable(self):
        self.assertIsNone(unclaimable_reason(self.newcomer))
        self.assertTrue(claim_link(self.newcomer).startswith("https://ow.example/claim/"))

    def test_the_other_refusals_still_apply_first(self):
        self.assertEqual(unclaimable_reason(self.invited_staff), STAFF)
        self.assertEqual(unclaimable_reason(self.invited_inactive), INACTIVE)
        self.assertEqual(unclaimable_reason(self.plain), NOT_A_PERSON)

    def test_an_invited_newcomer_may_reset_a_lost_password(self):
        self.assertIsNone(unresettable_reason(self.newcomer))
        self.assertEqual(unresettable_reason(self.plain), NOT_A_PERSON)

    def test_claiming_stamps_the_first_activation_for_an_invited_newcomer(self):
        from django.contrib.auth.tokens import default_token_generator

        token = default_token_generator.make_token(self.newcomer)

        key = claims.complete_claim(self.newcomer, token, "violet-harbour-lantern")

        self.assertTrue(key)
        self.assertIsNotNone(UserProfile.objects.get(user=self.newcomer).claimed_at)


class TestMe(InvitedSetup):
    def test_can_register_is_true_for_an_invited_newcomer_and_a_person_only(self):
        for user, expected in ((self.newcomer, True), (self.player, True), (self.plain, False)):
            with self.subTest(user=user.username):
                body = self.client_of(user).get("/me/").json()
                self.assertEqual(body["can_register"], expected)

        self.assertFalse(self.client_of(self.newcomer).get("/me/").json()["is_person"])

    def test_me_stays_at_its_query_budget(self):
        client = self.client_of(self.newcomer)

        with self.assertNumQueries(ME_QUERIES):
            client.get("/me/")


class TestAccountViews(InvitedSetup):
    def test_email_and_password_changes_are_open_to_an_invited_newcomer(self):
        self.newcomer.set_password("old-password-xyz")
        self.newcomer.save()
        client = self.client_of(self.newcomer)

        response = client.put(
            "/me/email/", {"password": "old-password-xyz", "email": "new@ow.example"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"email": "new@ow.example"})

    def test_photo_and_showcase_stay_for_people(self):
        client = self.client_of(self.newcomer)

        self.assertEqual(client.delete("/me/photo/").status_code, 404)
        self.assertEqual(client.put("/me/showcase/", {"codes": []}, format="json").status_code, 404)
