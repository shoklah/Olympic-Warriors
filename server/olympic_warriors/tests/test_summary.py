"""
Tests for the Edition model changes and the public edition summary endpoint.
"""

import importlib
import re

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Crossfit,
    Darts,
    Discipline,
    Edition,
    Game,
    Orienteering,
    Petanque,
    Player,
    Relay,
    Team,
    TeamResult,
    TeamSportRound,
)
from olympic_warriors.models.Edition import latest_edition
from olympic_warriors.serializer import EditionSummarySerializer

# Queries of one summary: disciplines, teams, players prefetch, the three of the
# standings, results, rounds, games. Pin it so a per-row fan-out cannot come back.
SUMMARY_QUERIES = 9


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


class ScheduleSetup(SummarySetup):
    """SummarySetup plus a revealed Darts schedule and a hidden Petanque game."""

    def setUp(self):
        super().setUp()
        # Team sport with a schedule: Darts, revealed, two rounds, three games.
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.darts_r1 = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.darts_r2 = TeamSportRound.objects.create(discipline=self.darts, order=1)
        self.g1 = Game.objects.create(
            discipline=self.darts, round=self.darts_r1, team1=self.team_b, score1=12,
            team2=self.team_a, score2=9, referees=self.team_c, edition=self.edition,
            is_played=True,
        )
        self.g2 = Game.objects.create(
            discipline=self.darts, round=self.darts_r1, team1=self.team_c, score1=0,
            team2=self.team_b, score2=0, referees=self.team_a, edition=self.edition,
        )
        self.g3 = Game.objects.create(
            discipline=self.darts, round=self.darts_r2, team1=self.team_a, score1=7,
            team2=self.team_c, score2=7, referees=self.team_b, edition=self.edition,
            is_played=True,
        )
        # Hidden team sport: one round, one played game whose score must not leak.
        self.petanque = Petanque.objects.create(edition=self.edition, reveal_score=False)
        self.petanque_r1 = TeamSportRound.objects.create(discipline=self.petanque, order=0)
        self.g4 = Game.objects.create(
            discipline=self.petanque, round=self.petanque_r1, team1=self.team_a, score1=13,
            team2=self.team_b, score2=4, referees=self.team_c, edition=self.edition,
            is_played=True,
        )


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
                {
                    "id": self.relay.id,
                    "name": "Relay",
                    "result_type": "PTS",
                    "reveal_score": True,
                    "pairing_system": "NO",
                },
                {
                    "id": self.orienteering.id,
                    "name": "Orienteering",
                    "result_type": "TIM",
                    "reveal_score": False,
                    "pairing_system": "NO",
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

    def test_roster_players_carry_their_user_id(self):
        aigles = self.summary()["teams"][0]
        users = {u.username: u.id for u in User.objects.filter(username__in=["ana", "bob"])}

        self.assertEqual([p["user"] for p in aigles["players"]], [users["ana"], users["bob"]])

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

    def test_empty_result_type_is_treated_as_no_score(self):
        Discipline.objects.filter(pk=self.relay.pk).update(result_type="")

        results = [r for r in self.summary()["results"] if r["discipline"] == self.relay.id]
        for result in results:
            for field in ("ranking", "points", "time", "points_difference", "global_points"):
                self.assertIsNone(result[field], field)


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
        self.team = Team.objects.create(name="Aigles", edition=self.edition)
        self.relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        # A discipline without games keeps its points null until an organiser enters one;
        # give it a value here so the public shape check below has a ranking to assert on.
        TeamResult.objects.filter(discipline=self.relay, team=self.team).update(points=0)

    def test_public_without_token(self):
        response = self.client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()),
            {"edition", "disciplines", "teams", "results", "rounds", "games"},
        )
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


