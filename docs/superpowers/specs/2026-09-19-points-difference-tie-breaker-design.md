# Points difference tie-breaker — design

Date: 2026-09-19

## Goal

Rank teams that have the same number of league points in a discipline by their
points difference, so that two teams tied on wins no longer share a rank (and
no longer both collect the rank-1 bonus in the global ranking). Applies to
every points-based discipline that has games, which today means Rugby,
Dodgeball, Basketball and Darts.

## Current behaviour

- `TeamResult.ranking` (in `server/olympic_warriors/models/Team.py`) is one plus
  the number of active results in the discipline with strictly more points, so
  tied teams share a rank.
- `Game.save()` rolls league points (3 win, 1 draw, 0 loss) into
  `TeamResult.points` as deltas. Game scores stay on `Game.score1` /
  `Game.score2`; no points difference is stored anywhere.
- The discipline ranking page in the front shows results in API order.
- The Swiss scheduler orders teams by league points only.

## Decisions

- **Scope:** every discipline whose `result_type` is `POINTS`. The difference is
  derived from the discipline's active games, so a discipline with no games
  yields 0 for every team and its ranking is unchanged.
- **Residual ties:** teams with equal points and equal difference keep a shared
  rank, exactly as today. No further tie-breaker.
- **Exposure:** the difference is a read-only API field and is shown on the
  discipline ranking page.
- **Swiss pairing:** unchanged. The scheduler keeps ordering by points only.
- **Storage:** derived on the fly, no new column, no migration. It cannot drift
  from the game scores the way the delta-maintained `points` can.

## Backend (`server/olympic_warriors/models/Team.py`)

### `annotate_points_difference(queryset)`

Module-level helper that annotates a `TeamResult` queryset with an integer
`points_difference`. It fetches `Game` through `apps.get_model` to avoid the
circular import with `Discipline.py`, and builds two subqueries:

- games where `team1` is the result's team and `discipline` is the result's
  discipline: `Sum(score1 - score2)`
- games where `team2` is the result's team, same discipline:
  `Sum(score2 - score1)`

Both are filtered on `is_active=True`, wrapped in `Coalesce(..., 0)`, and added
together. Games use `OuterRef("team_id")` and `OuterRef("discipline_id")`. The
result is a single query for the whole discipline.

### `TeamResult.points_difference` property

Runs the helper on the result's own row and returns the integer. It is a plain
statistic and does not check `reveal_score`.

### `TeamResult.ranking`

For `ResultTypes.POINTS`, the rank becomes one plus the count of active results
in the discipline that satisfy:

    points > self.points
    OR (points = self.points AND points_difference > self.points_difference)

The `reveal_score` gate (return 0) and the `TIME` branch are unchanged.
`global_points` reads `ranking` and needs no change. `Team.ranking`,
`Game.save()` and the schedulers are untouched.

## API

`TeamResultSerializer` in `server/olympic_warriors/serializer.py` gains
`points_difference = serializers.ReadOnlyField()`. Every results endpoint
returns it next to `ranking` and `global_points`. No view or URL changes.

## Front (`front/src/routes/disciplines/[slug]/ranking/`)

- `+page.server.js`: sort the enriched results by `ranking` ascending before
  returning them, so the list order matches the rank numbers.
- `+page.svelte`: for points disciplines, show the difference after the points
  with an explicit sign, e.g. `9 pts (+12)`, `9 pts (0)`, `6 pts (-4)`. Time
  disciplines are untouched.

## Tests

New `server/olympic_warriors/tests/test_ranking.py`, using the existing edition
and team fixtures and a `Darts` discipline with round robin pairing so games
exist without per-player events. Scores are set directly on `Game` rows and
saved, which rolls league points through the existing path. Cases:

- `points_difference` sums games played as team1 and as team2, and is 0 for a
  team with no games.
- Two teams with equal league points are ordered by difference; the one behind
  gets the next rank.
- Equal points and equal difference share a rank, and the following team skips
  a place (1, 1, 3).
- A discipline without games (e.g. `GeneralCultureQuizz`) still ranks on points
  alone.
- `reveal_score = False` still yields rank 0.
- The serializer output includes `points_difference`.

## Known caveat

Soft-deleting a game (`is_active = False`) removes it from the points difference
but leaves the league points that `Game.save()` already rolled into
`TeamResult.points`. That is the existing delta-maintenance weakness described
in `CLAUDE.md`, not something this feature changes.

## Out of scope

- Swiss pairing order.
- Head-to-head or points-scored tie-breakers.
- Storing the difference on `TeamResult`.
