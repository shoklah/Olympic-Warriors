# General Culture Quizz and Darts Disciplines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two `Discipline` subclasses, `GeneralCultureQuizz` (hand-entered points) and `Darts` (team-vs-team games via the existing scheduler), with admin registration, migrations and the repo's first discipline tests.

**Architecture:** Each discipline is a Django multi-table-inheritance subclass of `Discipline` whose `save()` sets `name` and `result_type` on first save and defers everything else to the base class. The base `Discipline.save()` creates one `TeamResult` per active team and, when the admin picks a `pairing_system`, schedules `TeamSportRound`s and `Game`s. Nothing else changes.

**Tech Stack:** Django 4.2, Django REST Framework, PostgreSQL via `docker compose` (server on 3003, Postgres on 5433). Tests run with `manage.py test` inside the `server` container.

**Spec:** `docs/superpowers/specs/2026-09-18-culture-quizz-and-darts-design.md`

---

## File structure

| Path | Responsibility |
|---|---|
| `server/olympic_warriors/models/GeneralCultureQuizz.py` | New. Quiz discipline subclass, sets name and result type. |
| `server/olympic_warriors/models/Darts.py` | New. Darts discipline subclass, sets name and result type. |
| `server/olympic_warriors/models/__init__.py` | Modify. Export the two new classes. |
| `server/olympic_warriors/admin.py` | Modify. Import and register both with `DisciplineAdmin`. |
| `server/olympic_warriors/migrations/0025_generalculturequizz.py` | Generated. `CreateModel` for the quiz. |
| `server/olympic_warriors/migrations/0026_darts.py` | Generated. `CreateModel` for darts. |
| `server/olympic_warriors/tests/test_disciplines.py` | New. Shared fixture plus quiz and darts tests. |

## Things to know before starting

- **Business logic lives in model `save()` overrides.** `Discipline.save()` (in `server/olympic_warriors/models/Discipline.py`) creates `TeamResult` rows and dispatches scheduling on first save. `Game.save()` turns scores into `TeamResult.points` as deltas.
- **A freshly scheduled game is a draw.** The round-robin scheduler creates games with `score1 = score2 = 0`, and `Game.save()` on a new object with equal scores gives both teams `+1`. So after scheduling, team results are not zero. Tests assert deltas, not absolute values.
- **Round robin shape with six teams.** `schedule_round_robin_games` builds a full round robin: `max_rounds` defaults to five, every team plays once per round, fifteen games total. Each round is played in batches of `len(teams) // 3` simultaneous games (two, then one) refereed by the teams not playing in the batch. Use six teams in tests. (When this plan was written the scheduler dropped one pairing per round and produced ten games; that has since been fixed on `dev`.)
- **The discipline `name` string matters.** Admin code and the front icon key match on it. Use exactly `General Culture Quizz` and `Darts`.
- **All commands run from the worktree root** `/Users/shoklah/Work/Playground/Olympic-Warriors/.claude/worktrees/new-disciplines-culture-darts-62bc99`. Do not `cd` to the main checkout.
- **Docker project name.** Compose derives its project name from the worktree folder, so this stack is separate from the main checkout's. Ports 3003 and 5433 must be free (the main stack was down when this plan was written).

---

### Task 1: Environment and baseline

**Files:**
- Create (gitignored): `server/dev.env`

- [ ] **Step 1: Copy the env file from the main checkout**

```bash
cp /Users/shoklah/Work/Playground/Olympic-Warriors/server/dev.env server/dev.env
```

Expected: file exists, `git status` still clean (it is gitignored).

- [ ] **Step 2: Start Postgres and the server**

```bash
docker compose up -d --build db server
```

Expected: both containers reach `Started`/`Healthy`. The server container runs `migrate` then `runserver`. A warning about the obsolete `version` attribute is normal.

- [ ] **Step 3: Run the existing test suite as a baseline**

```bash
docker compose exec server python manage.py test olympic_warriors
```

Expected: `Ran 1 test ... FAILED (failures=1)`. The single pre-existing test gets a 401 because of the decorator-ordering auth bug documented in `CLAUDE.md`. That is the baseline; it is not touched by this plan.

---

### Task 2: General Culture Quizz

**Files:**
- Create: `server/olympic_warriors/tests/test_disciplines.py`
- Create: `server/olympic_warriors/models/GeneralCultureQuizz.py`
- Modify: `server/olympic_warriors/models/__init__.py`
- Modify: `server/olympic_warriors/admin.py` (import block lines 7-32, register block near line 399)
- Generate: `server/olympic_warriors/migrations/0025_generalculturequizz.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_disciplines.py`:

