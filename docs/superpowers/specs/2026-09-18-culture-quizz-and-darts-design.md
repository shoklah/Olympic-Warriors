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
  admin form, exactly as for `Rugby` and `Dodgeball`. The base
  `Discipline.save()` then schedules rounds and games with referees, and
  `Game.save()` rolls win/draw/loss points into `TeamResult.points`.
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
   team count minus one), and every `Game` belongs to that discipline with a
   referee that is neither `team1` nor `team2`.
3. **Darts scoring.** The existing `Game.save()` treats a freshly scheduled
   0-0 game as a draw and gives both teams one point at creation. Editing one
   scheduled darts game to `score1 > score2` then moves `team1`'s result up by
   two and `team2`'s down by one relative to the post-scheduling baseline, so
   that game ends up contributing three points to the winner and none to the
   loser.

## Out of scope

- Icons and the front's hard-coded icon map. Six existing disciplines already
  render without an icon; this will be handled in a later front pass.
- Views, serializers, URL entries.
- Pre-existing scheduler bug: `schedule_round_robin_games` raises
  `ZeroDivisionError` with exactly two active teams, because
  `len(teams) // 3` simultaneous games is zero and the guard only rejects fewer
  than two. Not touched here.
- Pre-existing test failure: `tests/test_players.py` gets a 401 because of the
  decorator-ordering bug documented in `CLAUDE.md`. The full suite is expected
  to show that one failure alongside the new passing tests.

## Running the tests

The worktree has no `server/dev.env` (gitignored). Copy it from the main
checkout, then:

```bash
docker compose up -d db server
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

## Follow-ups surfaced during review (not addressed here)

- **Round-robin schedule is unbalanced.** `schedule_round_robin_games` keeps
  the first team pinned in `l1[0]` while rotating the others and creates only
  `len(teams) // 3` games per round, so with six teams the first team plays all
  five rounds while every other team plays three, and only 10 of the 15
  pairings happen. Since `Game.save()` credits one point per team at creation,
  the pinned team starts with more points. Affects every game-based discipline,
  not just darts. The darts test pins this behaviour with an explanatory
  comment rather than endorsing it.
- **Scheduling only happens on first save.** A discipline created with pairing
  system `None` can never be scheduled afterwards from the admin; it must be
  deleted and recreated. Consider re-dispatching when `pairing_system` changes
  away from `None`, or making the field read-only after creation.
- **Unpinned dependencies break a fresh image.** `server/requirements.txt`
  pins nothing. A fresh build in September 2026 pulls a Django REST Framework
  release that turns the documented `@permission_classes` ordering bug in
  `views.py` into a hard `TypeError` at boot. The main checkout's long-running
  container is on Django 4.2.19 and DRF 3.15.2. Either pin those versions or fix
  the decorator order.
- **Icons.** No SVG for `Generalculturequizz` or `Darts` in
  `front/src/lib/img/icons/`, and the front's icon map is hard-coded; six older
  disciplines are in the same state. To be handled in a later front pass.
