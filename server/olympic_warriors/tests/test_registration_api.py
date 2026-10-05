"""GET, PUT and DELETE /registration/: the caller's registration for the latest edition."""
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Edition, LateRegistration, Player, PlayerRating, RegistrationSkill, Team, UserProfile,
)
from olympic_warriors.throttling import RegistrationRateThrottle

LIMIT = RegistrationRateThrottle().num_requests
NOT_A_PERSON = {"error": "not_a_person"}

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "registration-tests",
        }
    }
)


def answer(**changes):
    data = {
        "ratings": {"AAA": 6, "BBB": 6},
        "global_level": 8,
        "sport_frequency": "two_hours",
        "sports": [{"sport": "Judo", "level": "amateur"}],
        "team_with": "Avec Bob",
        "team_avoid": "Pas Carl",
        "dietary_restrictions": "",
        "attendance_confirmed": True,
    }
    data.update(changes)
    return data


@PRIVATE_CACHE
class RegistrationSetup(APITestCase):
    def setUp(self):
        cache.clear()
        self.old = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.edition = Edition.objects.create(
            year=2027, host="Lyon", start_date=date(2027, 9, 18), end_date=date(2027, 9, 19),
            registration_opens=date(2020, 1, 1), registration_closes=date(2999, 1, 1),
        )
        for order, identifier in enumerate(("AAA", "BBB")):
            RegistrationSkill.objects.create(
                edition=self.edition, name_fr=identifier, name_en=identifier,
                identifier=identifier, weight=1, order=order,
            )
        self.ana = self.user("ana", email="ana@example.com")  # a person of 2026
        Player.objects.create(user=self.ana, edition=self.old, rating=5, sport_frequency="hour")
        self.newbie = self.user("newbie", email="newbie@olympicwarriors.com")
        UserProfile.objects.create(user=self.newbie, invited=True)
        self.plain = self.user("plain", email="plain@example.com")

    @staticmethod
    def user(username, **kw):
        return User.objects.create(username=username, first_name=username.title(), **kw)

    def client_of(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=user)[0].key}"
        )
        return client

    def close(self):
        Edition.objects.filter(pk=self.edition.pk).update(registration_closes=date(2020, 1, 2))


class TestAccess(RegistrationSetup):
    def test_a_visitor_is_refused(self):
        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)("/registration/").status_code, 401)

    def test_someone_who_cannot_register_gets_404(self):
        client = self.client_of(self.plain)

        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(client, method)("/registration/")
                self.assertEqual((response.status_code, response.json()), (404, NOT_A_PERSON))

    def test_no_edition_at_all(self):
        UserProfile.objects.filter(user=self.newbie).update(invited=True)
        Edition.objects.all().delete()  # ana, a person of 2026 only, would stop being one

        response = self.client_of(self.newbie).get("/registration/")

        self.assertEqual((response.status_code, response.json()), (404, {"error": "no_edition"}))


