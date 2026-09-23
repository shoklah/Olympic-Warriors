# Standings and Manual Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute an edition's standings (discipline ranks, points differences, global points, team totals and ranks) in one pass of three queries instead of hundreds, and let organisers record a finishing order per team for editions without result data.

**Architecture:** A new `olympic_warriors/standings.py` computes everything in Python from the edition's active teams, results and played games. The model properties keep their names and delegate to it; the summary serializer computes it once per request and reads from context. `Team.final_rank` plus `Edition.ranking_is_manual` switch the team ranking to the stored order with `null` totals. The front hides the points figure when the total is `null` and sorts a `null` rank last.

**Tech Stack:** Django 4.2 / DRF (tests through the compose stack), SvelteKit 2 / Vitest.

**Spec:** `docs/superpowers/specs/2026-09-23-standings-and-manual-ranking-design.md`

---

## Conventions for every task

- Work in the main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors` on branch `claude/standings` (from `dev`). Never switch branches, never `git stash`.
- Server commands run through the running compose stack, which mounts `./server`:
  `docker compose exec -T server python manage.py <command>`
- Front commands run in the front container (the host has no vitest binary):
  `docker compose exec -T front npm test`, `docker compose exec -T front npx vitest run <path>`, `docker compose exec -T front npm run build`
- Commit style: `[ADD]`, `[FIX]`, `[TEST]`, `[DOCS]` prefix, message ending with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Implementers run one at a time (shared git index).

## File map

| File | Change |
|---|---|
| `server/olympic_warriors/standings.py` | create: `compute_standings`, dataclasses |
| `server/olympic_warriors/tests/test_standings.py` | create |
| `server/olympic_warriors/models/Team.py` | `Team.final_rank`; properties delegate; `annotate_points_difference` removed |
| `server/olympic_warriors/models/Edition.py` | `ranking_is_manual` |
| `server/olympic_warriors/migrations/0031_team_final_rank.py` | generated |
| `server/olympic_warriors/admin.py` | `TeamAdmin` shows and edits `final_rank` |
| `server/olympic_warriors/serializer.py` | summary reads the standings from context |
| `server/olympic_warriors/tests/test_ranking.py` | the `annotate_points_difference` test replaced |
| `server/olympic_warriors/tests/test_summary.py` | manual edition payload, query count |
| `server/olympic_warriors/tests/test_transfer.py` | `final_rank` round trip |
| `front/src/lib/edition.js` | `rankedTeams` sorts `null` last |
| `front/src/lib/fixtures/summary.js` | `summaryManual` |
| `front/src/lib/edition.test.js` | `rankedTeams` with `null` |
| `front/src/routes/[year=year]/ranking/+page.svelte` + `page.test.js` | no `pts` on `null` |
| `front/src/routes/[year=year]/teams/[id]/+page.svelte` + `page.test.js` | no `pts` on `null` |
| `CLAUDE.md` | rankings paragraph |

---

### Task 0: Baseline

- [ ] **Step 1: Check the baseline is green**

```bash
docker compose exec -T server python manage.py test
docker compose exec -T front npm test
```
Expected: both pass (196 Django tests, 280 front tests at the time of writing). If not, stop and report.

---

### Task 1: Standings module

**Files:**
- Create: `server/olympic_warriors/standings.py`
- Create: `server/olympic_warriors/tests/test_standings.py`

The module reads the models through `apps.get_model()` so `models/Team.py` can import it lazily without a cycle.

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_standings.py`:

