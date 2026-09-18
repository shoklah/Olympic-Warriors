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
    GeneralCultureQuizz,
    ResultTypes,
)


class DisciplineTestSetup(TestCase):
    """
    One edition with six active teams (the smallest count that lets the
    round-robin scheduler keep teams free to referee) and one inactive team.
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
        self.assertEqual(results.count(), 6)
        self.assertTrue(all(result.points == 0 for result in results))
        self.assertFalse(results.filter(team=self.inactive_team).exists())

    def test_schedules_no_rounds_or_games(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        self.assertEqual(TeamSportRound.objects.filter(discipline=quizz).count(), 0)
        self.assertEqual(Game.objects.filter(discipline=quizz).count(), 0)
