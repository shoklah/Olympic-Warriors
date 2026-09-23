"""
Standings of an edition computed in one pass: discipline rankings, points differences,
global points, team totals and team ranks, from three queries and nothing stored.

The rules are the ones the model properties always applied:
- a result ranks only when its discipline is revealed and it has a score for its type;
  points disciplines rank by points then points difference, time disciplines by time;
  ties share a rank, unranked results have rank 0;
- global points reward the rank among the discipline's registered results, with a
  podium bonus; an unranked result earns nothing; registered results are the
  discipline's active results of active teams: a deactivated team neither ranks nor
  counts;
- a team's total is the sum of its global points, teams rank by total, ties shared;
- a manual edition (a team with a final_rank) ranks teams by that stored order instead,
  and has no totals.
"""

from collections import defaultdict
from dataclasses import dataclass

from .models import Game, Team, TeamResult
from .models.ResultTypes import ResultTypes


@dataclass(frozen=True)
class ResultStanding:
    """A team's standing in one discipline. Zeros when hidden or without a score."""

    ranking: int = 0
    points_difference: int = 0
    global_points: int = 0


@dataclass(frozen=True)
class TeamStanding:
    """A team's standing in the edition. Nones for a manual edition without a rank."""

    ranking: int | None = None
    total_points: int | None = None


@dataclass(frozen=True)
class Standings:
    """Standings of one edition: results by TeamResult id, teams by Team id."""

    results: dict[int, ResultStanding]
    teams: dict[int, TeamStanding]

    def result(self, result_id):
        """Standing of a result, or the zero standing when it is not part of the edition."""
        return self.results.get(result_id, ResultStanding())

    def team(self, team_id):
        """Standing of a team, or the empty standing when it is not active in the edition."""
        return self.teams.get(team_id, TeamStanding())


def global_points(ranking, registered):
    """Points a rank earns among `registered` results: reversed rank plus a podium bonus."""
    if ranking == 0:
        return 0
    points = registered - ranking + 1
    if ranking == 1:
        points += 2
    elif ranking <= 3:
        points += 1
    return points


def compute_standings(edition):
    """Standings of every active team and result of the edition."""
    teams = list(Team.objects.filter(edition=edition, is_active=True))
    results = list(
        TeamResult.objects.filter(
            discipline__edition=edition,
            discipline__is_active=True,
            team__is_active=True,
            is_active=True,
        ).select_related("discipline")
    )
    games = Game.objects.filter(
        discipline__edition=edition,
        discipline__is_active=True,
        round__is_active=True,
        is_active=True,
        is_played=True,
    ).values_list("discipline_id", "team1_id", "score1", "team2_id", "score2")

    differences = defaultdict(int)  # (discipline id, team id) -> points difference
    for discipline_id, team1_id, score1, team2_id, score2 in games:
        differences[(discipline_id, team1_id)] += score1 - score2
        differences[(discipline_id, team2_id)] += score2 - score1

    by_discipline = defaultdict(list)
    for result in results:
        by_discipline[result.discipline_id].append(result)

    result_standings = {}
    for discipline_results in by_discipline.values():
        result_standings.update(_rank_discipline(discipline_results, differences))

    totals = {team.id: 0 for team in teams}
    for result in results:
        if result.team_id in totals:
            totals[result.team_id] += result_standings[result.id].global_points

    # Same rule as Edition.ranking_is_manual, on the teams already loaded: keep both in step.
    if any(team.final_rank is not None for team in teams):
        team_standings = {team.id: TeamStanding(ranking=team.final_rank) for team in teams}
    else:
        team_standings = {
            team.id: TeamStanding(
                ranking=1 + sum(1 for other in totals.values() if other > totals[team.id]),
                total_points=totals[team.id],
            )
            for team in teams
        }

    return Standings(results=result_standings, teams=team_standings)


def _score_key(result, differences):
    """
    Sort key of a result, larger is better, or None when the result has no score for
    its discipline's type.
    """
    discipline = result.discipline
    if discipline.result_type == ResultTypes.POINTS:
        if result.points is None:
            return None
        return (result.points, differences[(discipline.id, result.team_id)])
    if discipline.result_type == ResultTypes.TIME:
        if result.time is None:
            return None
        clock = result.time
        seconds = clock.hour * 3600 + clock.minute * 60 + clock.second + clock.microsecond / 1e6
        return (-seconds,)
    return None


def _rank_discipline(results, differences):
    """ResultStanding of every result of one discipline (all rows share the discipline)."""
    discipline = results[0].discipline
    keys = {result.id: _score_key(result, differences) for result in results}
    scored = [key for key in keys.values() if key is not None]
    standings = {}
    for result in results:
        difference = differences[(discipline.id, result.team_id)]
        key = keys[result.id]
        if not discipline.reveal_score or key is None:
            standings[result.id] = ResultStanding(points_difference=difference)
            continue
        ranking = 1 + sum(1 for other in scored if other > key)
        standings[result.id] = ResultStanding(
            ranking=ranking,
            points_difference=difference,
            global_points=global_points(ranking, len(results)),
        )
    return standings
