# League points from played games — design

Date: 2026-09-22

## Goal

Stop counting unplayed games in the league points of a team-sport discipline,
and stop maintaining those points as deltas. `TeamResult.points` for a game
discipline is recomputed from the discipline's played games every time a game
is saved. Follow-up to the schedule-and-games spec
(`2026-09-22-schedule-and-games-design.md`), which recorded this as accepted
debt.

## Current behaviour

- `Game.save()` compares the new scores with the stored row and applies
  deltas to both teams' `TeamResult.points` (3 win, 1 draw, 0 loss). On
  creation it grants the result of the initial scores, so every scheduled
  0-0 game hands both teams a draw point before anyone has played.
- `Game.is_played` (since migration 0028) is display-only; the points ignore
  it. A score edited outside `Game.save()` desyncs the points permanently.
- `annotate_points_difference()` sums score gaps over every active game,
  played or not.
- On the real data (2024 Rugby and Dodgeball, 2026 Rugby and Darts, all games
  played) the stored points equal a recompute from the games exactly, so the
  switch changes no existing number.

## Decisions

- **Rule:** a team's league points in a discipline are 3 per win, 1 per draw
  and 0 per loss over the discipline's active, played games. Unplayed games
  contribute nothing, whatever their scores say.
- **Recompute, not deltas.** `Game.save()` recomputes the points of every team
  the game touches (its current teams, and its previous teams when a team was
  changed) from scratch after saving. Score edits, flag flips, team swaps and
  soft deletes all go through the same path, and a stale value cannot survive
  the next save.
- **Points difference** counts played games only, the same rule.
- **No migration.** The data already matches the rule.
- **Manual disciplines are untouched.** Recomputing only happens when a game
  is saved, so disciplines without games keep their hand-entered points.

## Backend (`server/olympic_warriors/models/`)

### `Game` (`Discipline.py`)

- `_update_points` is removed.
- New `league_points(team)` classmethod-style helper: over
  `Game.objects.filter(discipline=..., is_active=True, is_played=True)` where
  the team is `team1` or `team2`, sum 3 for a win, 1 for a draw.
- `save()`: remember the previous `team1_id`/`team2_id` when the row exists,
  call `super().save()`, then for each distinct team id among the previous and
  current pair, `TeamResult.objects.filter(team_id=..., discipline=self.discipline)
  .update(points=<recomputed>)`. A missing result row (team registered after
  the discipline) is skipped rather than raising.
- Everything else in `save()` (nothing else today) stays.

### `annotate_points_difference` (`Team.py`)

- The game subquery gains `is_played=True`.

## Tests

New `tests/test_points.py` on a Darts discipline with three teams and one
round:

- creating an unplayed game leaves both teams at 0;
- marking it played grants 3/0 for a win and 1/1 for a draw;
- unmarking removes the points;
- editing the scores of a played game recomputes (a win turned into a loss
  moves 3 points across);
- editing the scores of an unplayed game changes nothing;
- soft-deleting a played game removes its points;
- moving a played game to another team recomputes the old and the new team;
- `points_difference` ignores unplayed games.

Existing tests: `test_ranking.py`'s `play()` helper creates played games;
`test_disciplines.py`'s roll-up test asserts the new semantics (scheduled
games grant nothing, a played 3-1 grants 3/0). The admin changelist test in
`test_summary.py` already expects 3/3/0 after playing two games, which the
new rule also yields.

## Docs

CLAUDE.md: the domain paragraph describes points as recomputed from played
games (no more "as deltas" nor the draw-point caveat); the schedule spec's
"out of scope" note is superseded by this spec.