```python
"""
Tests for olympic_warriors.standings: one pass over an edition, nothing stored.
"""

from datetime import time

from django.test import TestCase

from olympic_warriors.models import (
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
        Relay.objects.filter(pk=hidden.pk).update(is_active=False)
        standings = compute_standings(self.edition)

        ghost_result = TeamResult.objects.get(team=self.ghost, discipline=self.darts)
        self.assertNotIn(ghost_result.id, standings.results)
        self.assertNotIn(self.result(self.team_a, hidden).id, standings.results)
        self.assertEqual(standings.result(ghost_result.id), ResultStanding())
        self.assertNotIn(self.ghost.id, standings.teams)
        self.assertEqual(standings.team(self.ghost.id), TeamStanding())


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
        self.play(self.team_a, 5, self.team_b, 2)  # darts: A 6, B 1, C 3 (tied 0 pts, rank 3), D 3
        relay = Relay.objects.create(edition=self.edition, reveal_score=True)
        TeamResult.objects.filter(discipline=relay, team=self.team_b).update(points=1)  # B 6
        standings = compute_standings(self.edition)

        self.assertEqual(standings.team(self.team_b.id), TeamStanding(1, 7))
        self.assertEqual(standings.team(self.team_a.id), TeamStanding(2, 6))
        self.assertEqual(standings.team(self.team_c.id), TeamStanding(3, 3))
        self.assertEqual(standings.team(self.team_d.id), TeamStanding(3, 3))

    def test_runs_in_three_queries(self):
        self.play(self.team_a, 5, self.team_b, 2)
        Relay.objects.create(edition=self.edition, reveal_score=True)

        with self.assertNumQueries(3):
            compute_standings(self.edition)


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
```

Arithmetic behind `test_totals_sum_global_points_and_rank_teams`: darts has 4 registered results; A rank 1 → 4-1+1+2 = 6; B rank 4 → 1; C and D have 0 points and difference 0 → rank 3 each → 4-3+1+1 = 3. Relay: only B scored → B rank 1 of 4 → 6; A, C, D unscored → 0. Totals: B 7, A 6, C 3, D 3.

- [ ] **Step 2: Run the tests to check they fail**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_standings
```
Expected: `ModuleNotFoundError: No module named 'olympic_warriors.standings'`. (The `final_rank` tests will fail until Task 2 adds the field; that is expected in this task.)

- [ ] **Step 3: Write the module**

Create `server/olympic_warriors/standings.py`:

```python
"""
Standings of an edition computed in one pass: discipline rankings, points differences,
global points, team totals and team ranks, from three queries and nothing stored.

The rules are the ones the model properties always applied:
- a result ranks only when its discipline is revealed and it has a score for its type;
  points disciplines rank by points then points difference, time disciplines by time;
  ties share a rank, unranked results have rank 0;
- global points reward the rank among the discipline's registered results, with a
  podium bonus; an unranked result earns nothing;
- a team's total is the sum of its global points, teams rank by total, ties shared;
- a manual edition (a team with a final_rank) ranks teams by that stored order instead,
  and has no totals.
"""

from collections import defaultdict
from dataclasses import dataclass

from django.apps import apps

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
    results: dict  # TeamResult id -> ResultStanding
    teams: dict  # Team id -> TeamStanding

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
    Team = apps.get_model("olympic_warriors", "Team")
    TeamResult = apps.get_model("olympic_warriors", "TeamResult")
    Game = apps.get_model("olympic_warriors", "Game")

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
```

- [ ] **Step 4: Run the tests**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_standings
```
Expected: every test passes except the two in `TestManualRanking`, which fail on `final_rank` (`FieldError` in the `update()`, or `AttributeError` in `compute_standings`) until Task 2 adds the field. Every other failure is a bug in the module. If `test_runs_in_three_queries` reports more than 3, the `select_related("discipline")` or the `values_list` is wrong; fix it.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/standings.py server/olympic_warriors/tests/test_standings.py
git commit -m "[ADD] standings: an edition's rankings and totals computed in one pass

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `Team.final_rank`, `Edition.ranking_is_manual`, delegating properties

**Files:**
- Modify: `server/olympic_warriors/models/Team.py`
- Modify: `server/olympic_warriors/models/Edition.py`
- Create (generated): `server/olympic_warriors/migrations/0031_team_final_rank.py`
- Modify: `server/olympic_warriors/tests/test_ranking.py`
- Modify: `server/olympic_warriors/tests/test_transfer.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_ranking.py`, delete the import line `from olympic_warriors.models.Team import annotate_points_difference` and replace the whole method `test_annotated_queryset_iterates_as_model_instances` (in the class that defines it) with:

