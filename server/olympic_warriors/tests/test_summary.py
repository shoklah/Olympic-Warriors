"""
Tests for the Edition model changes and the public edition summary endpoint.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from olympic_warriors.models import Edition, Orienteering, Player, Relay, Team, TeamResult
from olympic_warriors.serializer import EditionSummarySerializer


class TestEditionModel(TestCase):
    """year is unique and photos_url is optional."""

    def test_year_is_unique(self):
        Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Edition.objects.create(
                    year=2026, host="Lyon", start_date="2026-10-01", end_date="2026-10-02"
                )

    def test_photos_url_defaults_to_none(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.assertIsNone(edition.photos_url)

    def test_photos_url_is_stored(self):
        edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
            photos_url="https://drive.example.com/ow-2026",
        )
        edition.refresh_from_db()
        self.assertEqual(edition.photos_url, "https://drive.example.com/ow-2026")


class TestTeamResultsByEdition(APITestCase):
    """The by-edition results view filters through the discipline's edition."""

    def setUp(self):
        self.user = User.objects.create_user(username="orga", password="x")
        self.client.force_authenticate(user=self.user)
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.other = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        Team.objects.create(name="A", edition=self.edition)
        Team.objects.create(name="Z", edition=self.other)
        Relay.objects.create(edition=self.edition)  # one result for A
        Relay.objects.create(edition=self.other)  # one result for Z

    def test_returns_only_that_editions_results(self):
        response = self.client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([r["team_name"] for r in response.data], ["A"])

    def test_excludes_inactive_results(self):
        Team.objects.create(name="B", edition=self.edition)
        Relay.objects.create(edition=self.edition)  # a second result each for A and B
        TeamResult.objects.filter(team__name="B").update(is_active=False)

        response = self.client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        # setUp's own Relay already gave team A one active result, so this
        # edition legitimately has two active "A" results at this point;
        # what this test asserts is that team B's now-inactive result is
        # excluded.
        self.assertNotIn("B", [r["team_name"] for r in response.data])


