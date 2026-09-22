"""
League points of a team-sport discipline are recomputed from its played games.
"""

from django.test import TestCase

from olympic_warriors.models import Darts, Edition, Game, Team, TeamResult, TeamSportRound


class PointsSetup(TestCase):
    """One revealed Darts discipline, three teams, one round, no game yet."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def game(self, team1, score1, team2, score2, **kwargs):
        return Game.objects.create(
            discipline=self.darts,
            round=self.round,
            team1=team1,
            score1=score1,
            team2=team2,
            score2=score2,
            referees=self.c if self.c not in (team1, team2) else self.a,
            edition=self.edition,
            **kwargs,
        )

    def points(self, team):
        return TeamResult.objects.get(team=team, discipline=self.darts).points


class TestLeaguePoints(PointsSetup):

    def test_unplayed_game_grants_nothing(self):
        self.game(self.a, 0, self.b, 0)
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 0))

    def test_unplayed_game_with_scores_grants_nothing(self):
        self.game(self.a, 9, self.b, 1)
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 0))

    def test_played_win_grants_three_and_zero(self):
        self.game(self.a, 9, self.b, 1, is_played=True)
        self.assertEqual((self.points(self.a), self.points(self.b)), (3, 0))

    def test_played_draw_grants_one_each(self):
        self.game(self.a, 4, self.b, 4, is_played=True)
        self.assertEqual((self.points(self.a), self.points(self.b)), (1, 1))

    def test_marking_played_adds_and_unmarking_removes(self):
        game = self.game(self.a, 9, self.b, 1)
        game.is_played = True
        game.save()
        self.assertEqual((self.points(self.a), self.points(self.b)), (3, 0))
        game.is_played = False
        game.save()
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 0))

    def test_editing_a_played_score_recomputes(self):
        game = self.game(self.a, 9, self.b, 1, is_played=True)
        game.score1, game.score2 = 2, 5
        game.save()
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 3))

    def test_editing_an_unplayed_score_changes_nothing(self):
        game = self.game(self.a, 0, self.b, 0)
        game.score1 = 7
        game.save()
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 0))

    def test_soft_deleting_a_played_game_removes_its_points(self):
        game = self.game(self.a, 9, self.b, 1, is_played=True)
        game.is_active = False
        game.save()
        self.assertEqual((self.points(self.a), self.points(self.b)), (0, 0))

    def test_moving_a_played_game_to_another_team_recomputes_both(self):
        game = self.game(self.a, 9, self.b, 1, is_played=True)
        game.team1 = self.c
        game.referees = self.a
        game.save()
        self.assertEqual(
            (self.points(self.a), self.points(self.b), self.points(self.c)), (0, 0, 3)
        )

    def test_points_accumulate_over_played_games_only(self):
        self.game(self.a, 9, self.b, 1, is_played=True)
        self.game(self.a, 2, self.c, 2, is_played=True)
        self.game(self.b, 5, self.c, 0)
        self.assertEqual(
            (self.points(self.a), self.points(self.b), self.points(self.c)), (4, 0, 1)
        )

    def test_points_difference_ignores_unplayed_games(self):
        self.game(self.a, 9, self.b, 1, is_played=True)
        self.game(self.a, 0, self.c, 7)
        result = TeamResult.objects.get(team=self.a, discipline=self.darts)
        self.assertEqual(result.points_difference, 8)
