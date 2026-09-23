# Player profiles: places per discipline and best discipline

## Goal

Step 2 of the player profiles roadmap (step 1: `2026-09-23-player-profiles-design.md`):
- show on each profile how the player's teams ranked in each discipline across editions;
- add a card naming the player's best discipline(s).

Nothing is stored.

## Definitions

- **Discipline place.** Take one of the player's counted participations (finished,
  ranked, at least two teams; see the step 1 spec). The discipline place is the rank of
  that participation's team in one of the edition's disciplines, from
  `compute_standings`. A result without a rank (discipline hidden, no score, no result
  type) gives no place. Each place keeps its year.
  - Unfinished editions give none: they aren't counted participations.
  - Today, 2021–2023 give none either, because their disciplines have no results.
- **Discipline identity across editions.** Disciplines are matched by `Discipline.name`,
  the name the model sets and the admin and scoring already rely on.
- **Discipline places of a person.** One entry per discipline name, with its places
  sorted best first (lower rank first; equal ranks newest first).
- **Order and position.** A person's disciplines are ordered with the leaderboard's
  medal-table rule:
  - more 1st places first, then more 2nd places, and so on;
  - an extra lower place counts in the discipline's favour;
  - identical places share a position, listed by name.

  `position` is the discipline's shared position among the person's own disciplines
  (1, 1, 3, …).
- **Best discipline(s).** The disciplines at position 1. There are none when the person
  has no discipline place.

## Backend

### `standings.py`

`compute_standings` already loads every result with its discipline, so exposing each
team's discipline results costs no query:

```python
@dataclass(frozen=True)
class DisciplineStanding:
    """A team's standing in one discipline of the edition."""
    discipline_id: int
    discipline_name: str
    standing: ResultStanding

@dataclass(frozen=True)
class Standings:
    results: dict[int, ResultStanding]
    teams: dict[int, TeamStanding]
    by_team: dict[int, tuple[DisciplineStanding, ...]] = field(default_factory=dict)

    def disciplines_of(self, team_id) -> tuple[DisciplineStanding, ...]
```

`by_team` holds the active results of active disciplines of active teams: the same rows
as `results`, ordered by discipline id. The query count stays at 3.

### `profiles.py`

- `Participation` gains `disciplines: tuple[DisciplinePlace, ...] = ()`, where
  `DisciplinePlace(name, year, rank)` is one ranked result of the participation's team.
  It is filled only for a participation that counts, from
  `standings.disciplines_of(team_id)`, keeping results whose `standing.ranking > 0`.
- `PlayerRecord` gains `disciplines: tuple[DisciplinePlaces, ...]`, where
  `DisciplinePlaces(name, places, position)` has its places sorted best first.
  The disciplines are ordered and positioned by the medal-table rule, with the name as
  tie-break.
- The medal key is written once, over a sequence of ranks, and serves both the
  leaderboard and the disciplines.
- No new query: `PROFILES_QUERIES` stays `2 + 3 × finished editions with players`.

### API

`GET /profile/<user_id>/` gains:

```json
"disciplines": [
  {"name": "Relay", "position": 1, "places": [{"year": 2025, "rank": 1}, {"year": 2024, "rank": 2}]},
  {"name": "Darts", "position": 2, "places": [{"year": 2024, "rank": 1}]}
]
```

`GET /profiles/` is unchanged.

## Front (`/players/<id>`)

- **Figures.** Two cards side by side, each capped at 14rem (grid
  `repeat(2, minmax(0, 14rem))`):
  - the average rank card, as today;
  - a best-discipline card:
    - label « Épreuve fétiche » / "Signature event", plural when there are several
      (« Épreuves fétiches » / "Signature events"; wording chosen by Hugo);
    - content: each best discipline's icon (`iconFor`) and translated name
      (`disciplineName`), at most 3, then "+N";
    - "—" when the player has no discipline place.
- **Section « Par épreuve » / "By discipline"**, after « Éditions ». It is only shown when
  there is at least one discipline.
  - One row per discipline, in the server's order. Each row has the icon, the translated
    name, and the places best first.
  - Each place is the rank as a `.num`, coloured gold, silver or bronze for 1–3 and
    `--muted` after, followed by the year, small and muted.
  - The figures are `aria-hidden`. A visually hidden sentence reads them instead
    (`players.placeIn`): "1re place en 2025, 2e place en 2024".
- **New keys:** `profile.bestDiscipline` (plural `{ one, other }`) and
  `profile.byDiscipline`.
- **New helper:** `bestDisciplines(disciplines, max = 3)` in `$lib/players` returns
  `{ shown, more, count }` for the entries at position 1.

## Testing

Server:
- `disciplines_of` returns the team's discipline standings with names, and `compute_standings`
  still runs 3 queries.
- A person's discipline places:
  - come from counted participations only: a running edition and a hidden discipline
    give none;
  - aggregate across editions by name;
  - are sorted best first;
  - disciplines are ordered by the medal table, and tied disciplines share position 1;
  - a person without places has `disciplines == ()`.
- `/profile/<id>/` carries `disciplines`, and the query pins still hold.

Front:
- `bestDisciplines`: none, one, a tie, and more than 3.
- Profile page:
  - the best-discipline card, singular and plural, with "—" when there is none;
  - the section rows read like `Relay 1 2025 2 2024` with the spoken sentence;
  - the section is absent without disciplines;
  - one French test (« Relais », « Épreuve fétiche », « Par épreuve »).

## Out of scope

- Per-discipline leaderboards across players.
- Team counts per discipline.
- Per-edition discipline breakdowns (the team page has them).