class SummarySetup:
    """
    One 2026 edition with three teams, a revealed Relay (points 10/5/0) and a hidden
    Orienteering, plus a 2025 edition that must never leak into the 2026 summary.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
            photos_url="https://drive.example.com/ow-2026",
        )
        self.other = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.team_a = Team.objects.create(name="Aigles", edition=self.edition)
        self.team_b = Team.objects.create(name="Bisons", edition=self.edition)
        self.team_c = Team.objects.create(name="Cerfs", edition=self.edition)
        self.team_z = Team.objects.create(name="Zèbres", edition=self.other)

        ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        bob = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        old = User.objects.create(username="old", first_name="Old", last_name="Timer")
        Player.objects.create(user=ana, edition=self.edition, rating=5, team=self.team_a)
        Player.objects.create(user=bob, edition=self.edition, rating=5, team=self.team_a)
        Player.objects.create(
            user=old, edition=self.edition, rating=5, team=self.team_a, is_active=False
        )

        self.relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_a).update(points=5)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_b).update(points=10)
        TeamResult.objects.filter(discipline=self.relay, team=self.team_c).update(points=0)
        self.orienteering = Orienteering.objects.create(edition=self.edition, reveal_score=False)
        Relay.objects.create(edition=self.other, reveal_score=True)

    def summary(self):
        return EditionSummarySerializer(self.edition).data


class TestEditionSummarySerializer(SummarySetup, TestCase):

    def test_edition_fields(self):
        edition = self.summary()["edition"]
        self.assertEqual(
            edition,
            {
                "id": self.edition.id,
                "year": 2026,
                "host": "Paris",
                "start_date": "2026-09-19",
                "end_date": "2026-09-20",
                "photos_url": "https://drive.example.com/ow-2026",
            },
        )

    def test_disciplines_of_this_edition_in_id_order(self):
        disciplines = self.summary()["disciplines"]
        self.assertEqual(
            disciplines,
            [
                {"id": self.relay.id, "name": "Relay", "result_type": "PTS", "reveal_score": True},
                {
                    "id": self.orienteering.id,
                    "name": "Orienteering",
                    "result_type": "TIM",
                    "reveal_score": False,
                },
            ],
        )

    def test_inactive_discipline_excluded(self):
        self.orienteering.is_active = False
        self.orienteering.save()
        self.assertEqual([d["name"] for d in self.summary()["disciplines"]], ["Relay"])

    def test_teams_in_name_order_with_active_roster(self):
        teams = self.summary()["teams"]
        self.assertEqual([t["name"] for t in teams], ["Aigles", "Bisons", "Cerfs"])
        aigles = teams[0]
        self.assertEqual(aigles["ranking"], 2)
        self.assertEqual(aigles["total_points"], 3)
        self.assertEqual(
            [(p["first_name"], p["last_name"]) for p in aigles["players"]],
            [("Ana", "Lopez"), ("Bob", "Martin")],
        )
        self.assertEqual(teams[1]["ranking"], 1)
        self.assertEqual(teams[1]["total_points"], 5)

    def test_inactive_team_excluded(self):
        self.team_c.is_active = False
        self.team_c.save()
        self.assertEqual([t["name"] for t in self.summary()["teams"]], ["Aigles", "Bisons"])

    def test_revealed_results_carry_scores(self):
        results = [r for r in self.summary()["results"] if r["discipline"] == self.relay.id]
        by_team = {r["team"]: r for r in results}
        row = by_team[self.team_b.id]
        row.pop("id")
        self.assertEqual(
            row,
            {
                "team": self.team_b.id,
                "discipline": self.relay.id,
                "result_type": "PTS",
                "ranking": 1,
                "points": 10,
                "time": None,
                "points_difference": 0,
                "global_points": 5,
            },
        )
        self.assertEqual(by_team[self.team_a.id]["ranking"], 2)
        self.assertEqual(by_team[self.team_a.id]["global_points"], 3)
        self.assertEqual(by_team[self.team_c.id]["ranking"], 3)
        self.assertEqual(by_team[self.team_c.id]["global_points"], 2)

    def test_hidden_results_are_null(self):
        results = [
            r for r in self.summary()["results"] if r["discipline"] == self.orienteering.id
        ]
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result["result_type"], "TIM")
            for field in ("ranking", "points", "time", "points_difference", "global_points"):
                self.assertIsNone(result[field], field)

    def test_inactive_result_excluded(self):
        TeamResult.objects.filter(discipline=self.relay, team=self.team_c).update(is_active=False)
        results = [r for r in self.summary()["results"] if r["discipline"] == self.relay.id]
        self.assertEqual(
            sorted(r["team"] for r in results), sorted([self.team_a.id, self.team_b.id])
        )

    def test_other_edition_never_leaks(self):
        data = self.summary()
        self.assertNotIn("Zèbres", [t["name"] for t in data["teams"]])
        self.assertEqual(len(data["results"]), 6)

    def test_missing_score_in_revealed_discipline_is_null(self):
        TeamResult.objects.filter(discipline=self.relay, team=self.team_c).update(points=None)

        results = self.summary()["results"]  # must not raise

        results = [r for r in results if r["discipline"] == self.relay.id]
        by_team = {r["team"]: r for r in results}
        for field in ("ranking", "points", "time", "points_difference", "global_points"):
            self.assertIsNone(by_team[self.team_c.id][field], field)

        self.assertEqual(by_team[self.team_b.id]["ranking"], 1)
        self.assertEqual(by_team[self.team_b.id]["global_points"], 5)
        self.assertEqual(by_team[self.team_a.id]["ranking"], 2)
        self.assertEqual(by_team[self.team_a.id]["global_points"], 3)


class TestRankingWithoutScore(TestCase):
    """TeamResult.ranking returns 0, never crashes, when the score for its type is NULL."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.team = Team.objects.create(name="Solo", edition=self.edition)

    def test_points_discipline_without_points(self):
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        result = TeamResult.objects.get(discipline=relay, team=self.team)
        result.points = None
        self.assertEqual(result.ranking, 0)
        self.assertEqual(result.global_points, 0)

    def test_time_discipline_without_time(self):
        orienteering = Orienteering.objects.create(edition=self.edition, reveal_score=True)
        result = TeamResult.objects.get(discipline=orienteering, team=self.team)
        result.time = None
        self.assertEqual(result.ranking, 0)


class TestEditionSummaryEndpoint(APITestCase):
    """
    GET /edition/year/<year>/summary/ is public and 404s on unknown or inactive years.
    APITestCase's self.client already carries no credentials by default.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        Team.objects.create(name="Aigles", edition=self.edition)
        Relay.objects.create(edition=self.edition, reveal_score=True)

    def test_public_without_token(self):
        response = self.client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"edition", "disciplines", "teams", "results"})
        self.assertEqual(response.data["edition"]["year"], 2026)
        self.assertEqual(response.data["teams"][0]["name"], "Aigles")
        self.assertEqual(response.data["results"][0]["ranking"], 1)

    def test_unknown_year_is_404(self):
        response = self.client.get("/edition/year/1999/summary/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Edition not found"})

    def test_inactive_edition_is_404(self):
        self.edition.is_active = False
        self.edition.save()
        response = self.client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 404)