```python
"""
Tests for minimal and game-based discipline subclasses.
"""

from django.test import TestCase

from olympic_warriors.models import (
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    GeneralCultureQuizz,
    ResultTypes,
)


class DisciplineTestSetup(TestCase):
    """
    One edition with six active teams (the smallest count that lets the
    round-robin scheduler keep teams free to referee) and one inactive team.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
        )
        self.teams = [
            Team.objects.create(name=f"Team {i}", edition=self.edition) for i in range(1, 7)
        ]
        self.inactive_team = Team.objects.create(
            name="Ghost", edition=self.edition, is_active=False
        )


class TestGeneralCultureQuizz(DisciplineTestSetup):

    def test_sets_name_and_result_type(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        quizz.refresh_from_db()
        self.assertEqual(quizz.name, "General Culture Quizz")
        self.assertEqual(quizz.result_type, ResultTypes.POINTS)

    def test_creates_zero_point_result_per_active_team(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        results = TeamResult.objects.filter(discipline=quizz)
        self.assertEqual(results.count(), 6)
        self.assertTrue(all(result.points == 0 for result in results))
        self.assertFalse(results.filter(team=self.inactive_team).exists())

    def test_schedules_no_rounds_or_games(self):
        quizz = GeneralCultureQuizz.objects.create(edition=self.edition)
        self.assertEqual(TeamSportRound.objects.filter(discipline=quizz).count(), 0)
        self.assertEqual(Game.objects.filter(discipline=quizz).count(), 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

Expected: `ImportError: cannot import name 'GeneralCultureQuizz' from 'olympic_warriors.models'`.

- [ ] **Step 3: Create the model**

Create `server/olympic_warriors/models/GeneralCultureQuizz.py`:

```python
from .Discipline import Discipline
from .ResultTypes import ResultTypes


class GeneralCultureQuizz(Discipline):
    """
    General Culture Quizz is a discipline that takes place in an edition of the Olympic Warriors.
    Live scoring happens on an external quiz platform; only final points are stored here.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to general culture quizz and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'General Culture Quizz'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
```

- [ ] **Step 4: Export it from the models package**

In `server/olympic_warriors/models/__init__.py`, add after the `ObstacleCourse` line:

```python
from .GeneralCultureQuizz import GeneralCultureQuizz
```

- [ ] **Step 5: Register it in the admin**

In `server/olympic_warriors/admin.py`, add `GeneralCultureQuizz,` to the `from .models import (...)` block after `ObstacleCourse,`, and add at the end of the file after `site.register(ObstacleCourse, DisciplineAdmin)`:

```python
site.register(GeneralCultureQuizz, DisciplineAdmin)
```

- [ ] **Step 6: Generate the migration**

```bash
docker compose exec server python manage.py makemigrations olympic_warriors -n generalculturequizz
```

Expected: `Migrations for 'olympic_warriors': olympic_warriors/migrations/0025_generalculturequizz.py - Create model GeneralCultureQuizz`. The generated file should contain a single `CreateModel` whose only field is `discipline_ptr`, with `bases=('olympic_warriors.discipline',)` and a dependency on `('olympic_warriors', '0024_obstaclecourse')`. If the file is owned by root, run `chown` from the host or recreate it.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

Expected: `Ran 3 tests ... OK`.

- [ ] **Step 8: Commit**

```bash
git add server/olympic_warriors/models/GeneralCultureQuizz.py server/olympic_warriors/models/__init__.py server/olympic_warriors/admin.py server/olympic_warriors/migrations/0025_generalculturequizz.py server/olympic_warriors/tests/test_disciplines.py
git commit -m "[ADD] General Culture Quizz discipline

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Darts

**Files:**
- Modify: `server/olympic_warriors/tests/test_disciplines.py`
- Create: `server/olympic_warriors/models/Darts.py`
- Modify: `server/olympic_warriors/models/__init__.py`
- Modify: `server/olympic_warriors/admin.py`
- Generate: `server/olympic_warriors/migrations/0026_darts.py`

- [ ] **Step 1: Write the failing tests**

In `server/olympic_warriors/tests/test_disciplines.py`, add `Discipline` and `Darts` to the import block so it reads:

```python
from olympic_warriors.models import (
    Edition,
    Team,
    TeamResult,
    TeamSportRound,
    Game,
    Discipline,
    GeneralCultureQuizz,
    Darts,
    ResultTypes,
)
```

Then append at the end of the file:

```python
class TestDarts(DisciplineTestSetup):

    def _create_round_robin_darts(self):
        return Darts.objects.create(
            edition=self.edition,
            pairing_system=Discipline.PairingSystem.ROUND_ROBIN,
        )

    def test_sets_name_and_result_type(self):
        darts = Darts.objects.create(edition=self.edition)
        darts.refresh_from_db()
        self.assertEqual(darts.name, "Darts")
        self.assertEqual(darts.result_type, ResultTypes.POINTS)

    def test_round_robin_schedules_rounds_and_games_with_referees(self):
        darts = self._create_round_robin_darts()
        darts.refresh_from_db()

        # Six teams: max_rounds defaults to 5, every pair of teams meets once.
        self.assertEqual(darts.max_rounds, 5)
        self.assertEqual(TeamSportRound.objects.filter(discipline=darts).count(), 5)

        games = Game.objects.filter(discipline=darts)
        self.assertEqual(games.count(), 15)
        for game in games:
            self.assertEqual(game.edition, self.edition)
            self.assertNotIn(game.referees_id, (game.team1_id, game.team2_id))

    def test_game_score_rolls_into_team_results(self):
        darts = self._create_round_robin_darts()
        game = Game.objects.filter(discipline=darts).first()

        # Scheduled games start 0-0, which Game.save() already counted as a draw (+1 each).
        team1_before = TeamResult.objects.get(team=game.team1, discipline=darts).points
        team2_before = TeamResult.objects.get(team=game.team2, discipline=darts).points

        game.score1 = 3
        game.score2 = 1
        game.save()

        team1_after = TeamResult.objects.get(team=game.team1, discipline=darts).points
        team2_after = TeamResult.objects.get(team=game.team2, discipline=darts).points

        # Draw -> team1 win: winner goes from 1 to 3 (+2), loser from 1 to 0 (-1).
        self.assertEqual(team1_after - team1_before, 2)
        self.assertEqual(team2_after - team2_before, -1)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

Expected: `ImportError: cannot import name 'Darts' from 'olympic_warriors.models'`.

- [ ] **Step 3: Create the model**

Create `server/olympic_warriors/models/Darts.py`:

```python
from .Discipline import Discipline
from .ResultTypes import ResultTypes


class Darts(Discipline):
    """
    Darts is a discipline that takes place in an edition of the Olympic Warriors.
    Games are scheduled by the base Discipline according to the pairing system
    chosen in the admin.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to darts, schedule games and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Darts'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