```python
    def test_team_total_and_ranking_follow_the_standings(self):
        self.play(self.team_a, 5, self.team_b, 2)  # A rank 1 of 4 -> 6, B rank 4 -> 1, C/D rank 3 -> 3

        self.assertEqual(self.team_a.total_points, 6)
        self.assertEqual(self.team_b.total_points, 1)
        self.assertEqual(self.team_a.ranking, 1)
        self.assertEqual(self.team_c.ranking, 2)
        self.assertEqual(self.team_b.ranking, 4)

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
```

Append to `server/olympic_warriors/tests/test_transfer.py`:

```python
class TestFinalRankTransfer(TestCase):
    """Team.final_rank is an ordinary team field: exported and imported like the others."""

    def test_final_rank_round_trips(self):
        edition = build_edition(2023)
        Team.objects.filter(edition=edition, name="Red").update(final_rank=1)
        document = export_edition(2023)
        edition.delete()

        import_edition(document)

        self.assertEqual(Team.objects.get(edition__year=2023, name="Red").final_rank, 1)
        self.assertIsNone(Team.objects.get(edition__year=2023, name="Blue").final_rank)
```

- [ ] **Step 2: Run them to check they fail**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_ranking olympic_warriors.tests.test_transfer
```
Expected: failures on `final_rank` (`FieldError`/`TypeError`) and `ranking_is_manual` (`AttributeError`).

- [ ] **Step 3: Rewrite `models/Team.py`**

Replace the file's imports and `TeamResult`/`Team` bodies so the file reads as follows (the class docstrings and `__str__` stay; the whole file is given to avoid ambiguity):

```python
from django.db import models

from .Edition import Edition


class TeamResult(models.Model):
    """
    Team's score for an Discipline.
    """

    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name='registered_team')
    discipline = models.ForeignKey(
        "Discipline", on_delete=models.CASCADE, related_name='registered_to'
    )
    points = models.IntegerField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return (
            self.team.name + " - " + self.discipline.name + ' ' + str(self.discipline.edition.year)
        )

    @property
    def result_type(self) -> str:
        """
        Get the result type of the team in the discipline.
        """
        return self.discipline.result_type

    def _standing(self):
        """
        This result's row of the edition standings (see olympic_warriors.standings).
        Each access recomputes the edition: callers that need many rows should call
        compute_standings once and read from it.
        """
        from ..standings import ResultStanding, compute_standings

        if self.pk is None:
            return ResultStanding()
        return compute_standings(self.discipline.edition).result(self.pk)

    @property
    def points_difference(self) -> int:
        """
        Sum of the team's score minus its opponent's score over the active, played games
        of the discipline. 0 when the team has no game.
        """
        return self._standing().points_difference

    @property
    def ranking(self) -> int:
        """
        Ranking of the team in the discipline, 0 while the score is hidden or missing.
        Points disciplines break ties on points difference; teams still tied share a rank.
        """
        return self._standing().ranking

    @property
    def global_points(self) -> int:
        """
        Points the team earns towards the edition ranking from its rank in the discipline.
        """
        return self._standing().global_points


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    # Finishing order recorded by hand for an edition without result data. As soon as
    # one active team of an edition has one, the edition ranking is this order and the
    # totals are null (see olympic_warriors.standings).
    final_rank = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        """
        String representation of the object
        """
        return str(self.name)

    def _standing(self):
        """
        This team's row of the edition standings (see olympic_warriors.standings).
        """
        from ..standings import TeamStanding, compute_standings

        if self.pk is None:
            return TeamStanding()
        return compute_standings(self.edition).team(self.pk)

    @property
    def total_points(self):
        """
        Total global points of the team, None in a manual edition.
        """
        return self._standing().total_points

    @property
    def ranking(self):
        """
        Ranking of the team in the edition: computed from the totals, or the stored
        final_rank in a manual edition (None for a team without one).
        """
        return self._standing().ranking
