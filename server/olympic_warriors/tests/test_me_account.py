from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from olympic_warriors.models import UserProfile
from olympic_warriors.tests.test_me import MeSetup, NOT_A_PERSON, PRIVATE_CACHE

GOOD = "old-password-x1"


@PRIVATE_CACHE
class TestAccountEndpoints(MeSetup, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.login(self.lea)

    def test_me_carries_the_email(self):
        self.assertEqual(self.me()["email"], "leamartin@mail.example")

    def test_email_change(self):
        r = self.client.put("/me/email/", {"password": GOOD, "email": "New@Mail.example"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.lea.refresh_from_db()
        self.assertEqual(self.lea.email, "new@mail.example")

    def test_email_change_refusals(self):
        r = self.client.put("/me/email/", {"password": "wrong", "email": "a@b.co"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "wrong_password"}))
        r = self.client.put("/me/email/", {"password": GOOD, "email": "nope"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "invalid_email"}))

    def test_password_change_returns_a_new_token(self):
        old = Token.objects.get(user=self.lea).key
        r = self.client.put(
            "/me/password/", {"current": GOOD, "new": "a-brand-new-pass-77"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["token"], old)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old}")
        self.assertEqual(self.client.get("/me/").status_code, 401)

    def test_password_change_refusals(self):
        r = self.client.put("/me/password/", {"current": "wrong", "new": "a-brand-new-pass-77"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "wrong_password"}))
        r = self.client.put("/me/password/", {"current": GOOD, "new": "short"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password_too_short", r.data["errors"])

    def test_deactivate(self):
        r = self.client.post("/me/deactivate/", {"password": GOOD}, format="json")
        self.assertEqual(r.status_code, 204)
        self.lea.refresh_from_db()
        self.assertFalse(self.lea.is_active)
        self.assertTrue(UserProfile.objects.get(user=self.lea).anonymized)
        self.assertEqual(self.client.get("/me/").status_code, 401)  # token gone

    def test_deactivate_needs_the_password(self):
        r = self.client.post("/me/deactivate/", {"password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.is_active)

    def test_not_for_non_persons(self):
        # Olga is an organiser who never played, Bea a user whose only player row is inactive.
        for user in (self.olga, self.bea):
            self.login(user)
            for method, path in (("put", "/me/email/"), ("put", "/me/password/"), ("post", "/me/deactivate/")):
                r = getattr(self.client, method)(path, {}, format="json")
                self.assertEqual((r.status_code, r.data), (404, NOT_A_PERSON), (user.username, path))

    def test_an_organiser_who_plays_changes_their_email(self):
        self.login(self.chloe)
        r = self.client.put("/me/email/", {"password": GOOD, "email": "Chloe@New.example"}, format="json")
        self.assertEqual((r.status_code, r.data), (200, {"email": "chloe@new.example"}))
        self.chloe.refresh_from_db()
        self.assertEqual(self.chloe.email, "chloe@new.example")

    def test_an_organiser_who_plays_changes_their_password(self):
        self.login(self.chloe)
        old = Token.objects.get(user=self.chloe).key
        r = self.client.put(
            "/me/password/", {"current": GOOD, "new": "a-brand-new-pass-77"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["token"], old)
        self.chloe.refresh_from_db()
        self.assertTrue(self.chloe.check_password("a-brand-new-pass-77"))
        self.assertTrue(self.chloe.is_staff)
        # The old session is over, and the new token is still an organiser's.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old}")
        self.assertEqual(self.client.get("/me/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        me = self.client.get("/me/")
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data["is_staff"])

    def test_an_organiser_cannot_delete_their_account(self):
        self.login(self.chloe)
        r = self.client.post("/me/deactivate/", {"password": GOOD}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "organiser_cannot_deactivate"}))
        self.chloe.refresh_from_db()
        self.assertTrue(self.chloe.is_active)
        self.assertTrue(self.chloe.check_password(GOOD))
        self.assertFalse(UserProfile.objects.filter(user=self.chloe, anonymized=True).exists())
        self.assertEqual(self.client.get("/me/").status_code, 200)  # token kept

    def test_the_organiser_refusal_comes_before_the_password_check(self):
        # Same answer whatever the password, so the refusal tells nothing about it.
        self.login(self.chloe)
        r = self.client.post("/me/deactivate/", {"password": "wrong"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "organiser_cannot_deactivate"}))

    def test_a_superuser_who_plays_cannot_delete_their_account(self):
        self.lea.is_superuser = True
        self.lea.save(update_fields=["is_superuser"])
        r = self.client.post("/me/deactivate/", {"password": GOOD}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "organiser_cannot_deactivate"}))
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.is_active)

    def test_the_password_check_is_throttled(self):
        for _ in range(10):
            self.client.put("/me/email/", {"password": "wrong", "email": "a@b.co"}, format="json")
        r = self.client.put("/me/email/", {"password": GOOD, "email": "a@b.co"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_a_deactivated_account_cannot_log_in_and_stays_on_the_public_profile(self):
        self.client.post("/me/deactivate/", {"password": GOOD}, format="json")
        self.client.credentials()
        r = self.client.post(
            "/auth/token/", {"username": "leamartin", "password": GOOD}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        r = self.client.get(f"/profile/{self.lea.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Léa", r.content.decode())
        self.assertNotIn("Martin", r.content.decode())