```

- [ ] **Step 4: Export it from the models package**

In `server/olympic_warriors/models/__init__.py`, add after the `GeneralCultureQuizz` line:

```python
from .Darts import Darts
```

- [ ] **Step 5: Register it in the admin**

In `server/olympic_warriors/admin.py`, add `Darts,` to the `from .models import (...)` block after `GeneralCultureQuizz,`, and add at the end of the file after `site.register(GeneralCultureQuizz, DisciplineAdmin)`:

```python
site.register(Darts, DisciplineAdmin)
```

- [ ] **Step 6: Generate the migration**

```bash
docker compose exec server python manage.py makemigrations olympic_warriors -n darts
```

Expected: `Migrations for 'olympic_warriors': olympic_warriors/migrations/0026_darts.py - Create model Darts`, depending on `('olympic_warriors', '0025_generalculturequizz')`, single `CreateModel` with only `discipline_ptr`.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_disciplines
```

Expected: `Ran 6 tests ... OK`.

- [ ] **Step 8: Commit**

```bash
git add server/olympic_warriors/models/Darts.py server/olympic_warriors/models/__init__.py server/olympic_warriors/admin.py server/olympic_warriors/migrations/0026_darts.py server/olympic_warriors/tests/test_disciplines.py
git commit -m "[ADD] Darts discipline

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Verification

**Files:** none modified.

- [ ] **Step 1: Confirm no migration drift**

```bash
docker compose exec server python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`.

- [ ] **Step 2: Run the full suite**

```bash
docker compose exec server python manage.py test olympic_warriors
```

Expected: `Ran 9 tests ... FAILED (failures=1)`, where the only failure is the pre-existing `test_players` 401 and all eight `test_disciplines` tests pass (the review pass after Task 3 added two more tests).

- [ ] **Step 3: Run pylint as CI does (advisory)**

```bash
pylint --load-plugins pylint_django --ignore=lib server/olympic_warriors/models/Darts.py server/olympic_warriors/models/GeneralCultureQuizz.py server/olympic_warriors/tests/test_disciplines.py
```

Expected: no new warnings beyond what the existing discipline files produce (CI runs it with `continue-on-error`, so this is informational). Skip if `pylint_django` is not installed on the host.

- [ ] **Step 4: Confirm the admin exposes both disciplines**

```bash
docker compose exec server python manage.py shell -c "from django.contrib.admin import site; from olympic_warriors.models import Darts, GeneralCultureQuizz; print(Darts in site._registry, GeneralCultureQuizz in site._registry)"
```

Expected: `True True`.

- [ ] **Step 5: Stop the stack**

```bash
docker compose down
```
