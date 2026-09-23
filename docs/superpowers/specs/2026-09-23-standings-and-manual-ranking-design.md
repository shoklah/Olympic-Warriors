# Standings in one pass, and a manual ranking for old editions

## Goals

1. **Performance.** The summary endpoint of a small edition (8 teams, 6 disciplines) runs
   ~400 queries in ~430 ms, because `TeamResult.ranking` re-counts the other results of its
   discipline and `Team.total_points` walks every result, each with its own queries. It
   grows with teams × disciplines × teams. Compute the standings of an edition once, from a
   handful of queries, and store nothing.
2. **Manual ranking.** The first editions have no result data, only a finishing order.
   Let an organiser record that order per team in the admin, and have the ranking page
   show it, without points.

## Standings module

`olympic_warriors/standings.py` exposes:

```python
@dataclass(frozen=True)
class ResultStanding:
    ranking: int             # 0 when hidden or without a score (same as today)
    points_difference: int   # 0 without played games
    global_points: int       # 0 when ranking is 0

@dataclass(frozen=True)
class TeamStanding:
    ranking: int | None      # None: manual edition, team without final_rank
    total_points: int | None # None: manual edition

@dataclass(frozen=True)
class Standings:
    results: dict[int, ResultStanding]   # by TeamResult id
    teams: dict[int, TeamStanding]       # by Team id

def compute_standings(edition) -> Standings
```

`compute_standings` fetches, for the edition, the active teams, the active `TeamResult`s of
active disciplines whose team is active (with the discipline), and the active, played games
of active rounds, then computes everything in Python:

- `points_difference` per result: sum over the team's played games in the discipline of own
  score minus opponent score (the current `annotate_points_difference` rule).
- `ranking` per result, per discipline, with the current rules: 0 when `reveal_score` is
  off, when the result has no score for its type (`points` null for a points discipline,
  `time` null for a time one) or when the result type is `NONE`; otherwise 1 + the number of
  results ahead, ahead meaning more points or equal points and larger points difference for
  a points discipline, and a smaller time for a time one. Ties share a rank.
- `global_points` per result: 0 when ranking is 0; otherwise
  `registered - ranking + 1`, plus 2 for rank 1 and plus 1 for ranks 2 and 3, where
  `registered` is the number of active results of the discipline (current rule).
- Team `total_points`: sum of its results' `global_points`; team `ranking`: 1 + the number
  of teams with more points, ties share a rank.
- **Manual edition** (`edition.ranking_is_manual`): team `ranking` is `Team.final_rank`
  (`None` for a team without one) and `total_points` is `None` for every team. Results are
  still computed as above; they are simply not what the team ranking is built from.

The model properties keep their names and semantics but delegate:
`TeamResult.ranking`, `TeamResult.points_difference`, `TeamResult.global_points`,
`Team.total_points`, `Team.ranking` each call `compute_standings(edition)` and read their
row. They stay correct for the admin and the older endpoints, at the cost of one standings
computation per call, which is still far cheaper than today. A row missing from the
standings (inactive team, inactive discipline, unsaved object) yields the zero/`None`
values above. `annotate_points_difference` goes away with its test, replaced by the
standings tests.

## Manual ranking

- `Team.final_rank`: `PositiveIntegerField(null=True, blank=True)`, migration `0031`.
  Ties allowed, no uniqueness. `export_edition`/`import_edition` carry it like any team field.
- `Edition.ranking_is_manual` (property): true when any active team of the edition has a
  `final_rank`.
- `TeamAdmin`: `final_rank` in `list_display` and `list_editable`, next to the computed
  `total_points` and `ranking` columns (which show `-` for `None`).

## Summary endpoint

`EditionSummarySerializer.to_representation` calls `compute_standings(instance)` once and
passes it through context. `SummaryTeamSerializer` reads `ranking` and `total_points` from
it (both nullable in the schema). `SummaryResultSerializer` reads `ranking`,
`points_difference` and `global_points` from it instead of the instance properties; the
hiding rules (`reveal_score`, missing score, staff view) do not change.

## Front

- `rankedTeams`: a `null` ranking sorts last, ties by name.
- Ranking page: the `pts` figure is omitted when `total_points` is `null`; `MedalRank`
  already prints `—` for a `null` rank and the medal classes simply do not apply.
- Team page: the points figure in the header is omitted when `total_points` is `null`;
  the ordinal medal shows `—` for a `null` rank.
- Fixture `summaryManual` in `front/src/lib/fixtures/summary.js`: an edition with
  `final_rank`s, one team without, all `total_points` null.

## Testing

Server:
- `tests/test_standings.py`: `compute_standings` on an edition with a revealed points
  discipline with games (tie broken on points difference), a time discipline, an unrevealed
  discipline (ranking 0, global 0), a result without score, an inactive team and an inactive
  discipline (absent), and the manual case (stored ranks, `None`s, an unranked team). Assert
  the query count with `assertNumQueries` so the fan-out cannot come back.
- Existing `test_ranking.py` and `test_summary.py` keep passing through the delegating
  properties; the `annotate_points_difference` test is replaced by a standings one.
- `test_summary.py`: the payload of a manual edition (`ranking` from `final_rank`,
  `total_points` null, unranked team null) and a query-count assertion on the summary.
- `test_transfer.py`: `final_rank` survives an export/import round trip.

Front: `rankedTeams` with null ranks; ranking page and team page on `summaryManual`, in
English and French, asserting no `pts` text and the `—` rank.

## Out of scope

- Storing standings in the database.
- An organiser control for `final_rank` outside the admin.
- Manual per-discipline results for editions without data (they stay null and hidden).
