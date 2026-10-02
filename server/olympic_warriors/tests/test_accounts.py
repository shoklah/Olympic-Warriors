"""
What a logged-in person does to their own account (olympic_warriors/accounts.py): proving
the current password, changing email or password, deactivating; and the two throttles
the account endpoints use.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from rest_framework.parsers import JSONParser

from olympic_warriors import accounts
from olympic_warriors.avatars import store_photo
from olympic_warriors.models import Edition, Player, Team, UserProfile
from olympic_warriors.throttling import ResetEmailRateThrottle

from .test_avatars import MediaRootTestCase, encode, picture, upload


class AccountsTests(MediaRootTestCase):
    def setUp(self):
        super().setUp()
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        team = Team.objects.create(name="MxM", edition=edition)
        self.user = User.objects.create_user(
            "leamartin", email="lea@mail.example", password="old-password-x1",
            first_name="Léa", last_name="Martin",
        )
        Player.objects.create(user=self.user, edition=edition, team=team, rating=5)

    def test_check_password(self):
        self.assertTrue(accounts.password_ok(self.user, "old-password-x1"))
        self.assertFalse(accounts.password_ok(self.user, "nope"))
        self.assertFalse(accounts.password_ok(self.user, None))

    def test_change_email_normalises_and_validates(self):
        accounts.change_email(self.user, "  New@Mail.Example ")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@mail.example")
        with self.assertRaises(ValidationError):
            accounts.change_email(self.user, "not-an-email")
        with self.assertRaises(ValidationError):
            accounts.change_email(self.user, None)

    def test_change_password_rotates_the_token(self):
        old = Token.objects.get(user=self.user).key
        key = accounts.change_password(self.user, "a-brand-new-pass-77")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-brand-new-pass-77"))
        self.assertNotEqual(key, old)
        self.assertFalse(Token.objects.filter(key=old).exists())

    def test_change_password_runs_the_validators(self):
        with self.assertRaises(ValidationError):
            accounts.change_password(self.user, "short")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-password-x1"))

    def test_deactivate_without_a_profile_row(self):
        accounts.deactivate(self.user)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(UserProfile.objects.get(user=self.user).anonymized)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_deactivate(self):
        profile = UserProfile.objects.create(user=self.user, showcase=["champion"])
        accounts.deactivate(self.user)
        self.user.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(profile.anonymized)
        self.assertEqual(profile.showcase, [])
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertTrue(Player.objects.get(user=self.user).is_active)  # history stays

    def test_deactivate_removes_the_photo_files_after_commit(self):
        profile = UserProfile.objects.create(user=self.user, showcase=["champion"])
        store_photo(profile, upload(encode(picture(), "JPEG")))
        self.assertEqual(len(self.avatar_files()), 2)

        with self.captureOnCommitCallbacks(execute=True):
            accounts.deactivate(self.user)

        profile.refresh_from_db()
        self.assertFalse(profile.photo)
        self.assertFalse(profile.photo_small)
        self.assertTrue(profile.anonymized)
        self.assertEqual(profile.showcase, [])
        self.assertEqual(self.avatar_files(), [])


class ResetEmailThrottleTests(MediaRootTestCase):
    def key(self, body):
        request = APIRequestFactory().post("/x/", body, format="json")
        return ResetEmailRateThrottle().get_cache_key(
            Request(request, parsers=[JSONParser()]), None
        )

    def test_usable_email_gives_a_lowercased_key(self):
        key = self.key({"email": "  Lea@Mail.Example "})
        self.assertIn("lea@mail.example", key)

    def test_unusable_bodies_are_not_counted(self):
        for body in ({}, {"email": 3}, {"email": "   "}, {"email": None}, ["a"]):
            self.assertIsNone(self.key(body), body)
