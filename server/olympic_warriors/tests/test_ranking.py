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
    ResultTypes,
)
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
            is_played=True,
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
            is_played=True,
        )

        self.assertEqual(self.result(self.team_a).points_difference, 0)

    def test_team_total_and_ranking_follow_the_standings(self):
        # C and D never play, so their points stay null and they are unranked (0 points).
        self.play(self.team_a, 5, self.team_b, 2)  # A rank 1 of 4 -> 6, B rank 2 -> 4

        self.assertEqual(self.team_a.total_points, 6)
        self.assertEqual(self.team_b.total_points, 4)
        self.assertEqual(self.team_c.total_points, 0)
        self.assertEqual(self.team_a.ranking, 1)
        self.assertEqual(self.team_b.ranking, 2)
        self.assertEqual(self.team_c.ranking, 3)

    def test_manual_edition_ranks_teams_by_final_rank_without_totals(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Team.objects.filter(pk=self.team_b.pk).update(final_rank=1)
        Team.objects.filter(pk=self.team_a.pk).update(final_rank=2)

        self.assertTrue(self.edition.ranking_is_manual)
        self.assertEqual(Team.objects.get(pk=self.team_b.pk).ranking, 1)
        self.assertEqual(Team.objects.get(pk=self.team_a.pk).ranking, 2)
        self.assertIsNone(Team.objects.get(pk=self.team_c.pk).ranking)
        self.assertIsNone(Team.objects.get(pk=self.team_a.pk).total_points)
        # the discipline standing is still computed
        self.assertEqual(self.result(self.team_a).ranking, 1)

    def test_edition_without_final_rank_is_not_manual(self):
        self.assertFalse(self.edition.ranking_is_manual)

    def test_unsaved_rows_have_empty_standings(self):
        self.assertEqual(TeamResult(team=self.team_a, discipline=self.darts).ranking, 0)
        self.assertEqual(TeamResult(team=self.team_a, discipline=self.darts).global_points, 0)
        self.assertIsNone(Team(name="New", edition=self.edition).ranking)

class TestRankingTieBreaker(RankingTestSetup):
    """Equal league points are split by points difference; equal difference shares a rank."""

    def test_equal_points_are_ranked_by_difference(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A 3 pts (+3), B 0 pts (-3)
        self.play(self.team_c, 1, self.team_d, 0)  # C 3 pts (+1), D 0 pts (-1)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 2)
        self.assertEqual(self.result(self.team_d).ranking, 3)
        self.assertEqual(self.result(self.team_b).ranking, 4)

    def test_more_points_beat_better_difference(self):
        self.play(self.team_a, 1, self.team_b, 0)  # A 3 pts (+1)
        self.play(self.team_c, 9, self.team_d, 9)  # C 1 pt (0), D 1 pt (0)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 2)
        self.assertEqual(self.result(self.team_d).ranking, 2)
        self.assertEqual(self.result(self.team_b).ranking, 4)

    def test_equal_points_and_difference_share_rank(self):
        self.play(self.team_a, 3, self.team_b, 1)  # A 3 pts (+2), B 0 pts (-2)
        self.play(self.team_c, 3, self.team_d, 1)  # C 3 pts (+2), D 0 pts (-2)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_c).ranking, 1)
        self.assertEqual(self.result(self.team_b).ranking, 3)
        self.assertEqual(self.result(self.team_d).ranking, 3)

    def test_hidden_scores_rank_zero(self):
        self.darts.reveal_score = False
        self.darts.save()
        self.play(self.team_a, 5, self.team_b, 2)

        self.assertEqual(self.result(self.team_a).ranking, 0)

    def test_discipline_without_games_ranks_on_points_only(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition, reveal_score=True)
        points = {self.team_a: 10, self.team_b: 5, self.team_c: 5, self.team_d: 0}
        for team, value in points.items():
            TeamResult.objects.filter(team=team, discipline=quizz).update(points=value)

        def rank(team):
            return TeamResult.objects.get(team=team, discipline=quizz).ranking

        self.assertEqual(rank(self.team_a), 1)
        self.assertEqual(rank(self.team_b), 2)
        self.assertEqual(rank(self.team_c), 2)
        self.assertEqual(rank(self.team_d), 4)
        self.assertEqual(
            TeamResult.objects.get(team=self.team_b, discipline=quizz).points_difference, 0
        )

    def test_inactive_results_are_not_counted(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A 3 pts (+3)
        self.play(self.team_c, 1, self.team_d, 0)  # C 3 pts (+1), D 0 pts (-1)
        TeamResult.objects.filter(team=self.team_c, discipline=self.darts).update(is_active=False)

        self.assertEqual(self.result(self.team_a).ranking, 1)
        self.assertEqual(self.result(self.team_d).ranking, 2)


class TestTeamResultSerializer(RankingTestSetup):
    """The API exposes the difference next to ranking and global_points."""

    def test_serializes_points_difference(self):
        self.play(self.team_a, 5, self.team_b, 2)

        data = TeamResultSerializer(self.result(self.team_a)).data

        self.assertEqual(data["points_difference"], 3)
        self.assertEqual(data["result_type"], "PTS")
        self.assertEqual(data["ranking"], 1)


class TestGlobalPoints(RankingTestSetup):
    """global_points rewards the discipline rank; an unranked result earns nothing."""

    def test_points_follow_ranking_with_podium_bonus(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A 3 pts (+3), B 0 pts (-3)
        self.play(self.team_c, 1, self.team_d, 0)  # C 3 pts (+1), D 0 pts (-1)

        # 4 teams: rank 1 -> 4 + 2, rank 2 -> 3 + 1, rank 3 -> 2 + 1, rank 4 -> 1
        self.assertEqual(self.result(self.team_a).global_points, 6)
        self.assertEqual(self.result(self.team_c).global_points, 4)
        self.assertEqual(self.result(self.team_d).global_points, 3)
        self.assertEqual(self.result(self.team_b).global_points, 1)

    def test_hidden_scores_give_no_points(self):
        self.darts.reveal_score = False
        self.darts.save()
        self.play(self.team_a, 5, self.team_b, 2)

        self.assertEqual(self.result(self.team_a).global_points, 0)

    def test_result_type_none_gives_no_points(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Darts.objects.filter(pk=self.darts.pk).update(result_type=ResultTypes.NONE)

        self.assertEqual(self.result(self.team_a).ranking, 0)
        self.assertEqual(self.result(self.team_a).global_points, 0)
        self.assertEqual(self.result(self.team_b).global_points, 0)
