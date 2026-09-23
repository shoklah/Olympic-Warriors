"""
Tests for olympic_warriors.standings: one pass over an edition, nothing stored.
"""

from datetime import time

from django.test import TestCase

from olympic_warriors.models import (
    Discipline,
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    Darts,
    Orienteering,
    Relay,
)
from olympic_warriors.standings import ResultStanding, TeamStanding, compute_standings


class StandingsSetup(TestCase):
    """
    One edition, four active teams and one inactive. Darts is a revealed points
    discipline without a pairing system, so each test plays exactly the games it needs.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.team_a = Team.objects.create(name="A", edition=self.edition)
        self.team_b = Team.objects.create(name="B", edition=self.edition)
        self.team_c = Team.objects.create(name="C", edition=self.edition)
        self.team_d = Team.objects.create(name="D", edition=self.edition)
        self.ghost = Team.objects.create(name="Ghost", edition=self.edition, is_active=False)
        self.darts = Darts.objects.create(edition=self.edition, reveal_score=True)
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)

    def play(self, team1, score1, team2, score2, **kwargs):
        kwargs.setdefault("is_played", True)
        return Game.objects.create(
            discipline=self.darts,
            round=self.round,
            team1=team1,
            score1=score1,
            team2=team2,
            score2=score2,
            referees=self.team_d,
            edition=self.edition,
            **kwargs,
        )

    def result(self, team, discipline=None):
        return TeamResult.objects.get(team=team, discipline=discipline or self.darts)

    def standing(self, team, discipline=None):
        return compute_standings(self.edition).result(self.result(team, discipline).id)


class TestPointsDiscipline(StandingsSetup):
    def test_ranks_by_points_then_difference_and_shares_ties(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A 3 pts (+3), B 0 (-3)
        self.play(self.team_c, 1, self.team_d, 0)  # C 3 pts (+1), D 0 (-1)

        self.assertEqual(self.standing(self.team_a), ResultStanding(1, 3, 6))
        self.assertEqual(self.standing(self.team_c), ResultStanding(2, 1, 4))
        self.assertEqual(self.standing(self.team_d), ResultStanding(3, -1, 3))
        self.assertEqual(self.standing(self.team_b), ResultStanding(4, -3, 1))

    def test_equal_points_and_difference_share_a_rank(self):
        self.play(self.team_a, 1, self.team_b, 0)  # A 3 (+1), B 0 (-1)
        self.play(self.team_c, 9, self.team_d, 9)  # C 1 (0), D 1 (0)

        self.assertEqual(self.standing(self.team_c).ranking, 2)
        self.assertEqual(self.standing(self.team_d).ranking, 2)
        self.assertEqual(self.standing(self.team_b).ranking, 4)

    def test_unplayed_and_inactive_games_do_not_count(self):
        self.play(self.team_a, 5, self.team_b, 2, is_played=False)
        game = self.play(self.team_c, 9, self.team_d, 0)
        game.is_active = False
        game.save()

        self.assertEqual(self.standing(self.team_a).points_difference, 0)
        self.assertEqual(self.standing(self.team_c).points_difference, 0)

    def test_hidden_discipline_has_rank_zero_and_no_global_points(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Darts.objects.filter(pk=self.darts.pk).update(reveal_score=False)

        standing = self.standing(self.team_a)
        self.assertEqual(standing.ranking, 0)
        self.assertEqual(standing.global_points, 0)
        self.assertEqual(standing.points_difference, 3)  # still computed, hidden by the API

    def test_result_without_points_has_rank_zero(self):
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=relay, team=self.team_a).update(points=7)

        self.assertEqual(self.standing(self.team_a, relay).ranking, 1)
        self.assertEqual(self.standing(self.team_b, relay), ResultStanding(0, 0, 0))

    def test_inactive_team_result_and_inactive_discipline_are_absent(self):
        hidden = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=hidden, team=self.team_a).update(points=7)
        Relay.objects.filter(pk=hidden.pk).update(is_active=False)
        standings = compute_standings(self.edition)

        # A's rank 1 in the deactivated discipline feeds nothing into the totals.
        self.assertEqual(standings.team(self.team_a.id), TeamStanding(1, 0))

        # Discipline.save() registers active teams only; give the ghost a row by hand.
        ghost_result = TeamResult.objects.create(team=self.ghost, discipline=self.darts)
        self.assertNotIn(ghost_result.id, standings.results)
        self.assertNotIn(self.result(self.team_a, hidden).id, standings.results)
        self.assertEqual(standings.result(ghost_result.id), ResultStanding())
        self.assertNotIn(self.ghost.id, standings.teams)
        self.assertEqual(standings.team(self.ghost.id), TeamStanding())

    def test_inactive_team_result_neither_ranks_nor_counts_as_registered(self):
        self.play(self.team_a, 5, self.team_b, 2)
        ghost_result = TeamResult.objects.create(team=self.ghost, discipline=self.darts, points=99)
        standings = compute_standings(self.edition)

        self.assertNotIn(ghost_result.id, standings.results)
        # 4 registered results, not 5: rank 1 -> 4 + 2
        self.assertEqual(standings.result(self.result(self.team_a).id), ResultStanding(1, 3, 6))

    def test_games_of_inactive_rounds_count_for_nothing(self):
        self.play(self.team_a, 5, self.team_b, 2)
        dead_round = TeamSportRound.objects.create(discipline=self.darts, order=1, is_active=False)
        game = Game.objects.create(
            discipline=self.darts,
            round=dead_round,
            team1=self.team_c,
            score1=9,
            team2=self.team_d,
            score2=0,
            referees=self.team_a,
            edition=self.edition,
            is_played=True,
        )
        game.save()  # recomputes league points from the games that count

        self.assertEqual(self.standing(self.team_c).points_difference, 0)
        self.assertEqual(self.result(self.team_c).points, 0)

    def test_discipline_without_result_type_ranks_nobody(self):
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        Discipline.objects.filter(pk=relay.pk).update(result_type="")
        TeamResult.objects.filter(discipline=relay, team=self.team_a).update(points=7)

        self.assertEqual(self.standing(self.team_a, relay), ResultStanding())


class TestTimeDiscipline(StandingsSetup):
    def test_smaller_time_ranks_first_and_missing_time_is_unranked(self):
        orienteering = Orienteering.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=orienteering, team=self.team_a).update(
            time=time(0, 12, 30)
        )
        TeamResult.objects.filter(discipline=orienteering, team=self.team_b).update(
            time=time(0, 10, 5)
        )
        TeamResult.objects.filter(discipline=orienteering, team=self.team_c).update(
            time=time(0, 12, 30)
        )

        self.assertEqual(self.standing(self.team_b, orienteering), ResultStanding(1, 0, 6))
        self.assertEqual(self.standing(self.team_a, orienteering).ranking, 2)
        self.assertEqual(self.standing(self.team_c, orienteering).ranking, 2)
        self.assertEqual(self.standing(self.team_d, orienteering).ranking, 0)


class TestTeamStandings(StandingsSetup):
    def test_totals_sum_global_points_and_rank_teams(self):
        self.play(self.team_a, 5, self.team_b, 2)  # darts: A 3 pts (+3), B 0 (-3)
        self.play(self.team_c, 0, self.team_d, 0)  # C 1 pt (0), D 1 pt (0)
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=relay, team=self.team_b).update(points=1)
        standings = compute_standings(self.edition)

        self.assertEqual(standings.team(self.team_b.id), TeamStanding(1, 7))
        self.assertEqual(standings.team(self.team_a.id), TeamStanding(2, 6))
        self.assertEqual(standings.team(self.team_c.id), TeamStanding(3, 4))
        self.assertEqual(standings.team(self.team_d.id), TeamStanding(3, 4))

    def test_runs_in_three_queries(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Relay.objects.create(edition=self.edition, reveal_score=True)

        with self.assertNumQueries(3):
            compute_standings(self.edition)

    def test_disciplines_of_a_team_carry_names_and_standings(self):
        self.play(self.team_a, 5, self.team_b, 2)
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=relay, team=self.team_b).update(points=1)
        standings = compute_standings(self.edition)

        b = {d.discipline_name: d for d in standings.disciplines_of(self.team_b.id)}

        self.assertEqual(set(b), {"Darts", "Relay"})
        self.assertEqual(b["Relay"].standing.ranking, 1)
        self.assertEqual(b["Relay"].discipline_id, relay.id)
        self.assertEqual(b["Darts"].standing.ranking, 2)
        self.assertEqual(standings.disciplines_of(self.ghost.id), ())  # inactive team
        self.assertEqual(standings.disciplines_of(999999), ())

    def test_disciplines_of_are_ordered_by_discipline_id(self):
        # Darts (from setUp) is created first, so it has the lowest id: creation order
        # doubles as discipline id order here, letting us pin the exact expected order.
        self.play(self.team_a, 5, self.team_b, 2)
        second = Relay.objects.create(edition=self.edition, reveal_score=True)
        third = Orienteering.objects.create(edition=self.edition, reveal_score=True)
        standings = compute_standings(self.edition)

        ids = [d.discipline_id for d in standings.disciplines_of(self.team_a.id)]

        self.assertEqual(ids, [self.darts.id, second.id, third.id])
        self.assertEqual(ids, sorted(ids))


class TestManualRanking(StandingsSetup):
    def test_stored_ranks_replace_the_computed_ones_and_totals_are_null(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Team.objects.filter(pk=self.team_b.pk).update(final_rank=1)
        Team.objects.filter(pk=self.team_a.pk).update(final_rank=2)
        Team.objects.filter(pk=self.team_c.pk).update(final_rank=2)
        standings = compute_standings(self.edition)

        self.assertEqual(standings.team(self.team_b.id), TeamStanding(1, None))
        self.assertEqual(standings.team(self.team_a.id), TeamStanding(2, None))
        self.assertEqual(standings.team(self.team_c.id), TeamStanding(2, None))
        self.assertEqual(standings.team(self.team_d.id), TeamStanding(None, None))
        # discipline standings are untouched
        self.assertEqual(standings.result(self.result(self.team_a).id).ranking, 1)

    def test_inactive_team_rank_does_not_make_the_edition_manual(self):
        Team.objects.filter(pk=self.ghost.pk).update(final_rank=1)

        self.assertEqual(compute_standings(self.edition).team(self.team_a.id).total_points, 0)
