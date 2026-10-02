"""A deactivated player's name is masked in every public payload (spec 2026-10-02)."""

import re

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.anonymity import shown_names
from olympic_warriors.models import Badge, BadgeProgress, Edition, Player, Team, UserProfile
from olympic_warriors.tests.test_permissions import PUBLIC, routes
from olympic_warriors.tests.test_profiles import DisciplinesSetup


class AnonymitySetup:
    def setUp(self):
        self.edition = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.team = Team.objects.create(name="MxM", edition=self.edition)
        self.lea = User.objects.create_user("leamartin", first_name="Léa", last_name="Martin")
        Player.objects.create(user=self.lea, edition=self.edition, team=self.team, rating=5)


class TestShownNames(AnonymitySetup, APITestCase):
    def test_real_names_without_a_profile_or_a_flag(self):
        self.assertEqual(shown_names(self.lea), ("Léa", "Martin"))
        UserProfile.objects.create(user=self.lea)
        self.assertEqual(shown_names(User.objects.get(pk=self.lea.pk)), ("Léa", "Martin"))

    def test_masked_names_when_anonymized(self):
        UserProfile.objects.create(user=self.lea, anonymized=True)
        self.assertEqual(shown_names(User.objects.get(pk=self.lea.pk)), ("Joueur", "anonyme"))


class TestPublicPayloads(AnonymitySetup, APITestCase):
    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.lea, anonymized=True)

    def assertMasked(self, response):
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertNotIn("Léa", text)
        self.assertNotIn("Martin", text)
        self.assertIn("anonyme", text)

    def test_summary_roster(self):
        self.assertMasked(self.client.get("/edition/year/2024/summary/"))

    def test_leaderboard(self):
        self.assertMasked(self.client.get("/profiles/"))

    def test_profile(self):
        self.assertMasked(self.client.get(f"/profile/{self.lea.pk}/"))


class TestAllTimeAndPartners(DisciplinesSetup, TestCase):
    """Bob is anonymized: his all-time row and the partner entries naming him are masked,
    while everyone else keeps their names."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.ana = User.objects.get(first_name="Ana")
        self.bob = User.objects.get(first_name="Bob")
        UserProfile.objects.create(user=self.bob, anonymized=True)
        Badge.objects.create(
            user=self.ana, code=Badge.Codes.COMRADES, edition=self.y2025, partner=self.bob
        )
        BadgeProgress.objects.create(
            user=self.ana, code=Badge.Codes.COMRADES, value=2, best=2, partner=self.bob
        )

    def test_discipline_all_time_row(self):
        data = self.client.get(f"/discipline/{self.relay2024.id}/all-time/").json()

        names = {(row["first_name"], row["last_name"]) for row in data["players"]}
        self.assertIn(("Joueur", "anonyme"), names)
        self.assertNotIn("Bob", {row["first_name"] for row in data["players"]})
        self.assertIn("Ana", {row["first_name"] for row in data["players"]})
        self.assertNotIn("Bob", self.client.get(f"/discipline/{self.relay2024.id}/all-time/").content.decode())

    def test_badge_and_progress_partner_on_a_profile(self):
        response = self.client.get(f"/profile/{self.ana.pk}/")
        data = response.json()

        comrades = next(b for b in data["badges"] if b["code"] == Badge.Codes.COMRADES)
        self.assertEqual(
            (comrades["partner"]["first_name"], comrades["partner"]["last_name"]),
            ("Joueur", "anonyme"),
        )
        progress = next(p for p in data["progress"] if p["code"] == Badge.Codes.COMRADES)
        self.assertEqual(
            (progress["partner"]["first_name"], progress["partner"]["last_name"]),
            ("Joueur", "anonyme"),
        )
        self.assertNotIn("Bob", response.content.decode())

    def test_bob_own_profile_and_leaderboard_row_are_masked(self):
        profile = self.client.get(f"/profile/{self.bob.pk}/").json()
        rows = self.client.get("/profiles/").json()

        self.assertEqual((profile["first_name"], profile["last_name"]), ("Joueur", "anonyme"))
        self.assertNotIn("Bob", {row["first_name"] for row in rows})
        self.assertIn("Ana", {row["first_name"] for row in rows})


class TestNoPublicRouteLeaksAnAnonymizedPerson(DisciplinesSetup, TestCase):
    """The guard: walk every public route of urls.py and look for the anonymized person's
    real names, username and email in the 200 bodies. A route that serialises a person
    without shown_names() fails here, whatever its shape."""

    LEAKS = ("Zyxwv", "Qpmlk", "zyxwvqpmlk", "zyxwv@mail.example")
    # Public routes that take no ids of this world: the schema, the login, the link pages.
    SKIPPED = ("api/", "auth/", "claim/", "password-reset")

    def setUp(self):
        super().setUp()
        self.bob = User.objects.get(first_name="Bob")
        self.bob.first_name, self.bob.last_name = "Zyxwv", "Qpmlk"
        self.bob.username, self.bob.email = "zyxwvqpmlk", "zyxwv@mail.example"
        self.bob.save()
        UserProfile.objects.create(user=self.bob, anonymized=True)
        ana = User.objects.get(first_name="Ana")
        Badge.objects.create(user=ana, code=Badge.Codes.COMRADES, edition=self.y2025, partner=self.bob)
        BadgeProgress.objects.create(user=ana, code=Badge.Codes.COMRADES, value=2, best=2, partner=self.bob)
        self.ids = {
            "edition_id": self.y2024.id,
            "year": self.y2024.year,
            "discipline_id": self.relay2024.id,
            "user_id": self.bob.pk,
        }

    def url(self, route):
        return "/" + re.sub(r"<(?:\w+:)?(\w+)>", lambda m: str(self.ids[m.group(1)]), route)

    def test_every_public_route_hides_the_real_person(self):
        walked = 0
        for route, _, methods, _ in routes():
            if route not in PUBLIC or route.startswith(self.SKIPPED):
                continue
            walked += 1
            for owner in (self.bob.pk, User.objects.get(first_name="Ana").pk):
                self.ids["user_id"] = owner
                response = APIClient().get(self.url(route))
                with self.subTest(route=route, user=owner):
                    self.assertEqual(response.status_code, 200)
                    text = response.content.decode()
                    for leak in self.LEAKS:
                        self.assertNotIn(leak, text)
        self.assertGreaterEqual(walked, 8)
