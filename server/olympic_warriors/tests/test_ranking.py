"""
Tests for discipline rankings and the points difference tie-breaker.
"""

from django.test import TestCase

from olympic_warriors.models import (
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    Darts,
    GeneralCultureQuizz,
)
from olympic_warriors.models.Team import annotate_points_difference
from olympic_warriors.serializer import TeamResultSerializer


class RankingTestSetup(TestCase):
    """
    One edition with four teams and a Darts discipline without a pairing system, so no
    game is scheduled automatically and each test creates exactly the games it needs.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
        )
        self.team_a = Team.objects.create(name="A", edition=self.edition)
        self.team_b = Team.objects.create(name="B", edition=self.edition)
        self.team_c = Team.objects.create(name="C", edition=self.edition)
        self.team_d = Team.objects.create(name="D", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def play(self, team1, score1, team2, score2):
        """
        Create a finished game; Game.save() rolls the league points into TeamResult.
        """
        return Game.objects.create(
            discipline=self.darts,
            round=self.round,
            team1=team1,
            score1=score1,
            team2=team2,
            score2=score2,
            referees=self.team_d,
            edition=self.edition,
        )

    def result(self, team):
        return TeamResult.objects.get(team=team, discipline=self.darts)


class TestPointsDifference(RankingTestSetup):
    """points_difference is summed from the discipline's active games."""

    def test_sums_games_as_team1_and_as_team2(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A +3, B -3
        self.play(self.team_d, 2, self.team_a, 3)  # A +1, D -1

        self.assertEqual(self.result(self.team_a).points_difference, 4)
        self.assertEqual(self.result(self.team_b).points_difference, -3)
        self.assertEqual(self.result(self.team_d).points_difference, -1)

    def test_is_zero_without_games(self):
        self.assertEqual(self.result(self.team_c).points_difference, 0)

    def test_ignores_inactive_games(self):
        game = self.play(self.team_a, 5, self.team_b, 2)
        game.is_active = False
        game.save()

        self.assertEqual(self.result(self.team_a).points_difference, 0)
        self.assertEqual(self.result(self.team_b).points_difference, 0)

    def test_ignores_games_of_other_disciplines(self):
        other = Darts.objects.create(edition=self.edition, reveal_score=True)
        other_round = TeamSportRound.objects.create(discipline=other, order=0)
        Game.objects.create(
            discipline=other,
            round=other_round,
            team1=self.team_a,
            score1=9,
            team2=self.team_b,
            score2=0,
            referees=self.team_d,
            edition=self.edition,
        )

        self.assertEqual(self.result(self.team_a).points_difference, 0)

    def test_annotated_queryset_iterates_as_model_instances(self):
        self.play(self.team_a, 5, self.team_b, 2)
        results = annotate_points_difference(
            TeamResult.objects.filter(discipline=self.darts).order_by("team__name")
        )

        differences = [result.points_difference for result in results]

        self.assertEqual(differences, [3, -3, 0, 0])
