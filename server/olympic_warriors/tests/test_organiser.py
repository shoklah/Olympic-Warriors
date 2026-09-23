"""
Organiser endpoints: score a game, enter a result, reveal a discipline, close a round.
Staff only, latest edition only, every write through the models' save().
"""

from datetime import time

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Crossfit,
    Darts,
    Discipline,
    Edition,
    Game,
    Team,
    TeamResult,
    TeamSportRound,
)


class OrganiserSetup(APITestCase):
    """2026 (latest) with Darts (RR, one round, one game) and Crossfit (TIM, no round); 2025 with Darts."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.old = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition,
        )
        self.crossfit = Crossfit.objects.create(edition=self.edition)
        self.time_result = TeamResult.objects.get(discipline=self.crossfit, team=self.a)

        self.old_team = Team.objects.create(name="Z", edition=self.old)
        self.old_darts = Darts.objects.create(edition=self.old)
        self.old_result = TeamResult.objects.get(discipline=self.old_darts, team=self.old_team)

        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.player = User.objects.create_user(username="player", password="x")
        # JSON bodies: with the multipart default a missing boolean reads as False, not missing.
        self.client = APIClient()
        self.client.default_format = "json"
        self.client.force_authenticate(user=self.staff)

    def as_anonymous(self):
        client = APIClient()
        client.default_format = "json"
        return client

    def as_player(self):
        client = APIClient()
        client.default_format = "json"
        client.force_authenticate(user=self.player)
        return client


class TestPermissions(OrganiserSetup):

    def test_every_write_needs_a_token(self):
        client = self.as_anonymous()
        self.assertEqual(client.patch(f"/game/{self.game.id}/score/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/result/{self.time_result.id}/value/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 401)
        self.assertEqual(client.patch(f"/round/{self.round.id}/close/").status_code, 401)

    def test_every_write_refuses_a_player(self):
        client = self.as_player()
        self.assertEqual(client.patch(f"/game/{self.game.id}/score/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/result/{self.time_result.id}/value/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 403)
        self.assertEqual(client.patch(f"/round/{self.round.id}/close/").status_code, 403)


class TestGameScore(OrganiserSetup):

    def test_sets_the_score_and_recomputes_points(self):
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": True}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["score1"], response.data["score2"]), (7, 3))
        self.assertTrue(response.data["is_played"])
        self.assertEqual(TeamResult.objects.get(team=self.a, discipline=self.darts).points, 3)

    def test_unplaying_a_game_takes_its_points_back(self):
        self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": True})
        self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3, "is_played": False})
        self.assertEqual(TeamResult.objects.get(team=self.a, discipline=self.darts).points, 0)

    def test_refuses_a_missing_field_or_a_negative_score(self):
        response = self.client.patch(f"/game/{self.game.id}/score/", {"score1": 7, "score2": 3})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": -1, "score2": 3, "is_played": True}
        )
        self.assertEqual(response.status_code, 400)

    def test_404_on_an_inactive_or_unknown_game(self):
        Game.objects.filter(id=self.game.id).update(is_active=False)
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 1, "score2": 0, "is_played": True}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.patch("/game/999/score/", {}).status_code, 404)

    def test_409_outside_the_latest_edition(self):
        old_round = TeamSportRound.objects.create(discipline=self.old_darts, order=0)
        other = Team.objects.create(name="Y", edition=self.old)
        old_game = Game.objects.create(
            discipline=self.old_darts, round=old_round, team1=self.old_team, team2=other,
            referees=self.old_team, edition=self.old,
        )
        response = self.client.patch(
            f"/game/{old_game.id}/score/", {"score1": 1, "score2": 0, "is_played": True}
        )
        self.assertEqual(response.status_code, 409)

    def test_refuses_an_out_of_range_score(self):
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 10**9, "score2": 3, "is_played": True}
        )
        self.assertEqual(response.status_code, 400)

    def test_allows_scoring_after_the_round_is_closed(self):
        Game.objects.filter(id=self.game.id).update(is_played=True)
        self.client.patch(f"/round/{self.round.id}/close/")
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 5, "score2": 2, "is_played": True}
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_404_when_the_round_is_inactive(self):
        TeamSportRound.objects.filter(id=self.round.id).update(is_active=False)
        response = self.client.patch(
            f"/game/{self.game.id}/score/", {"score1": 1, "score2": 0, "is_played": True}
        )
        self.assertEqual(response.status_code, 404)


class TestTeamResult(OrganiserSetup):

    def test_sets_a_time_from_minutes_and_seconds(self):
        response = self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:15"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["time"], "00:13:15")
        self.time_result.refresh_from_db()
        self.assertEqual(self.time_result.time, time(0, 13, 15))

    def test_minutes_above_59_roll_into_hours(self):
        self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "75:02"})
        self.time_result.refresh_from_db()
        self.assertEqual(self.time_result.time, time(1, 15, 2))

    def test_empty_clears_the_value(self):
        self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:15"})
        response = self.client.patch(f"/result/{self.time_result.id}/value/", {"time": None})
        self.assertEqual(response.status_code, 200)
        self.time_result.refresh_from_db()
        self.assertIsNone(self.time_result.time)

    def test_sets_points_on_a_points_discipline_without_games(self):
        quiz = Discipline.objects.create(name="Quiz", edition=self.edition, result_type="PTS")
        result = TeamResult.objects.get(discipline=quiz, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 12})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["points"], 12)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": -1})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"/result/{result.id}/value/", {"time": "01:00"})
        self.assertEqual(response.status_code, 400)

    def test_refuses_a_bad_time_and_the_wrong_field(self):
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "13:75"}).status_code, 400
        )
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "0:13:15"}).status_code, 400
        )
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", {"points": 3}).status_code, 400
        )

    def test_refuses_a_discipline_with_rounds(self):
        result = TeamResult.objects.get(discipline=self.darts, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 3})
        self.assertEqual(response.status_code, 400)

    def test_409_outside_the_latest_edition(self):
        response = self.client.patch(f"/result/{self.old_result.id}/value/", {"points": 3})
        self.assertEqual(response.status_code, 409)

    def test_refuses_a_discipline_with_no_result_type(self):
        fair = Discipline.objects.create(name="Fair", edition=self.edition, result_type="NON")
        result = TeamResult.objects.get(discipline=fair, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 3})
        self.assertEqual(response.status_code, 400)

    def test_refuses_an_extra_key(self):
        quiz = Discipline.objects.create(name="Quiz2", edition=self.edition, result_type="PTS")
        result = TeamResult.objects.get(discipline=quiz, team=self.a)
        response = self.client.patch(f"/result/{result.id}/value/", {"points": 3, "x": 1})
        self.assertEqual(response.status_code, 400)

    def test_999_minutes_rolls_into_hours(self):
        self.client.patch(f"/result/{self.time_result.id}/value/", {"time": "999:59"})
        self.time_result.refresh_from_db()
        self.assertEqual(self.time_result.time, time(16, 39, 59))

    def test_refuses_a_non_object_body(self):
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", 5, format="json").status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(f"/result/{self.time_result.id}/value/", None, format="json").status_code,
            400,
        )

    def test_404_on_unknown_result(self):
        self.assertEqual(self.client.patch("/result/999/value/", {"points": 1}).status_code, 404)


class TestReveal(OrganiserSetup):

    def test_reveals_and_hides(self):
        response = self.client.patch(f"/discipline/{self.darts.id}/reveal/", {"reveal_score": True})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["reveal_score"])
        self.assertTrue(Discipline.objects.get(id=self.darts.id).reveal_score)
        self.client.patch(f"/discipline/{self.darts.id}/reveal/", {"reveal_score": False})
        self.assertFalse(Discipline.objects.get(id=self.darts.id).reveal_score)

    def test_refuses_a_missing_flag_and_an_old_edition(self):
        self.assertEqual(self.client.patch(f"/discipline/{self.darts.id}/reveal/", {}).status_code, 400)
        response = self.client.patch(f"/discipline/{self.old_darts.id}/reveal/", {"reveal_score": True})
        self.assertEqual(response.status_code, 409)

    def test_404_on_unknown_discipline(self):
        response = self.client.patch("/discipline/999/reveal/", {"reveal_score": True})
        self.assertEqual(response.status_code, 404)


class TestCloseRound(OrganiserSetup):

    def test_refuses_while_a_game_is_unplayed(self):
        response = self.client.patch(f"/round/{self.round.id}/close/")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(TeamSportRound.objects.get(id=self.round.id).is_over)

    def test_closes_a_complete_round(self):
        Game.objects.filter(id=self.game.id).update(is_played=True)
        response = self.client.patch(f"/round/{self.round.id}/close/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_over"])
        self.assertEqual(self.client.patch(f"/round/{self.round.id}/close/").status_code, 409)

    def test_closing_a_swiss_round_schedules_the_next_one(self):
        swiss = Discipline.objects.create(
            name="Petanque", edition=self.edition, result_type="PTS",
            pairing_system=Discipline.PairingSystem.SWISS, max_rounds=3,
        )
        first = TeamSportRound.objects.get(discipline=swiss, order=0)
        Game.objects.filter(round=first).update(is_played=True)
        response = self.client.patch(f"/round/{first.id}/close/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(TeamSportRound.objects.filter(discipline=swiss, order=1).exists())

    def test_409_outside_the_latest_edition(self):
        old_round = TeamSportRound.objects.create(discipline=self.old_darts, order=0)
        self.assertEqual(self.client.patch(f"/round/{old_round.id}/close/").status_code, 409)

    def test_closing_a_round_robin_round_schedules_nothing(self):
        rr = Discipline.objects.create(
            name="Chess", edition=self.edition, result_type="PTS",
            pairing_system=Discipline.PairingSystem.ROUND_ROBIN,
        )
        total_rounds_before = TeamSportRound.objects.filter(discipline=rr, is_active=True).count()
        first = TeamSportRound.objects.get(discipline=rr, order=0)
        Game.objects.filter(round=first).update(is_played=True)
        response = self.client.patch(f"/round/{first.id}/close/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            TeamSportRound.objects.filter(discipline=rr, is_active=True).count(), total_rounds_before
        )

    def test_404_on_unknown_round(self):
        self.assertEqual(self.client.patch("/round/999/close/").status_code, 404)
