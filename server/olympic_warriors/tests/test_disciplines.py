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
    Volleyball,
    JumpingRope,
    Dance,
    Frisbee,
    Geoguessr,
    Football,
    Handball,
    BurgerQuizz,
    BlindfoldedObstacleCourse,
    DiscThrow,
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
    """Minimal discipline: no scheduling, one resultless (points=None) row per active team."""

    def test_sets_name_and_result_type(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        quizz.refresh_from_db()
        self.assertEqual(quizz.name, "General Culture Quizz")
        self.assertEqual(quizz.result_type, ResultTypes.POINTS)

    def test_creates_a_pointless_result_per_active_team(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        results = TeamResult.objects.filter(discipline=quizz)
        self.assertEqual(results.count(), len(self.teams))
        self.assertFalse(results.exclude(points__isnull=True).exists())
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
    """Game-based discipline: pairing-system-driven scheduling and score roll-up."""

    def _create_round_robin_darts(self):
        return Darts.objects.create(
            edition=self.edition,
            pairing_system=Discipline.PairingSystem.ROUND_ROBIN,
        )

    def test_sets_name_and_result_type_and_schedules_nothing_by_default(self):
        darts = Darts.objects.create(edition=self.edition)
        darts.refresh_from_db()
        self.assertEqual(darts.name, "Darts")
        self.assertEqual(darts.result_type, ResultTypes.POINTS)
        self.assertEqual(TeamSportRound.objects.filter(discipline=darts).count(), 0)
        self.assertEqual(Game.objects.filter(discipline=darts).count(), 0)

    def test_round_robin_schedules_rounds_and_games_with_referees(self):
        darts = self._create_round_robin_darts()
        darts.refresh_from_db()

        # With six teams the scheduler creates len(teams) - 1 rounds in which
        # every team plays once, so every pair of teams meets exactly once.
        expected_rounds = len(self.teams) - 1
        expected_games = len(self.teams) * (len(self.teams) - 1) // 2
        self.assertEqual(darts.max_rounds, expected_rounds)
        self.assertEqual(
            TeamSportRound.objects.filter(discipline=darts).count(), expected_rounds
        )

        games = Game.objects.filter(discipline=darts)
        self.assertEqual(games.count(), expected_games)
        for game in games:
            self.assertEqual(game.edition, self.edition)
            self.assertNotIn(game.referees_id, (game.team1_id, game.team2_id))

    def test_game_score_rolls_into_team_results(self):
        darts = self._create_round_robin_darts()
        game = Game.objects.filter(discipline=darts).order_by("round__order", "id").first()

        # Scheduled games are unplayed: nobody has points yet.
        self.assertEqual(TeamResult.objects.get(team=game.team1, discipline=darts).points, 0)
        self.assertEqual(TeamResult.objects.get(team=game.team2, discipline=darts).points, 0)

        game.score1 = 3
        game.score2 = 1
        game.is_played = True
        game.save()

        self.assertEqual(TeamResult.objects.get(team=game.team1, discipline=darts).points, 3)
        self.assertEqual(TeamResult.objects.get(team=game.team2, discipline=darts).points, 0)

    def test_resaving_does_not_reschedule_or_rescore(self):
        darts = self._create_round_robin_darts()
        rounds_before = TeamSportRound.objects.filter(discipline=darts).count()
        games_before = Game.objects.filter(discipline=darts).count()
        points_before = dict(
            TeamResult.objects.filter(discipline=darts).values_list("team_id", "points")
        )

        # The scheduler writes max_rounds on a separately fetched instance, so refresh
        # first; resaving a stale instance would null max_rounds (see spec follow-ups).
        darts.refresh_from_db()
        darts.reveal_score = True
        darts.save()

        self.assertEqual(TeamSportRound.objects.filter(discipline=darts).count(), rounds_before)
        self.assertEqual(Game.objects.filter(discipline=darts).count(), games_before)
        points_after = dict(
            TeamResult.objects.filter(discipline=darts).values_list("team_id", "points")
        )
        self.assertEqual(points_after, points_before)


FIRST_EDITIONS_DISCIPLINES = [
    (Volleyball, "Volleyball", ResultTypes.POINTS),
    (JumpingRope, "Jumping Rope", ResultTypes.TIME),
    (Dance, "Dance", ResultTypes.POINTS),
    (Frisbee, "Frisbee", ResultTypes.POINTS),
    (Geoguessr, "Geoguessr", ResultTypes.POINTS),
    (Football, "Football", ResultTypes.POINTS),
    (Handball, "Handball", ResultTypes.POINTS),
    (BurgerQuizz, "Burger Quizz", ResultTypes.POINTS),
    (BlindfoldedObstacleCourse, "Blindfolded Obstacle Course", ResultTypes.TIME),
    (DiscThrow, "Disc Throw", ResultTypes.POINTS),
]


class TestFirstEditionsDisciplines(DisciplineTestSetup):
    """The disciplines of the first editions: name, result type and empty results."""

    def test_sets_name_and_result_type(self):
        for model, name, result_type in FIRST_EDITIONS_DISCIPLINES:
            with self.subTest(name=name):
                discipline = model.objects.create(edition=self.edition)
                discipline.refresh_from_db()
                self.assertEqual(discipline.name, name)
                self.assertEqual(discipline.result_type, result_type)

    def test_creates_an_empty_result_per_active_team(self):
        for model, name, _ in FIRST_EDITIONS_DISCIPLINES:
            with self.subTest(name=name):
                discipline = model.objects.create(edition=self.edition)
                results = TeamResult.objects.filter(discipline=discipline)
                self.assertEqual(results.count(), len(self.teams))
                self.assertFalse(results.filter(points__isnull=False).exists())
                self.assertFalse(results.filter(time__isnull=False).exists())
                self.assertFalse(results.filter(team=self.inactive_team).exists())

    def test_schedules_no_rounds_or_games_by_default(self):
        for model, name, _ in FIRST_EDITIONS_DISCIPLINES:
            with self.subTest(name=name):
                discipline = model.objects.create(edition=self.edition)
                self.assertEqual(
                    TeamSportRound.objects.filter(discipline=discipline).count(), 0
                )
                self.assertEqual(Game.objects.filter(discipline=discipline).count(), 0)
