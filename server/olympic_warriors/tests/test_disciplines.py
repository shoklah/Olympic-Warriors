"""
Tests for minimal and game-based discipline subclasses.
"""

from django.test import TestCase

from olympic_warriors.models import (
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    Discipline,
    GeneralCultureQuizz,
    Darts,
    ResultTypes,
)


class DisciplineTestSetup(TestCase):
    """
    One edition with six active teams and one inactive team. Six teams give the
    round-robin scheduler two simultaneous games and two referee teams per round.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
        )
        self.teams = [
            Team.objects.create(name=f"Team {i}", edition=self.edition) for i in range(1, 7)
        ]
        self.inactive_team = Team.objects.create(
            name="Ghost", edition=self.edition, is_active=False
        )


class TestGeneralCultureQuizz(DisciplineTestSetup):

    def test_sets_name_and_result_type(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        quizz.refresh_from_db()
        self.assertEqual(quizz.name, "General Culture Quizz")
        self.assertEqual(quizz.result_type, ResultTypes.POINTS)

    def test_creates_zero_point_result_per_active_team(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        results = TeamResult.objects.filter(discipline=quizz)
        self.assertEqual(results.count(), len(self.teams))
        self.assertFalse(results.exclude(points=0).exists())
        self.assertFalse(results.filter(time__isnull=False).exists())
        self.assertFalse(results.filter(team=self.inactive_team).exists())

    def test_schedules_no_rounds_or_games(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        self.assertEqual(TeamSportRound.objects.filter(discipline=quizz).count(), 0)
        self.assertEqual(Game.objects.filter(discipline=quizz).count(), 0)

    def test_resaving_does_not_duplicate_team_results(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        quizz.reveal_score = True
        quizz.save()
        self.assertEqual(TeamResult.objects.filter(discipline=quizz).count(), len(self.teams))


class TestDarts(DisciplineTestSetup):

    def _create_round_robin_darts(self):
        return Darts.objects.create(
            edition=self.edition,
            pairing_system=Discipline.PairingSystem.ROUND_ROBIN,
        )

    def test_sets_name_and_result_type(self):
        darts = Darts.objects.create(edition=self.edition)
        darts.refresh_from_db()
        self.assertEqual(darts.name, "Darts")
        self.assertEqual(darts.result_type, ResultTypes.POINTS)

    def test_round_robin_schedules_rounds_and_games_with_referees(self):
        darts = self._create_round_robin_darts()
        darts.refresh_from_db()

        # Six teams: max_rounds defaults to 5, two games per round.
        self.assertEqual(darts.max_rounds, 5)
        self.assertEqual(TeamSportRound.objects.filter(discipline=darts).count(), 5)

        games = Game.objects.filter(discipline=darts)
        self.assertEqual(games.count(), 10)
        for game in games:
            self.assertEqual(game.edition, self.edition)
            self.assertNotIn(game.referees_id, (game.team1_id, game.team2_id))

    def test_game_score_rolls_into_team_results(self):
        darts = self._create_round_robin_darts()
        game = Game.objects.filter(discipline=darts).first()

        # Scheduled games start 0-0, which Game.save() already counted as a draw (+1 each).
        team1_before = TeamResult.objects.get(team=game.team1, discipline=darts).points
        team2_before = TeamResult.objects.get(team=game.team2, discipline=darts).points

        game.score1 = 3
        game.score2 = 1
        game.save()

        team1_after = TeamResult.objects.get(team=game.team1, discipline=darts).points
        team2_after = TeamResult.objects.get(team=game.team2, discipline=darts).points

        # Draw -> team1 win: winner goes from 1 to 3 (+2), loser from 1 to 0 (-1).
        self.assertEqual(team1_after - team1_before, 2)
        self.assertEqual(team2_after - team2_before, -1)