```

Check with `grep -rn "annotate_points_difference\|cached_property" server/olympic_warriors --include='*.py'` that nothing else references the removed helper (the import in `test_ranking.py` was deleted in Step 1).

- [ ] **Step 4: Add `ranking_is_manual` to `Edition`**

In `server/olympic_warriors/models/Edition.py`, after `__str__`:

```python
    @property
    def ranking_is_manual(self) -> bool:
        """
        True when an active team of the edition carries a final_rank: the edition
        ranking is then that stored order, and totals are not shown.
        """
        return self.team_set.filter(is_active=True, final_rank__isnull=False).exists()
```

- [ ] **Step 5: Generate the migration**

```bash
docker compose exec -T server python manage.py makemigrations olympic_warriors --name team_final_rank
```
Expected: `0031_team_final_rank.py` with a single `AddField` on `team.final_rank` (`PositiveIntegerField(blank=True, null=True)`), depending on `0030_first_editions_disciplines` if that branch is merged, otherwise on `0029_game_score_labels`. Open it and check nothing else is in it.

- [ ] **Step 6: Run the server suite**

```bash
docker compose exec -T server python manage.py test
```
Expected: everything passes, including all of `test_standings`, the rewritten `test_ranking` tests and `test_transfer`. `test_summary` must pass unchanged: the summary still goes through the properties for now (slow, correct).

- [ ] **Step 7: Commit**

```bash
git add server/olympic_warriors/models/Team.py server/olympic_warriors/models/Edition.py server/olympic_warriors/migrations/0031_team_final_rank.py server/olympic_warriors/tests/test_ranking.py server/olympic_warriors/tests/test_transfer.py
git commit -m "[ADD] Team.final_rank and rankings delegating to the standings

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Summary serializer reads the standings once; admin edits `final_rank`

**Files:**
- Modify: `server/olympic_warriors/serializer.py` (`SummaryTeamSerializer`, `SummaryResultSerializer`, `EditionSummarySerializer.to_representation`)
- Modify: `server/olympic_warriors/admin.py` (`TeamAdmin`)
- Modify: `server/olympic_warriors/tests/test_summary.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/olympic_warriors/tests/test_summary.py` (the imports it needs, `SummarySetup`, `Team`, `TeamResult`, `Relay`, `TestCase`, are already at the top of the file):

```python
class TestManualRankingSummary(SummarySetup, TestCase):
    """A manual edition ranks teams by final_rank and sends no totals."""

    def setUp(self):
        super().setUp()
        Team.objects.filter(pk=self.team_b.pk).update(final_rank=1)
        Team.objects.filter(pk=self.team_a.pk).update(final_rank=2)

    def test_teams_carry_final_rank_and_null_totals(self):
        teams = {team["name"]: team for team in self.summary()["teams"]}

        self.assertEqual(teams["Bisons"]["ranking"], 1)
        self.assertEqual(teams["Aigles"]["ranking"], 2)
        self.assertIsNone(teams["Cerfs"]["ranking"])
        self.assertEqual({team["total_points"] for team in teams.values()}, {None})

    def test_results_are_still_ranked(self):
        results = {r["team"]: r for r in self.summary()["results"] if r["discipline"] == self.relay.id}

        self.assertEqual(results[self.team_b.id]["ranking"], 1)
        self.assertEqual(results[self.team_b.id]["global_points"], 5)


class TestSummaryQueryCount(SummarySetup, TestCase):
    """The summary computes the standings once; nothing fans out per team or result."""

    def test_summary_runs_in_a_fixed_number_of_queries(self):
        for _ in range(3):  # more results must not mean more queries
            Relay.objects.create(edition=self.edition, reveal_score=True)

        with self.assertNumQueries(SUMMARY_QUERIES):
            self.summary()
```

and near the top of the file, after the imports:

```python
# Queries of one summary: disciplines, teams, players prefetch, the three of the
# standings, results, rounds, games. Pin it so a per-row fan-out cannot come back.
SUMMARY_QUERIES = 9
```