class TestGet(RegistrationSetup):
    def test_a_person_gets_the_form_of_the_latest_edition(self):
        body = self.client_of(self.ana).get("/registration/").json()

        self.assertEqual(body["edition"]["year"], 2027)
        self.assertEqual(body["state"], {"is_open": True, "reason": ""})
        self.assertEqual([s["identifier"] for s in body["skills"]], ["AAA", "BBB"])
        self.assertEqual(body["email"], {"value": "ana@example.com", "editable": False})
        self.assertIsNone(body["registration"])
        self.assertEqual(body["suggested"]["year"], 2026)
        self.assertEqual(body["suggested"]["sport_frequency"], "hour")

    def test_an_invited_newcomer_gets_it_with_an_editable_email(self):
        body = self.client_of(self.newbie).get("/registration/").json()

        self.assertEqual(body["email"], {"value": "", "editable": True})
        self.assertIsNone(body["suggested"])

    def test_a_closed_registration_still_answers_with_its_reason(self):
        self.close()

        response = self.client_of(self.ana).get("/registration/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], {"is_open": False, "reason": "closed"})

    def test_a_late_pass_is_reported(self):
        self.close()
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        state = self.client_of(self.ana).get("/registration/").json()["state"]

        self.assertEqual(state, {"is_open": True, "reason": "late_pass"})

    def test_no_store(self):
        response = self.client_of(self.ana).get("/registration/")

        self.assertIn("no-store", response["Cache-Control"])


class TestPut(RegistrationSetup):
    def put(self, user=None, **changes):
        return self.client_of(user or self.ana).put("/registration/", answer(**changes), format="json")

    def test_registers_and_returns_the_form_with_the_saved_answers(self):
        response = self.put()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["registration"]["registered"])
        self.assertEqual(body["registration"]["ratings"], {"AAA": 6, "BBB": 6})
        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertEqual(player.rating, 8)
        self.assertEqual(player.global_level, 8)
        self.assertEqual(PlayerRating.objects.filter(player=player).count(), 2)
        self.assertEqual(player.playersport_set.count(), 1)

    def test_an_edit_keeps_the_team(self):
        self.put()
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(user=self.ana, edition=self.edition).update(team=team)

        self.put(team_with="Plutôt seule")

        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertEqual((player.team, player.team_with), (team, "Plutôt seule"))

    def test_an_invited_newcomer_becomes_a_person(self):
        self.assertFalse(self.client_of(self.newbie).get("/me/").json()["is_person"])

        response = self.put(user=self.newbie, email="Real@Example.com")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client_of(self.newbie).get("/me/").json()["is_person"])
        self.newbie.refresh_from_db()
        self.assertEqual(self.newbie.email, "real@example.com")

    def test_a_newcomer_without_a_usable_email_must_give_one(self):
        response = self.put(user=self.newbie)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"errors": ["no_email"]})
        self.assertFalse(Player.objects.filter(user=self.newbie).exists())

    def test_a_usable_email_is_never_overwritten_by_the_form(self):
        self.put(email="hijack@example.com")

        self.ana.refresh_from_db()
        self.assertEqual(self.ana.email, "ana@example.com")

    def test_refusals_list_every_code(self):
        response = self.put(ratings={}, global_level=0, attendance_confirmed=False)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"errors": ["missing_rating", "invalid_global_level", "attendance_required"]},
        )
        self.assertFalse(Player.objects.filter(user=self.ana, edition=self.edition).exists())

    def test_an_unreadable_body_is_a_400_not_a_500(self):
        response = self.client_of(self.ana).put(
            "/registration/", "{not json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_closed_registration_answers_409_with_its_reason(self):
        self.close()

        response = self.put()

        self.assertEqual((response.status_code, response.json()), (409, {"error": "closed"}))
        self.assertFalse(Player.objects.filter(user=self.ana, edition=self.edition).exists())

    def test_not_configured_and_not_yet_open(self):
        Edition.objects.filter(pk=self.edition.pk).update(registration_opens=date(2999, 1, 1))
        self.assertEqual(self.put().json(), {"error": "not_yet_open"})
        RegistrationSkill.objects.all().delete()
        self.assertEqual(self.put().json(), {"error": "not_configured"})

    def test_a_late_pass_opens_a_closed_registration(self):
        self.close()
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        self.assertEqual(self.put().status_code, 200)
        self.assertEqual(self.put(user=self.newbie, email="n@example.com").status_code, 409)

    def test_an_address_of_another_active_account_is_refused(self):
        self.user("other", email="taken@example.com")

        response = self.put(user=self.newbie, email="Taken@Example.com")

        self.assertEqual((response.status_code, response.json()), (400, {"errors": ["email_taken"]}))

    def test_a_person_removed_by_an_organiser_cannot_register_again(self):
        Player.objects.create(user=self.ana, edition=self.edition, rating=5, is_active=False)

        response = self.put()

        self.assertEqual(
            (response.status_code, response.json()), (409, {"error": "removed_by_organiser"})
        )
        self.assertFalse(Player.objects.get(user=self.ana, edition=self.edition).is_active)

    def test_a_late_pass_lets_a_removed_person_back(self):
        Player.objects.create(user=self.ana, edition=self.edition, rating=5, is_active=False)
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        self.assertEqual(self.put().status_code, 200)
        self.assertTrue(Player.objects.get(user=self.ana, edition=self.edition).is_active)

    def test_every_put_counts_against_the_throttle(self):
        for _ in range(LIMIT):
            self.put(ratings={})  # refused, still counted

        response = self.put()

        self.assertEqual(response.status_code, 429)
        # A GET is never limited.
        self.assertEqual(self.client_of(self.ana).get("/registration/").status_code, 200)


class TestDelete(RegistrationSetup):
    def test_withdrawing_keeps_the_answers_and_a_new_put_restores_them(self):
        client = self.client_of(self.ana)
        client.put("/registration/", answer(), format="json")

        self.assertEqual(client.delete("/registration/").status_code, 204)

        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertFalse(player.is_active)
        body = client.get("/registration/").json()
        self.assertFalse(body["registration"]["registered"])
        self.assertEqual(body["registration"]["team_with"], "Avec Bob")
        self.assertEqual(body["registration"]["team_avoid"], "Pas Carl")
        client.put("/registration/", answer(), format="json")
        player.refresh_from_db()
        self.assertTrue(player.is_active)

    def test_a_player_in_a_team_cannot_withdraw(self):
        client = self.client_of(self.ana)
        client.put("/registration/", answer(), format="json")
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(user=self.ana, edition=self.edition).update(team=team)

        response = client.delete("/registration/")

        self.assertEqual((response.status_code, response.json()), (409, {"error": "has_team"}))
        self.assertTrue(Player.objects.get(user=self.ana, edition=self.edition).is_active)

    def test_withdrawing_without_a_registration_is_a_no_op(self):
        self.assertEqual(self.client_of(self.ana).delete("/registration/").status_code, 204)

    def test_withdrawing_after_the_close_is_refused_without_a_pass(self):
        client = self.client_of(self.ana)
        client.put("/registration/", answer(), format="json")
        self.close()

        response = client.delete("/registration/")

        self.assertEqual((response.status_code, response.json()), (409, {"error": "closed"}))
        self.assertTrue(Player.objects.get(user=self.ana, edition=self.edition).is_active)

        LateRegistration.objects.create(user=self.ana, edition=self.edition)
        self.assertEqual(client.delete("/registration/").status_code, 204)
