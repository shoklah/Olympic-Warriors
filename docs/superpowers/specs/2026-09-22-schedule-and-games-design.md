# Schedule and games — design

Date: 2026-09-22

## Goal

Show the schedule of team-sport disciplines in the front: which teams play
whom in which round, who referees, and the score once the game is played.
Both audiences matter equally: a player finding their next game on the team
page, and a spectator following a discipline on its page. Follow-up to the
edition-aware frontend spec (`2026-09-22-edition-aware-frontend-design.md`).

## Current behaviour

- `TeamSportRound` (discipline, `order`, `is_over`) and `Game` (discipline,
  round, `team1`, `score1`, `team2`, `score2`, `referees`, edition) exist and
  are filled by the round-robin and Swiss schedulers. `Game.save()` rolls
  score changes into `TeamResult.points` as deltas.
- A game has no status: scores default to 0 and 0, and organisers deliberately
  mix rounds on the day so players can rest, so `round.is_over` does not say
  whether a given game was played.
- Games and rounds are only reachable through authenticated endpoints, and the
  front shows nothing about them.
- `GameEvent`s (per-player actions) exist in the model but no edition has any.

## Decisions

- **Both views:** the discipline page gets the full schedule by round; the team
  page gets that team's games and refereeing duties per discipline. Same rows,
  filtered differently.
- **Data:** the public summary payload gains `rounds` and `games`; no new
  endpoint.
- **Reveal:** while a discipline's `reveal_score` is off, games keep their
  pairings, referee and played flag but `score1` and `score2` are null.
- **Played state:** a new `Game.is_played` boolean, set by hand in the admin
  changelist, editable in place next to the scores. Two states only.
- **Backfill:** every existing game is marked played by the migration, since
  every edition in the database (2024, 2026) is over.
- **Out of scope:** per-player events, live "in progress" state, kick-off
  times, pitches, highlighting a current round.

## Backend

### `Game` model (`server/olympic_warriors/models/Discipline.py`)

- `is_played = models.BooleanField(default=False)`.
- Migration `0028_game_is_played`: `AddField` with default False, then a
  `RunPython` step that sets `is_played=True` on every existing game (reverse:
  no-op). New games created by the schedulers start unplayed.
- `GameAdmin` (`admin.py`): add `"is_played"` to `list_display` after
  `"score2"` and set `list_editable = ["score1", "score2", "is_played"]`, so a
  game is closed with one click in the changelist. `list_display` must start
  with a non-editable column (it does, `discipline`).
- `Game.save()` is unchanged; `is_played` has no side effect.
- Transfer tooling serializes `_meta.concrete_fields`, so the field rides
  along; an older export without it imports with the default.

### Summary payload (`serializer.py`)

Two arrays added to `EditionSummarySerializer`, active rows only:

```json
"rounds": [{"id", "discipline", "order", "is_over"}],
"games":  [{"id", "discipline", "round", "team1", "team2", "referees",
            "is_played", "score1", "score2"}]
```

- `rounds`: `TeamSportRound.objects.filter(discipline__edition=edition,
  discipline__is_active=True, is_active=True).order_by("discipline_id",
  "order")`.
- `games`: `Game.objects.filter(discipline__edition=edition,
  discipline__is_active=True, round__is_active=True, is_active=True,
  team1__is_active=True, team2__is_active=True)
  .select_related("discipline", "round").order_by("round__order", "id")`.
  A game whose referee team is inactive is kept; the front shows "Unknown".
- `SummaryGameSerializer.to_representation`: when
  `instance.discipline.reveal_score` is False, `score1` and `score2` are null.
  Declared `IntegerField(read_only=True, allow_null=True)` so the schema says
  so.
- `SummaryRoundSerializer` is a plain `ModelSerializer`.

### Tests (`tests/test_summary.py`)

A `ScheduleSetup` mixin extends `SummarySetup` with a revealed `Darts`
discipline (two rounds, three games among the three teams, one of them an
unplayed 0-0) and a hidden `Petanque` discipline (one round, one played game)
for the "hidden score" case. It is separate so the existing ranking
assertions are untouched by the league points those games add. Cases:

- rounds present, in `(discipline, order)` order, with `is_over`;
- games present in `(round order, id)` order with both teams, referee,
  `is_played` and scores for the revealed discipline;
- the hidden discipline's game has `score1`/`score2` null but keeps its
  pairing, referee and `is_played`;
- an inactive round's games and an inactive game are excluded;
- the migration backfill: a game created before the migration is
  `is_played=True` after it (tested with `MigrationExecutor` or, simpler, by
  asserting the data function marks a fixture game).

## Frontend

### Helpers (`front/src/lib/edition.js`, pure, tested)

- `disciplineSchedule(summary, disciplineId)` → `null` when the discipline
  has no rounds, else `[{order, isOver, games: [{id, team1Id, team1Name,
  team2Id, team2Name, refereeName, isPlayed, score1, score2}]}]` in round
  order. Team names default to `'Unknown'`.
- `teamGames(summary, teamId)` → `[{disciplineId, disciplineName, games:
  [...]}]` for disciplines where the team plays or referees at least one game,
  in discipline id order; each game row: `{id, round, role: 'play' |
  'referee', opponentId, opponentName, team1Name, team2Name, isPlayed,
  ownScore, theirScore, result: 'win' | 'loss' | 'draw' | null}`. `result` is
  null unless the game is played and both scores are numbers; for referee
  rows `ownScore`/`theirScore`/`result` are null and `opponent*` are null.

### Discipline page (`routes/[year=year]/disciplines/[id]`)

`+page.js` adds `schedule: disciplineSchedule(summary, discipline.id)`. The
page renders, after the ranking (or after the "Results not revealed yet"
line), a `Schedule` heading and one block per round: `Round N`, then each
game as a row `Team A  12 – 9  Team B` with `ref: Team C` beneath, or `Team A
—  Team B` when unplayed or unrevealed. No section when `schedule` is null.
Team names link to the team pages.

### Team page (`routes/[year=year]/teams/[id]`)

`+page.js` adds `games: teamGames(summary, team.id)`. Below the results
table, one block per discipline: heading with the discipline name, then rows
`Round 2 · vs Bisons · 12 – 9 · won`, `Round 3 · vs Cerfs · to play`, or
`Round 1 · referee · Aigles vs Cerfs`. Rows are not styled by result beyond
the word.

### Fixture and tests

`fixtures/summary.js` gains `rounds` (two for Relay, one for Orienteering)
and `games` (Relay: round 1 Bisons 12–9 Aigles ref Cerfs played, round 1
Cerfs 0–0 Bisons ref Aigles unplayed, round 2 Aigles 7–7 Cerfs ref Bisons
played; Orienteering round 1 Aigles vs Bisons ref Cerfs scores null).
`summaryAllRevealed` reveals the Orienteering game score 3–1.

- `edition.test.js`: `disciplineSchedule` order, names, null for a discipline
  without rounds, null scores when hidden; `teamGames` play and referee rows,
  own score first for a team2 side, win/loss/draw/null, disciplines without
  games omitted.
- Page tests: the discipline page shows the round blocks and the dash for an
  unplayed game; the team page shows a `won`, a `to play` and a `referee` row.

### Docs

CLAUDE.md: the two arrays and their reveal rule in the summary paragraph;
`Game.is_played` and the admin `list_editable` in the domain paragraph;
`disciplineSchedule`/`teamGames` in the helpers list.