- [ ] **Step 2: Run them to check they fail**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_summary.TestManualRankingSummary olympic_warriors.tests.test_summary.TestSummaryQueryCount
```
Expected: `TestSummaryQueryCount` fails with far more than 9 queries. `TestManualRankingSummary` may already pass through the properties; that is fine.

- [ ] **Step 3: Rewrite the three summary serializers**

In `server/olympic_warriors/serializer.py`, add `from .standings import compute_standings` to the imports.

Replace `SummaryTeamSerializer`'s docstring, `get_ranking` and `get_total_points`:

```python
class SummaryTeamSerializer(serializers.ModelSerializer):
    """
    A team's summary row. `ranking` and `total_points` come from the edition standings
    computed once by EditionSummarySerializer and handed in through context["standings"],
    instead of each team recomputing them. Both are null in a manual edition without a
    rank for this team (ranking) or for every team (total_points).
    """

    ranking = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    players = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "ranking", "total_points", "players")

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ranking(self, obj):
        return self.context["standings"].team(obj.id).ranking

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_total_points(self, obj):
        return self.context["standings"].team(obj.id).total_points

    @extend_schema_field(SummaryPlayerSerializer(many=True))
    def get_players(self, obj):
        return SummaryPlayerSerializer(obj.active_players, many=True).data
```

In `SummaryResultSerializer`, replace the three `IntegerField(read_only=True, allow_null=True)` declarations with method fields and add the accessor; the `to_representation` hiding logic stays as it is:

```python
    result_type = serializers.ReadOnlyField()
    ranking = serializers.SerializerMethodField()
    points_difference = serializers.SerializerMethodField()
    global_points = serializers.SerializerMethodField()

    def _standing(self, obj):
        """
        The result's standing: from context["standings"] inside the summary, computed
        for the one result otherwise (the organiser score endpoints return a single row).
        """
        standings = self.context.get("standings")
        if standings is None:
            standings = compute_standings(obj.discipline.edition)
        return standings.result(obj.id)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ranking(self, obj):
        return self._standing(obj).ranking

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_points_difference(self, obj):
        return self._standing(obj).points_difference

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_global_points(self, obj):
        return self._standing(obj).global_points
```

Update its class docstring's first sentence to: `A team's result in a discipline, its standing read from context["standings"] (see _standing).`

In `EditionSummarySerializer.to_representation`, replace
`totals = {team.id: team.total_points for team in teams}` with
`standings = compute_standings(instance)`, and the two context dicts:

```python
        staff_context = {"staff": bool(self.context.get("staff")), "standings": standings}
        return {
            "edition": SummaryEditionSerializer(instance).data,
            "disciplines": SummaryDisciplineSerializer(disciplines, many=True).data,
            "teams": SummaryTeamSerializer(
                teams, many=True, context={"standings": standings}
            ).data,
            "results": SummaryResultSerializer(results, many=True, context=staff_context).data,
            "rounds": SummaryRoundSerializer(rounds, many=True).data,
            "games": SummaryGameSerializer(games, many=True, context=staff_context).data,
        }
```

Check `grep -n "totals" server/olympic_warriors/serializer.py` returns nothing.

- [ ] **Step 4: Admin**

In `server/olympic_warriors/admin.py`, `TeamAdmin`:

```python
    list_display = ["name", "edition", "final_rank", "total_points", "ranking"]
    list_editable = ["final_rank"]
```

- [ ] **Step 5: Run the server suite and the query count**

```bash
docker compose exec -T server python manage.py test
```
Expected: all pass. If `TestSummaryQueryCount` reports a different count than 9, read the captured queries (`python manage.py shell` with `CaptureQueriesContext` on `EditionSummarySerializer(edition).data`), make sure none is per team or per result, and set `SUMMARY_QUERIES` to the exact measured number with the comment listing what they are.

- [ ] **Step 6: Measure on the dev database**

```bash
docker compose exec -T server python manage.py shell -c "
import time
from django.db import connection
from django.test.utils import CaptureQueriesContext
from olympic_warriors.models import Edition
from olympic_warriors.serializer import EditionSummarySerializer
for e in Edition.objects.filter(is_active=True).order_by('year'):
    with CaptureQueriesContext(connection) as ctx:
        t0=time.time(); EditionSummarySerializer(e).data; dt=time.time()-t0
    print(e.year, 'queries', len(ctx), 'ms', round(dt*1000))
"
```
Expected: about 9 queries and a few ms per edition (it was 398 queries / 430 ms for 2024). Report the numbers.