class TestGameIsPlayed(TestCase):
    """A game starts unplayed; the admin edits the flag in the changelist."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def test_defaults_to_not_played(self):
        game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        self.assertFalse(game.is_played)

    @override_settings(
        STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
    )
    def test_admin_edits_scores_and_is_played_in_the_changelist(self):
        User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(User.objects.get(username="root"))

        game_ab = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        game_bc = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.b, team2=self.c,
            referees=self.a, edition=self.edition,
        )

        response = self.client.get("/admin/olympic_warriors/game/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="form-0-is_played"', content)
        self.assertIn("Score 1", content)

        # Read the row order the changelist actually rendered rather than assuming it.
        row_ids = dict(re.findall(r'name="form-(\d)-id" value="(\d+)"', content))
        self.assertEqual(set(row_ids), {"0", "1"})
        row_for_game = {game_ab.pk: None, game_bc.pk: None}
        for row, pk in row_ids.items():
            row_for_game[int(pk)] = row

        edits = {
            game_ab.pk: {"score1": 9, "score2": 1},
            game_bc.pk: {"score1": 5, "score2": 3},
        }
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        for pk, scores in edits.items():
            row = row_for_game[pk]
            data[f"form-{row}-id"] = str(pk)
            data[f"form-{row}-score1"] = str(scores["score1"])
            data[f"form-{row}-score2"] = str(scores["score2"])
            data[f"form-{row}-is_played"] = "on"

        response = self.client.post("/admin/olympic_warriors/game/", data)
        self.assertEqual(response.status_code, 302)

        game_ab.refresh_from_db()
        game_bc.refresh_from_db()
        self.assertTrue(game_ab.is_played)
        self.assertTrue(game_bc.is_played)

        # Game creation grants both teams the +1 draw point (see Game.save()); the edits
        # above each move an old 0-0 draw to a > victory, i.e. +2/-1 (see Game.save()):
        # A: +1 (created) +2 (9-1 win)          = 3
        # B: +1 (created, game_ab) -1 (game_ab) +1 (created, game_bc) +2 (5-3 win) = 3
        # C: +1 (created, game_bc) -1 (game_bc) = 0
        points_by_team = {
            r.team.name: r.points
            for r in TeamResult.objects.filter(discipline=self.darts)
        }
        self.assertEqual(points_by_team, {"A": 3, "B": 3, "C": 0})

    @override_settings(
        STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
    )
    def test_admin_changelist_search_uses_related_names(self):
        """search_fields must point at text columns: FK names alone raise FieldError."""
        User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(User.objects.get(username="root"))
        Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        response = self.client.get("/admin/olympic_warriors/game/", {"q": "Darts"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="form-0-is_played"')

    def test_negative_score_is_rejected(self):
        game = Game(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition, score1=-1,
        )
        with self.assertRaises(ValidationError):
            game.full_clean()

    def test_backfill_marks_existing_games_played(self):
        migration = importlib.import_module("olympic_warriors.migrations.0028_game_is_played")

        game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        migration.mark_existing_games_played(apps, None)
        game.refresh_from_db()
        self.assertTrue(game.is_played)


class TestSummarySchedule(ScheduleSetup, TestCase):
    """Rounds and games in the summary; scores hidden until the discipline is revealed."""

    def test_rounds_in_discipline_and_order(self):
        rounds = self.summary()["rounds"]
        self.assertEqual(
            rounds,
            [
                {"id": self.darts_r1.id, "discipline": self.darts.id, "order": 0, "is_over": False},
                {"id": self.darts_r2.id, "discipline": self.darts.id, "order": 1, "is_over": False},
                {
                    "id": self.petanque_r1.id,
                    "discipline": self.petanque.id,
                    "order": 0,
                    "is_over": False,
                },
            ],
        )

    def test_games_in_round_order_with_scores_when_revealed(self):
        games = [g for g in self.summary()["games"] if g["discipline"] == self.darts.id]
        self.assertEqual([g["id"] for g in games], [self.g1.id, self.g2.id, self.g3.id])
        self.assertEqual(
            games[0],
            {
                "id": self.g1.id,
                "discipline": self.darts.id,
                "round": self.darts_r1.id,
                "team1": self.team_b.id,
                "team2": self.team_a.id,
                "referees": self.team_c.id,
                "is_played": True,
                "score1": 12,
                "score2": 9,
            },
        )
        self.assertFalse(games[1]["is_played"])

    def test_hidden_discipline_game_keeps_pairing_but_not_scores(self):
        game = next(g for g in self.summary()["games"] if g["discipline"] == self.petanque.id)
        self.assertEqual(
            (game["team1"], game["team2"], game["referees"]),
            (self.team_a.id, self.team_b.id, self.team_c.id),
        )
        self.assertTrue(game["is_played"])
        self.assertIsNone(game["score1"])
        self.assertIsNone(game["score2"])

    def test_inactive_round_and_game_excluded(self):
        self.darts_r2.is_active = False
        self.darts_r2.save()
        Game.objects.filter(pk=self.g2.pk).update(is_active=False)
        data = self.summary()
        self.assertEqual([r["id"] for r in data["rounds"]], [self.darts_r1.id, self.petanque_r1.id])
        self.assertEqual([g["id"] for g in data["games"]], [self.g1.id, self.g4.id])

    def test_inactive_discipline_rounds_and_games_excluded(self):
        Discipline.objects.filter(pk=self.darts.pk).update(is_active=False)
        data = self.summary()
        self.assertEqual([r["id"] for r in data["rounds"]], [self.petanque_r1.id])
        self.assertEqual([g["id"] for g in data["games"]], [self.g4.id])

    def test_other_edition_rounds_and_games_never_leak(self):
        other_relay = Relay.objects.get(edition=self.other)
        team_y = Team.objects.create(name="Ypres", edition=self.other)
        TeamResult.objects.create(team=team_y, discipline=other_relay, points=0)
        TeamSportRound.objects.create(discipline=other_relay, order=0)
        Game.objects.create(
            discipline=other_relay, round=TeamSportRound.objects.get(discipline=other_relay),
            team1=self.team_z, team2=team_y, referees=self.team_z, edition=self.other,
        )
        data = self.summary()
        self.assertNotIn(other_relay.id, [r["discipline"] for r in data["rounds"]])
        self.assertNotIn(other_relay.id, [g["discipline"] for g in data["games"]])


class TestStaffSummary(APITestCase):
    """
    Staff get the scores of every game and the stored value of every result whatever
    reveal_score says; the ranking of a hidden discipline stays null for everyone.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)  # hidden, PTS, no round yet
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.a, edition=self.edition, score1=7, score2=3, is_played=True,
        )
        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.player = User.objects.create_user(username="player", password="x")

    def summary(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        response = client.get("/edition/year/2026/summary/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_public_and_player_get_no_score_on_a_hidden_discipline(self):
        for user in (None, self.player):
            data = self.summary(user)
            game = data["games"][0]
            self.assertEqual((game["score1"], game["score2"]), (None, None))
            result = next(r for r in data["results"] if r["team"] == self.a.id)
            self.assertIsNone(result["points"])
            self.assertIsNone(result["ranking"])

    def test_staff_get_scores_and_stored_points_but_no_ranking(self):
        data = self.summary(self.staff)
        game = data["games"][0]
        self.assertEqual((game["score1"], game["score2"]), (7, 3))
        result = next(r for r in data["results"] if r["team"] == self.a.id)
        self.assertEqual(result["points"], 3)  # league points of the played win
        self.assertIsNone(result["ranking"])
        self.assertIsNone(result["global_points"])

    def test_staff_get_a_stored_time(self):
        crossfit = Crossfit.objects.create(edition=self.edition)  # hidden, TIM, no round
        TeamResult.objects.filter(discipline=crossfit, team=self.a).update(time="00:13:15")
        data = self.summary(self.staff)
        result = next(
            r for r in data["results"] if r["team"] == self.a.id and r["discipline"] == crossfit.id
        )
        self.assertEqual(result["time"], "00:13:15")
        self.assertIsNone(result["ranking"])

    def test_revealed_discipline_is_the_same_for_everyone(self):
        Discipline.objects.filter(id=self.darts.id).update(reveal_score=True)
        public = self.summary()
        staff = self.summary(self.staff)
        self.assertEqual(public["games"], staff["games"])
        self.assertEqual(public["results"], staff["results"])

    def test_disciplines_carry_their_pairing_system(self):
        data = self.summary()
        self.assertEqual(data["disciplines"][0]["pairing_system"], "NO")

    def test_a_fresh_result_has_no_value(self):
        quiz = Discipline.objects.create(name="Quiz", edition=self.edition, result_type="PTS")
        crossfit = Crossfit.objects.create(edition=self.edition)
        self.assertIsNone(TeamResult.objects.get(discipline=quiz, team=self.a).points)
        self.assertIsNone(TeamResult.objects.get(discipline=crossfit, team=self.a).time)
        self.assertEqual(TeamResult.objects.get(discipline=self.darts, team=self.a).points, 3)

    def test_swiss_bye_team_starts_at_zero_not_null(self):
        Team.objects.create(name="C", edition=self.edition)
        petanque = Discipline.objects.create(
            name="Petanque", edition=self.edition, result_type="PTS",
            pairing_system=Discipline.PairingSystem.SWISS, max_rounds=3,
        )
        points = set(
            TeamResult.objects.filter(discipline=petanque).values_list("points", flat=True)
        )
        self.assertEqual(points, {0})

    def test_switching_to_swiss_later_zeroes_the_bye_team(self):
        # Created without games: every result starts null. Switching to Swiss must zero them
        # all, including the bye team that Game.save() never touches.
        Team.objects.create(name="C", edition=self.edition)
        petanque = Discipline.objects.create(name="Petanque", edition=self.edition, result_type="PTS")
        self.assertEqual(
            set(TeamResult.objects.filter(discipline=petanque).values_list("points", flat=True)),
            {None},
        )
        petanque.pairing_system = Discipline.PairingSystem.SWISS
        petanque.max_rounds = 3
        petanque.save()
        self.assertEqual(
            set(TeamResult.objects.filter(discipline=petanque).values_list("points", flat=True)),
            {0},
        )


class TestCurrentUser(APITestCase):

    def test_current_user_says_whether_staff(self):
        staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.client.force_authenticate(user=staff)
        response = self.client.get("/user/current/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertNotIn("password", response.data)

    def test_current_user_refuses_a_player(self):
        # Staff-only through the default permission: a player never needs it.
        player = User.objects.create_user(username="player", password="x")
        self.client.force_authenticate(user=player)
        response = self.client.get("/user/current/")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("is_staff", response.data)


class TestLatestEdition(TestCase):

    def test_latest_is_the_highest_active_year(self):
        Edition.objects.create(year=2026, host="P", start_date="2026-09-19", end_date="2026-09-20")
        Edition.objects.create(
            year=2027, host="L", start_date="2027-09-19", end_date="2027-09-20", is_active=False
        )
        self.assertEqual(latest_edition().year, 2026)

    def test_latest_ignores_creation_order(self):
        Edition.objects.create(year=2026, host="P", start_date="2026-09-19", end_date="2026-09-20")
        Edition.objects.create(year=2025, host="L", start_date="2025-09-19", end_date="2025-09-20")
        self.assertEqual(latest_edition().year, 2026)

    def test_none_without_any_edition(self):
        self.assertIsNone(latest_edition())


class TestManualRankingSummary(SummarySetup, TestCase):
    """A manual edition ranks teams by final_rank and sends no totals."""

    def setUp(self):
        super().setUp()
        Team.objects.filter(pk=self.team_b.pk).update(final_rank=1)
        Team.objects.filter(pk=self.team_a.pk).update(final_rank=2)

    def test_teams_carry_final_rank_and_null_totals(self):
        teams = {team["name"]: team for team in self.summary()["teams"]}

        self.assertEqual(teams["Bisons"]["ranking"], 1)
        self.assertEqual(teams["Aigles"]["ranking"], 2)
        self.assertIsNone(teams["Cerfs"]["ranking"])
        self.assertEqual({team["total_points"] for team in teams.values()}, {None})

    def test_results_are_still_ranked(self):
        results = {
            r["team"]: r for r in self.summary()["results"] if r["discipline"] == self.relay.id
        }

        self.assertEqual(results[self.team_b.id]["ranking"], 1)
        self.assertEqual(results[self.team_b.id]["global_points"], 5)


class TestSummaryQueryCount(SummarySetup, TestCase):
    """The summary computes the standings once; nothing fans out per team or result."""

    def test_summary_runs_in_a_fixed_number_of_queries(self):
        for _ in range(3):  # more results must not mean more queries
            Relay.objects.create(edition=self.edition, reveal_score=True)

        with self.assertNumQueries(SUMMARY_QUERIES):
            self.summary()
