from collections import Counter
from itertools import combinations

from django.test import TestCase

from olympic_warriors.models import Discipline, Edition, Game, Team, TeamResult, TeamSportRound
from olympic_warriors.models.ResultTypes import ResultTypes
from olympic_warriors.schedule.round_robin import round_robin_pairings


def _games_per_team(discipline):
    played = Counter()
    for game in Game.objects.filter(discipline=discipline, is_active=True):
        played[game.team1_id] += 1
        played[game.team2_id] += 1
    return played


class SchedulingSetup(TestCase):

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2025,
            host="Paris",
            start_date="2025-06-01",
            end_date="2025-06-03",
            is_active=True,
        )

    def create_teams(self, count):
        return [
            Team.objects.create(name=f"Team {index}", edition=self.edition)
            for index in range(count)
        ]

    def create_discipline(self, **kwargs):
        kwargs.setdefault("name", "Rugby")
        kwargs.setdefault("edition", self.edition)
        kwargs.setdefault("result_type", ResultTypes.POINTS)
        return Discipline.objects.create(**kwargs)

    def assert_every_pair_meets_once(self, discipline, teams):
        pairs = Counter(
            frozenset((game.team1_id, game.team2_id))
            for game in Game.objects.filter(discipline=discipline, is_active=True)
        )
        expected = {frozenset((a.id, b.id)) for a, b in combinations(teams, 2)}
        self.assertEqual(set(pairs), expected)
        self.assertEqual(set(pairs.values()), {1})

    def assert_referees_are_not_playing(self, discipline):
        for game in Game.objects.filter(discipline=discipline, is_active=True):
            self.assertNotIn(game.referees_id, (game.team1_id, game.team2_id), str(game))


class TestRoundRobinPairings(TestCase):

    def test_even_number_of_teams(self):
        rounds = round_robin_pairings(list("ABCDEF"))
        self.assertEqual(len(rounds), 5)
        for pairings in rounds:
            self.assertEqual(len(pairings), 3)
            self.assertEqual(sorted(team for pair in pairings for team in pair), list("ABCDEF"))
        pairs = [frozenset(pair) for pairings in rounds for pair in pairings]
        self.assertEqual(len(pairs), 15)
        self.assertEqual(len(set(pairs)), 15)

    def test_odd_number_of_teams(self):
        rounds = round_robin_pairings(list("ABCDE"))
        self.assertEqual(len(rounds), 5)
        byes = []
        for pairings in rounds:
            self.assertEqual(len(pairings), 2)
            playing = {team for pair in pairings for team in pair}
            self.assertEqual(len(playing), 4)
            byes.extend(set("ABCDE") - playing)
        self.assertEqual(sorted(byes), list("ABCDE"))
        pairs = [frozenset(pair) for pairings in rounds for pair in pairings]
        self.assertEqual(len(set(pairs)), 10)


class TestRoundRobinScheduling(SchedulingSetup):

    def test_six_teams_play_the_same_number_of_games(self):
        teams = self.create_teams(6)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)

        discipline.refresh_from_db()
        self.assertEqual(discipline.max_rounds, 5)
        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 5)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 15)

        played = _games_per_team(discipline)
        self.assertEqual({played[team.id] for team in teams}, {5})
        self.assert_every_pair_meets_once(discipline, teams)
        self.assert_referees_are_not_playing(discipline)

        # Every team plays once per round
        for game_round in TeamSportRound.objects.filter(discipline=discipline):
            playing = Counter()
            for game in Game.objects.filter(round=game_round):
                playing[game.team1_id] += 1
                playing[game.team2_id] += 1
            self.assertEqual({playing[team.id] for team in teams}, {1})

        # Nobody starts with an advantage
        points = {
            result.points
            for result in TeamResult.objects.filter(discipline=discipline, is_active=True)
        }
        self.assertEqual(len(points), 1)

        # Refereeing is spread evenly
        refereed = Counter(
            game.referees_id for game in Game.objects.filter(discipline=discipline)
        )
        self.assertLessEqual(max(refereed.values()) - min(refereed[team.id] for team in teams), 1)

    def test_odd_number_of_teams(self):
        teams = self.create_teams(5)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)

        discipline.refresh_from_db()
        self.assertEqual(discipline.max_rounds, 5)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 10)
        self.assertEqual({_games_per_team(discipline)[team.id] for team in teams}, {4})
        self.assert_every_pair_meets_once(discipline, teams)
        self.assert_referees_are_not_playing(discipline)

    def test_max_rounds_limits_the_schedule(self):
        teams = self.create_teams(6)
        discipline = self.create_discipline(
            pairing_system=Discipline.PairingSystem.ROUND_ROBIN, max_rounds=3
        )

        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 3)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 9)
        self.assertEqual({_games_per_team(discipline)[team.id] for team in teams}, {3})

    def test_two_teams(self):
        self.create_teams(2)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)

        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 1)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 1)

    def test_not_enough_teams(self):
        self.create_teams(1)
        with self.assertRaises(ValueError):
            self.create_discipline(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)


class TestSwissScheduling(SchedulingSetup):

    def test_first_round_without_max_rounds(self):
        self.create_teams(6)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.SWISS)

        discipline.refresh_from_db()
        self.assertEqual(discipline.max_rounds, 3)
        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 1)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 3)

    def test_next_round_is_scheduled_when_round_is_over_until_max_rounds(self):
        self.create_teams(6)
        discipline = self.create_discipline(
            pairing_system=Discipline.PairingSystem.SWISS, max_rounds=2
        )

        first_round = TeamSportRound.objects.get(discipline=discipline)
        first_round.is_over = True
        first_round.save()
        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 2)
        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 6)

        second_round = TeamSportRound.objects.get(discipline=discipline, order=1)
        second_round.is_over = True
        second_round.save()
        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 2)

    def test_odd_number_of_teams_gives_a_bye(self):
        self.create_teams(5)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.SWISS)

        self.assertEqual(Game.objects.filter(discipline=discipline).count(), 2)


class TestSchedulingAfterCreation(SchedulingSetup):

    def test_pairing_system_set_later_schedules_games(self):
        teams = self.create_teams(4)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.NONE)
        self.assertFalse(Game.objects.filter(discipline=discipline).exists())

        # A team joining the edition after the discipline was created is registered too
        teams.append(Team.objects.create(name="Late team", edition=self.edition))

        discipline.pairing_system = Discipline.PairingSystem.ROUND_ROBIN
        discipline.save()

        self.assertEqual(
            TeamResult.objects.filter(discipline=discipline, is_active=True).count(), 5
        )
        self.assertEqual(TeamSportRound.objects.filter(discipline=discipline).count(), 5)
        self.assert_every_pair_meets_once(discipline, teams)

    def test_saving_again_does_not_schedule_twice(self):
        self.create_teams(4)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)
        games = Game.objects.filter(discipline=discipline).count()

        discipline.name = "Rugby 7"
        discipline.save()
        discipline.pairing_system = Discipline.PairingSystem.SWISS
        discipline.save()

        self.assertEqual(Game.objects.filter(discipline=discipline).count(), games)

    def test_editing_without_pairing_system_does_not_schedule(self):
        self.create_teams(4)
        discipline = self.create_discipline(pairing_system=Discipline.PairingSystem.NONE)

        discipline.name = "Fair"
        discipline.save()

        self.assertFalse(TeamSportRound.objects.filter(discipline=discipline).exists())
