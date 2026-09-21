# General Culture Quizz and Darts disciplines — design

Date: 2026-09-18

## Goal

Add two disciplines to the backend so organisers can create them for an edition
from the Django admin:

- **General Culture Quizz**: points entered by hand. Live scoring is handled by
  an external quiz platform, so the app only stores the final score per team.
- **Darts**: team-vs-team games scheduled and scored by the existing
  `Discipline` / `TeamSportRound` / `Game` machinery.

Backend only. No icons, no front changes, no dedicated views or serializers.

## Models

Both follow the minimal pattern in `server/olympic_warriors/models/Relay.py`:
subclass `Discipline`, override `save()` to set `name` and `result_type` when
`self.pk is None`, then call `super().save()`.

### `models/GeneralCultureQuizz.py`

- `class GeneralCultureQuizz(Discipline)`
- `name = 'General Culture Quizz'`, `result_type = ResultTypes.POINTS`
- `pairing_system` is left at its default (`NONE`), so the base class creates
  one `TeamResult` per active team and schedules nothing.

### `models/Darts.py`

- `class Darts(Discipline)`
- `name = 'Darts'`, `result_type = ResultTypes.POINTS`
- No pairing system is forced. The organiser picks Round Robin or Swiss on the
  admin form, exactly as for `Rugby` and `Dodgeball`. `max_rounds` may be left
  empty: round robin defaults it to a full round robin (team count minus one
  rounds, or the team count when odd) and Swiss to log2 of the team count,
  rounded up. The base `Discipline.save()` then schedules rounds and games with
  referees, and `Game.save()` rolls win/draw/loss points into
  `TeamResult.points`. The pairing system can also be set later on a
  discipline that has no round yet; saving it then schedules the games.
- No `GameEvent` subclass. `GameAdmin.get_inline_instances` matches on the
  discipline name and will show no per-player inline for darts games, which is
  the intended behaviour.

## Wiring

- Export `GeneralCultureQuizz` and `Darts` from `models/__init__.py`.
- `site.register(GeneralCultureQuizz, DisciplineAdmin)` and
  `site.register(Darts, DisciplineAdmin)` in `admin.py`.
- One migration per discipline, generated with `makemigrations`:
  `0025_generalculturequizz.py` then `0026_darts.py`. Each holds a single
  `CreateModel` carrying only the `discipline_ptr` one-to-one link, matching
  migration 0024. Separate migrations let each discipline land green on its own.

## Naming

The discipline `name` string is what admin code matches on and what the front's
`cleanString()` turns into an icon key, so it is fixed here:

| Discipline | `name`                  | Class                 | Future icon key       |
|------------|-------------------------|-----------------------|-----------------------|
| Quiz       | `General Culture Quizz` | `GeneralCultureQuizz` | `Generalculturequizz` |
| Darts      | `Darts`                 | `Darts`               | `Darts`               |

## Tests

New module `server/olympic_warriors/tests/test_disciplines.py`, using Django's
`TestCase` against the Postgres container.

Shared setup: one edition, six active teams, one inactive team. Six gives a
realistic edition: two simultaneous games and two referee teams per round.

Cases:

1. **Quiz creation.** Creating a `GeneralCultureQuizz` sets `name` and
   `result_type`, creates a `TeamResult` with `points == 0` for each of the six
   active teams and none for the inactive team, and creates no
   `TeamSportRound` or `Game`.
2. **Darts scheduling.** Creating a `Darts` with
   `pairing_system = ROUND_ROBIN` creates five rounds (`max_rounds` defaults to
   team count minus one) and fifteen games, one per pair of teams, and every
   `Game` belongs to that discipline with a referee that is neither `team1` nor
   `team2`.
3. **Darts scoring.** The existing `Game.save()` treats a freshly scheduled
   0-0 game as a draw and gives both teams one point at creation. Editing one
   scheduled darts game to `score1 > score2` then moves `team1`'s result up by
   two and `team2`'s down by one relative to the post-scheduling baseline, so
   that game ends up contributing three points to the winner and none to the
   loser.
4. **Idempotent resaves.** Saving an existing quiz or darts discipline again
   (for example to toggle `reveal_score`) creates no extra team results, rounds
   or games and leaves every team's points unchanged. A darts discipline left
   on the default pairing system schedules nothing.

## Out of scope

- Icons and the front's hard-coded icon map. Six existing disciplines already
  render without an icon; this will be handled in a later front pass.
- Views, serializers, URL entries.
- Scheduler fixes. When this spec was written `schedule_round_robin_games`
  raised `ZeroDivisionError` with exactly two active teams and
  `tests/test_players.py` failed with a 401 because of the decorator-ordering
  bug in `views.py`. Both have since been fixed on `dev` (see follow-ups); the
  full suite is expected to pass.

## Running the tests

The worktree has no `server/dev.env` (gitignored). Copy it from the main
checkout, then:

```bash
docker compose up -d db server
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

## Follow-ups surfaced during review

Fixed after this spec was written, on `dev`:

- **Round-robin schedule is unbalanced.** `schedule_round_robin_games` kept the
  first team pinned while rotating the others and created only
  `len(teams) // 3` games per round, so with six teams the first team played
  all five rounds while every other team played three, only 10 of the 15
  pairings happened, and the pinned team started with more points. The
  scheduler now builds a full circle-method round robin (with a bye when the
  team count is odd) and plays every pairing of a round in batches of
  simultaneous games refereed by the teams left over. Six teams give five
  rounds, fifteen games and five games per team; two teams no longer divide by
  zero. The darts test asserts the full round robin.
- **Scheduling only happens on first save.** `Discipline.save()` now also
  schedules when `pairing_system` changes away from `None` on a discipline that
  has no active round yet, registering teams that joined the edition in the
  meantime. Changing the pairing system once rounds exist schedules nothing.
- **Unpinned dependencies break a fresh image.** `server/requirements.txt` now
  pins every dependency, with Django 4.2.19 and DRF 3.15.2 matching the
  long-running container. `dev` already had the `@permission_classes` order
  fixed, so the pins are there for reproducibility.
- **Swiss pairing crashes when `max_rounds` is empty.** `schedule/swiss.py`
  now defaults `max_rounds` to log2 of the team count, rounded up, and stores
  it on the discipline. It also stops after `max_rounds` rounds instead of
  `max_rounds + 1`.

Still open:

- **Icons.** No SVG for `Generalculturequizz` or `Darts` in
  `front/src/lib/img/icons/`, and the front's icon map is hard-coded; six older
  disciplines are in the same state. To be handled in a later front pass.
- **Resaving a round-robin discipline nulls `max_rounds`.** The scheduler
  writes `max_rounds` on a separately fetched `Discipline` instance, so the
  caller's instance still holds `None`; any later `save()` from that instance
  (or from the admin form loaded before scheduling) overwrites the column with
  `None`. Cosmetic today because `max_rounds` is only read at scheduling time.