- [ ] **Step 7: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/admin.py server/olympic_warriors/tests/test_summary.py
git commit -m "[FIX] summary: standings computed once per request, final_rank editable in the admin

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Front: null rank and null total

**Files:**
- Modify: `front/src/lib/edition.js` (`byRankThenName`, line 6)
- Modify: `front/src/lib/fixtures/summary.js`
- Modify: `front/src/lib/edition.test.js`
- Modify: `front/src/routes/[year=year]/ranking/+page.svelte`, `page.test.js`
- Modify: `front/src/routes/[year=year]/teams/[id]/+page.svelte`, `page.test.js`

- [ ] **Step 1: Fixture**

Append to `front/src/lib/fixtures/summary.js`:

```js
/**
 * An old edition ranked by hand: Bisons first, Aigles second, Cerfs without a rank,
 * no totals, every result hidden.
 */
export const summaryManual = {
	...summary,
	edition: { ...summary.edition, year: 2022 },
	teams: [
		{ ...summary.teams[0], ranking: 2, total_points: null },
		{ ...summary.teams[1], ranking: 1, total_points: null },
		{ ...summary.teams[2], ranking: null, total_points: null }
	],
	disciplines: summary.disciplines.map((d) => ({ ...d, reveal_score: false })),
	results: summary.results.map((r) => ({
		...r,
		ranking: null,
		points: null,
		time: null,
		points_difference: null,
		global_points: null
	})),
	rounds: [],
	games: []
};
```

- [ ] **Step 2: Failing tests**

In `front/src/lib/edition.test.js`, import `summaryManual` alongside the other fixtures and add inside `describe('rankedTeams', …)`:

```js
	it('sorts an unranked team last', () => {
		expect(rankedTeams(summaryManual).map((t) => [t.name, t.ranking])).toEqual([
			['Bisons', 1],
			['Aigles', 2],
			['Cerfs', null]
		]);
	});
```

In `front/src/routes/[year=year]/ranking/page.test.js`, import `summaryManual` and add inside `describe('ranking page', …)`:

```js
	it('shows a hand-ranked edition without points', () => {
		renderWith(Page, { data: { summary: summaryManual } });

		const cards = screen.getAllByTestId('team-card');
		expect(cards[0]).toHaveTextContent(/^\s*1\s*Bisons\s*Chloé Nguyen\s*$/);
		expect(cards[1]).toHaveTextContent(/^\s*2\s*Aigles\s*Ana Lopez · Bob Martin\s*$/);
		expect(cards[2]).toHaveTextContent(/^\s*—\s*Cerfs\s*$/);
		expect(screen.queryByText(/pts/)).not.toBeInTheDocument();
		expect(cards[0]).toHaveClass('gold');
		expect(cards[2]).not.toHaveClass('bronze');
	});

	it('shows a hand-ranked edition without points in French', () => {
		renderWith(Page, { data: { summary: summaryManual } }, 'fr');

		expect(screen.getByRole('heading', { name: 'Classement' })).toBeInTheDocument();
		expect(screen.queryByText(/pts/)).not.toBeInTheDocument();
	});
```

In `front/src/routes/[year=year]/teams/[id]/page.test.js`, import `summaryManual` and add inside `describe('team page', …)`:

```js
	it('shows the rank alone on a hand-ranked edition', () => {
		renderWith(Page, { data: dataFor(1, summaryManual) });

		expect(screen.getByTestId('standing')).toHaveTextContent(/^\s*2nd\s*overall\s*$/);
	});

	it('shows a dash for a team without a rank, in French too', () => {
		renderWith(Page, { data: dataFor(3, summaryManual) }, 'fr');

		expect(screen.getByTestId('standing')).toHaveTextContent(/^\s*—\s*au général\s*$/);
		expect(screen.queryByText('pts')).not.toBeInTheDocument();
	});
```

Run:
```bash
docker compose exec -T front npx vitest run src/lib/edition.test.js "src/routes/[year=year]/ranking/page.test.js" "src/routes/[year=year]/teams/[id]/page.test.js"
```
Expected: the five new tests fail (`null pts` printed, `Cerfs` not last).

- [ ] **Step 3: Implement**

`front/src/lib/edition.js`, replace line 6:

```js
const rank = (team) => team.ranking ?? Number.POSITIVE_INFINITY; // no rank: sort last
const byRankThenName = (a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name);
```
(`Infinity - Infinity` is `NaN`, which is falsy, so two unranked teams fall through to the name.)

`front/src/routes/[year=year]/ranking/+page.svelte`, replace the `pts` span:

```svelte
				{#if team.total_points !== null}
					<span class="num pts">{team.total_points} {t('team.pts')}</span>
				{/if}
```

`front/src/routes/[year=year]/teams/[id]/+page.svelte`, replace the two spans after the `overall` label:

```svelte
		{#if data.team.total_points !== null}
			<span class="num points">{data.team.total_points}</span>
			<span class="label">{t('team.pts')}</span>
		{/if}
```

- [ ] **Step 4: Run all front tests and the build**

```bash
docker compose exec -T front npm test
docker compose exec -T front npm run build
```
Expected: all pass (the earlier ranking-page assertions with `5 pts` still hold), build OK.

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/edition.js front/src/lib/fixtures/summary.js front/src/lib/edition.test.js "front/src/routes/[year=year]/ranking" "front/src/routes/[year=year]/teams/[id]"
git commit -m "[FEAT] front: a hand-ranked edition shows ranks without points

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`, the "Domain:" paragraph under "Backend architecture" and the "Summary endpoint" paragraph.

- [ ] **Step 1: Rewrite the rankings sentence**

In the "Domain:" paragraph, replace the sentence starting `Rankings are computed properties on `TeamResult` and `Team`` (through `(never stored, so it cannot desync)`) with:

```
Rankings are never stored: `olympic_warriors/standings.py` computes an edition's whole standings in one pass (`compute_standings(edition)`: three queries, then discipline ranks gated by `Discipline.reveal_score`, points disciplines breaking ties on the points difference summed from active, played `Game` scores, global points with the podium bonus, team totals and ranks). `TeamResult.ranking`/`points_difference`/`global_points` and `Team.total_points`/`ranking` delegate to it, recomputing the edition on each access, so read many rows through `compute_standings` once, never through the properties in a loop. `Team.final_rank` (migration `0031`, `list_editable` in `TeamAdmin`) records a finishing order by hand for an edition without result data: once any active team of an edition has one (`Edition.ranking_is_manual`), the team ranking is that order (`None` for a team without) and every `total_points` is `None`.
```

In the "Summary endpoint" paragraph, replace `Team totals are computed once per request into a `totals` dict passed through serializer context: `Team.ranking` is quadratic, so never call it per team when serializing a list.` with:

```
The standings are computed once per request and passed through serializer context as `standings`; `SummaryResultSerializer` falls back to computing them for the single row the organiser score endpoints return. `test_summary.py` pins the query count of a summary, so a per-row fan-out fails the suite. In a manual edition `teams[].ranking` is the stored order (`null` for a team without one) and `teams[].total_points` is `null`; the front then hides the points figure.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOCS] CLAUDE.md: standings in one pass, manual ranking

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- Standings module, rules, dataclasses, `result()`/`team()` accessors: Task 1.
- Delegating properties, `annotate_points_difference` removed with its test replaced: Task 2.
- `Team.final_rank`, migration, `Edition.ranking_is_manual`, admin: Tasks 2 and 3.
- Summary reads standings once, results/teams nullable, staff hiding unchanged, single-row fallback for the organiser endpoints: Task 3.
- Query-count assertions: Task 1 (`assertNumQueries(3)`) and Task 3 (`SUMMARY_QUERIES`).
- Transfer round trip: Task 2.
- Front sort, both pages, fixture, English and French tests: Task 4.
- Docs: Task 5.
