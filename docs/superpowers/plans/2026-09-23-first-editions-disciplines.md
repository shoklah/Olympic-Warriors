# First Editions Disciplines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ten disciplines from the first editions (Volleyball, Jumping Rope, Dance, Frisbee, Geoguessr, Football, Handball, Burger Quizz, Blindfolded Obstacle Course, Disc Throw), each with a model, admin registration, migration, icon and French name.

**Architecture:** Each discipline is a Django multi-table-inheritance child of the concrete `Discipline` model. It only overrides `save()` to set `name` and `result_type` on creation; the base class does everything else (team results, scheduling). The front derives the icon file from the name and looks up the French name in a dictionary, and one test file enforces both for every model name.

**Tech Stack:** Django 4.2 + PostgreSQL (tests via docker compose), SvelteKit 2 / Vitest.

**Spec:** `docs/superpowers/specs/2026-09-23-first-editions-disciplines-design.md`

---

## Conventions for every task

- Work in the main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors` on branch `claude/first-editions-disciplines` (checked out from `dev`). Never switch branches.
- The compose stack is running and mounts `./server`, so server commands run through it without a rebuild:
  ```bash
  docker compose exec -T server python manage.py <command>
  ```
- Front commands run in `front/` (`node_modules` is there already; `front/.env` exists).
- Commit message style: `[ADD] ...`, ending with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Implementers run sequentially: parallel agents share the git index.

## File map

| File | Change |
|---|---|
| `server/olympic_warriors/models/{Volleyball,JumpingRope,Dance,Frisbee,Geoguessr,Football,Handball,BurgerQuizz,BlindfoldedObstacleCourse,DiscThrow}.py` | create, one discipline each |
| `server/olympic_warriors/models/__init__.py` | export the ten |
| `server/olympic_warriors/admin.py` | import and register the ten with `DisciplineAdmin` |
| `server/olympic_warriors/migrations/0030_first_editions_disciplines.py` | generated |
| `server/olympic_warriors/tests/test_disciplines.py` | one test class for the ten |
| `front/src/lib/icons.test.js` | ten names in `DISCIPLINE_NAMES` |
| `front/src/lib/i18n/disciplines.js` | French names |
| `front/src/lib/img/icons/<stem>.svg` | ten icons |

---

### Task 0: Baseline

- [ ] **Step 1: Check the baseline is green**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_disciplines
cd front && npm test
```
Expected: both pass. If the Django run fails before this plan's changes, stop and report.

---

### Task 1: Server models

**Files:**
- Create: the ten `server/olympic_warriors/models/<Model>.py`
- Modify: `server/olympic_warriors/models/__init__.py`
- Test: `server/olympic_warriors/tests/test_disciplines.py`

- [ ] **Step 1: Write the failing test**

In `server/olympic_warriors/tests/test_disciplines.py`, add these ten to the existing `from olympic_warriors.models import (...)` list, after `Darts,`:

```python
    Volleyball,
    JumpingRope,
    Dance,
    Frisbee,
    Geoguessr,
    Football,
    Handball,
    BurgerQuizz,
    BlindfoldedObstacleCourse,
    DiscThrow,
```

Append at the end of the file:

```python
FIRST_EDITIONS_DISCIPLINES = [
    (Volleyball, "Volleyball", ResultTypes.POINTS),
    (JumpingRope, "Jumping Rope", ResultTypes.TIME),
    (Dance, "Dance", ResultTypes.POINTS),
    (Frisbee, "Frisbee", ResultTypes.POINTS),
    (Geoguessr, "Geoguessr", ResultTypes.POINTS),
    (Football, "Football", ResultTypes.POINTS),
    (Handball, "Handball", ResultTypes.POINTS),
    (BurgerQuizz, "Burger Quizz", ResultTypes.POINTS),
    (BlindfoldedObstacleCourse, "Blindfolded Obstacle Course", ResultTypes.TIME),
    (DiscThrow, "Disc Throw", ResultTypes.POINTS),
]


class TestFirstEditionsDisciplines(DisciplineTestSetup):
    """The disciplines of the first editions: name, result type and empty results."""

    def test_sets_name_and_result_type(self):
        for model, name, result_type in FIRST_EDITIONS_DISCIPLINES:
            with self.subTest(name=name):
                discipline = model.objects.create(edition=self.edition)
                discipline.refresh_from_db()
                self.assertEqual(discipline.name, name)
                self.assertEqual(discipline.result_type, result_type)

    def test_creates_an_empty_result_per_active_team(self):
        for model, name, _ in FIRST_EDITIONS_DISCIPLINES:
            with self.subTest(name=name):
                discipline = model.objects.create(edition=self.edition)
                results = TeamResult.objects.filter(discipline=discipline)
                self.assertEqual(results.count(), len(self.teams))
                self.assertFalse(results.filter(points__isnull=False).exists())
                self.assertFalse(results.filter(time__isnull=False).exists())
```

- [ ] **Step 2: Run the test to check it fails**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_disciplines
```
Expected: an error `ImportError: cannot import name 'Volleyball' from 'olympic_warriors.models'`.

- [ ] **Step 3: Create the ten model files**

Every file follows this template. `<Class>`, `<Name>`, `<lowercase name>` and `<TYPE>` come from the table below.

```python
from .Discipline import Discipline
from .ResultTypes import ResultTypes


class <Class>(Discipline):
    """
    <Name> is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to <lowercase name> and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = '<Name>'
            self.result_type = ResultTypes.<TYPE>

        super().save(*args, **kwargs)
```

| File | `<Class>` | `<Name>` | `<TYPE>` |
|---|---|---|---|
| `models/Volleyball.py` | `Volleyball` | `Volleyball` | `POINTS` |
| `models/JumpingRope.py` | `JumpingRope` | `Jumping Rope` | `TIME` |
| `models/Dance.py` | `Dance` | `Dance` | `POINTS` |
| `models/Frisbee.py` | `Frisbee` | `Frisbee` | `POINTS` |
| `models/Geoguessr.py` | `Geoguessr` | `Geoguessr` | `POINTS` |
| `models/Football.py` | `Football` | `Football` | `POINTS` |
| `models/Handball.py` | `Handball` | `Handball` | `POINTS` |
| `models/BurgerQuizz.py` | `BurgerQuizz` | `Burger Quizz` | `POINTS` |
| `models/BlindfoldedObstacleCourse.py` | `BlindfoldedObstacleCourse` | `Blindfolded Obstacle Course` | `TIME` |
| `models/DiscThrow.py` | `DiscThrow` | `Disc Throw` | `POINTS` |

For the three team sports (Volleyball, Football, Handball), use the Darts docstring instead of the one-line docstring, so readers know games exist:

```python
    """
    <Name> is a discipline that takes place in an edition of the Olympic Warriors.
    Games are scheduled by the base Discipline according to the pairing system
    chosen in the admin.
    """
```
and the `save()` docstring `Override save method to set discipline name to <lowercase name>, schedule games and initialize team results.`

Frisbee gets one extra docstring line after the first one:
```
    Played golf style over several rounds; organisers enter the final points by hand,
    higher is better.
```

As an example, `models/JumpingRope.py` in full:

```python
from .Discipline import Discipline
from .ResultTypes import ResultTypes


class JumpingRope(Discipline):
    """
    Jumping Rope is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to jumping rope and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Jumping Rope'
            self.result_type = ResultTypes.TIME

        super().save(*args, **kwargs)
```

- [ ] **Step 4: Export them**

In `server/olympic_warriors/models/__init__.py`, insert after `from .Darts import Darts` (before the `ResultTypes` line):

```python
from .Volleyball import Volleyball
from .JumpingRope import JumpingRope
from .Dance import Dance
from .Frisbee import Frisbee
from .Geoguessr import Geoguessr
from .Football import Football
from .Handball import Handball
from .BurgerQuizz import BurgerQuizz
from .BlindfoldedObstacleCourse import BlindfoldedObstacleCourse
from .DiscThrow import DiscThrow
```

- [ ] **Step 5: Generate the migration**

```bash
docker compose exec -T server python manage.py makemigrations olympic_warriors --name first_editions_disciplines
```
Expected: `migrations/0030_first_editions_disciplines.py` with ten `CreateModel` operations, each having only a `discipline_ptr` OneToOneField with `bases=('olympic_warriors.discipline',)`. Open the file and check that it contains nothing else, such as an `AlterField` on an unrelated model. If it does, stop and report.

- [ ] **Step 6: Run the tests to check they pass**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_disciplines
```
Expected: all pass, including `TestFirstEditionsDisciplines` (2 tests, 10 subtests each).

- [ ] **Step 7: Commit**

```bash
git add server/olympic_warriors/models server/olympic_warriors/migrations/0030_first_editions_disciplines.py server/olympic_warriors/tests/test_disciplines.py
git commit -m "[ADD] ten disciplines from the first editions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Admin registration

**Files:**
- Modify: `server/olympic_warriors/admin.py` (the import block near line 7, the `site.register` list at the end)

- [ ] **Step 1: Import and register**

Add the ten names to the `from .models import (...)` block, after `Darts,`:

```python
    Volleyball,
    JumpingRope,
    Dance,
    Frisbee,
    Geoguessr,
    Football,
    Handball,
    BurgerQuizz,
    BlindfoldedObstacleCourse,
    DiscThrow,
```

Append after `site.register(Darts, DisciplineAdmin)`:

```python
site.register(Volleyball, DisciplineAdmin)
site.register(JumpingRope, DisciplineAdmin)
site.register(Dance, DisciplineAdmin)
site.register(Frisbee, DisciplineAdmin)
site.register(Geoguessr, DisciplineAdmin)
site.register(Football, DisciplineAdmin)
site.register(Handball, DisciplineAdmin)
site.register(BurgerQuizz, DisciplineAdmin)
site.register(BlindfoldedObstacleCourse, DisciplineAdmin)
site.register(DiscThrow, DisciplineAdmin)
```

- [ ] **Step 2: Check there is no pending migration and the full suite passes**

```bash
docker compose exec -T server python manage.py makemigrations --check --dry-run
docker compose exec -T server python manage.py test
```
Expected: `No changes detected`, then every test passes.

- [ ] **Step 3: Commit**

```bash
git add server/olympic_warriors/admin.py
git commit -m "[ADD] admin: register the first editions disciplines

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: French names

**Files:**
- Modify: `front/src/lib/icons.test.js` (`DISCIPLINE_NAMES`, line 27)
- Modify: `front/src/lib/i18n/disciplines.js`

- [ ] **Step 1: Add the names to the test list**

Replace `DISCIPLINE_NAMES` in `front/src/lib/icons.test.js` with the full sorted list:

```js
const DISCIPLINE_NAMES = [
	'Basketball',
	'Blindfolded Obstacle Course',
	'Blindtest',
	'Burger Quizz',
	'Crossfit',
	'Dance',
	'Darts',
	'Disc Throw',
	'Dodgeball',
	'Fair',
	'Football',
	'Frisbee',
	'General Culture Quizz',
	'Geoguessr',
	'Geography Quizz',
	'Handball',
	'Hide and Seek',
	'Jumping Rope',
	'Obstacle Course',
	'Orienteering',
	'Petanque',
	'Relay',
	'Rugby',
	'Volleyball'
];
```

- [ ] **Step 2: Run it to check it fails**

```bash
cd front && npx vitest run src/lib/icons.test.js
```
Expected: 20 failures, one icon and one French name per new discipline.

- [ ] **Step 3: Add the French names**

In `front/src/lib/i18n/disciplines.js`, add to `FRENCH_NAMES` after `Darts: 'Fléchettes'` (add a comma after that line):

```js
	Volleyball: 'Volley-ball',
	'Jumping Rope': 'Corde à sauter',
	Dance: 'Danse',
	'Burger Quizz': 'Burger Quiz',
	'Blindfolded Obstacle Course': "Parcours d'obstacles à l'aveugle",
	'Disc Throw': 'Lancer de disque'
```

and replace `SAME_IN_FRENCH` with:

```js
export const SAME_IN_FRENCH = [
	'Rugby',
	'Basketball',
	'Crossfit',
	'Blindtest',
	'Frisbee',
	'Geoguessr',
	'Football',
	'Handball'
];
```

In the JSDoc above `FRENCH_NAMES`, change `(Rugby,\n * Basketball, Crossfit, Blindtest)` to `(Rugby,\n * Football, Frisbee, …)`: the list is only examples, not exhaustive.

- [ ] **Step 4: Run it to check the French-name half passes**

```bash
cd front && npx vitest run src/lib/icons.test.js
```
Expected: 10 failures left, all under `every discipline model has an icon`.

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/icons.test.js front/src/lib/i18n/disciplines.js
git commit -m "[ADD] front: French names of the first editions disciplines

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Icons

**Files:**
- Create: ten files in `front/src/lib/img/icons/`

House style: `width="2000" height="2000" viewBox="0 0 2000 2000" fill="none"`, white strokes of about 80 to 130 units with round caps, white fills only for small solid details, no background.

- [ ] **Step 1: Write the ten SVGs**

`volleyball.svg` (ball with three curved panels):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="1000" cy="1000" r="850" stroke="white" stroke-width="120"/>
<path d="M1000 1000Q1050 500 780 180M1000 1000Q1450 1200 1830 1060M1000 1000Q560 1280 470 1680" stroke="white" stroke-width="110" stroke-linecap="round"/>
<path d="M620 300Q840 620 700 1150M1640 1450Q1220 1400 900 1600M1500 420Q1300 760 1500 1100" stroke="white" stroke-width="80" stroke-linecap="round"/>
</svg>
```

`jumpingrope.svg` (two handles, rope drooping between them):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M500 250V750M1500 250V750" stroke="white" stroke-width="200" stroke-linecap="round"/>
<path d="M500 800C500 2150 1500 2150 1500 800" stroke="white" stroke-width="90" stroke-linecap="round"/>
</svg>
```

`dance.svg` (disco ball on a string, with sparkles):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M1000 100V500" stroke="white" stroke-width="90" stroke-linecap="round"/>
<circle cx="1000" cy="1150" r="650" stroke="white" stroke-width="120"/>
<ellipse cx="1000" cy="1150" rx="300" ry="650" stroke="white" stroke-width="70"/>
<path d="M350 1150H1650M430 850Q1000 950 1570 850M430 1450Q1000 1350 1570 1450" stroke="white" stroke-width="70" stroke-linecap="round"/>
<path d="M300 250V550M150 400H450M1700 1750V1950M1600 1850H1800" stroke="white" stroke-width="80" stroke-linecap="round"/>
</svg>
```

`frisbee.svg` (disc golf basket: pole, chains, basket):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M1000 300V1850M600 1850H1400M550 400H1450" stroke="white" stroke-width="120" stroke-linecap="round"/>
<path d="M600 400Q700 800 1000 950M1400 400Q1300 800 1000 950M800 400Q850 800 1000 950M1200 400Q1150 800 1000 950" stroke="white" stroke-width="50" stroke-linecap="round"/>
<path d="M500 1050H1500L1400 1350H600Z" stroke="white" stroke-width="110" stroke-linejoin="round"/>
</svg>
```

`geoguessr.svg` (map pin over its shadow):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M1000 1550C1000 1550 500 1050 500 700A500 500 0 0 1 1500 700C1500 1050 1000 1550 1000 1550Z" stroke="white" stroke-width="120" stroke-linejoin="round"/>
<circle cx="1000" cy="700" r="170" stroke="white" stroke-width="110"/>
<ellipse cx="1000" cy="1780" rx="500" ry="120" stroke="white" stroke-width="80"/>
</svg>
```

`football.svg` (ball with a central pentagon and seams to the edge):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="1000" cy="1000" r="850" stroke="white" stroke-width="120"/>
<path d="M1000 720L1266 913L1165 1227H835L734 913Z" fill="white"/>
<path d="M1000 720V150M1266 913L1808 737M1165 1227L1500 1688M835 1227L500 1688M734 913L192 737" stroke="white" stroke-width="80" stroke-linecap="round"/>
</svg>
```

`handball.svg` (goal with a net and a ball in front of it):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M250 1850V450H1750V1850" stroke="white" stroke-width="120" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M550 450V1150M850 450V1150M1150 450V1150M1450 450V1150M250 800H1750M250 1150H1750" stroke="white" stroke-width="40" stroke-linecap="round"/>
<circle cx="1000" cy="1560" r="230" stroke="white" stroke-width="100"/>
</svg>
```

`burgerquizz.svg` (burger: bun, lettuce, patty, bun):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M300 900Q300 350 1000 350Q1700 350 1700 900Z" stroke="white" stroke-width="110" stroke-linejoin="round"/>
<path d="M800 580L850 620M1100 530L1150 570M1300 650L1350 690" stroke="white" stroke-width="70" stroke-linecap="round"/>
<path d="M300 1100Q450 1000 600 1100T900 1100T1200 1100T1500 1100T1700 1060" stroke="white" stroke-width="90" stroke-linecap="round"/>
<rect x="300" y="1250" width="1400" height="220" rx="110" stroke="white" stroke-width="110"/>
<path d="M300 1600H1700V1650Q1700 1800 1550 1800H450Q300 1800 300 1650Z" stroke="white" stroke-width="110" stroke-linejoin="round"/>
</svg>
```

`blindfoldedobstaclecourse.svg` (knotted blindfold over a hurdle like the one in `obstaclecourse.svg`):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M200 650Q1000 480 1750 650V900Q1000 730 200 900Z" stroke="white" stroke-width="110" stroke-linejoin="round"/>
<path d="M1750 775L1930 1100M1750 775L1650 1150" stroke="white" stroke-width="90" stroke-linecap="round"/>
<path d="M550 1900V1350M1450 1900V1350M450 1350H1550M120 1900H1880" stroke="white" stroke-width="100" stroke-linecap="round"/>
</svg>
```

`discthrow.svg` (discus flying along a dotted trajectory above the ground):
```svg
<svg width="2000" height="2000" viewBox="0 0 2000 2000" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M200 1650Q700 250 1300 650" stroke="white" stroke-width="80" stroke-linecap="round" stroke-dasharray="1 170"/>
<ellipse cx="1550" cy="800" rx="330" ry="130" transform="rotate(25 1550 800)" stroke="white" stroke-width="110"/>
<ellipse cx="1550" cy="800" rx="110" ry="45" transform="rotate(25 1550 800)" fill="white"/>
<path d="M150 1850H1850" stroke="white" stroke-width="90" stroke-linecap="round"/>
</svg>
```

- [ ] **Step 2: Look at them**

Render each icon to PNG on a dark background and view it. Check that each shape reads as intended, that nothing is clipped at the 2000 edge, and that no two icons look alike (volleyball vs football, frisbee vs discthrow, blindfoldedobstaclecourse vs obstaclecourse):

```bash
mkdir -p "$SCRATCH/icons" && for f in front/src/lib/img/icons/{volleyball,jumpingrope,dance,frisbee,geoguessr,football,handball,burgerquizz,blindfoldedobstaclecourse,discthrow}.svg; do sed 's|fill="none" xmlns|style="background:#111" fill="none" xmlns|' "$f" > "$SCRATCH/icons/$(basename $f)"; done
qlmanage -t -s 300 -o "$SCRATCH/icons" "$SCRATCH/icons"/*.svg
```
(`$SCRATCH` is the session scratchpad directory.) Open the PNGs with the Read tool. Adjust coordinates if a shape is wrong, and keep the house style.

- [ ] **Step 3: Run the front tests and build**

```bash
cd front && npm test && npm run build
```
Expected: every test passes and the build succeeds.

- [ ] **Step 4: Commit**

```bash
git add front/src/lib/img/icons
git commit -m "[ADD] front: icons of the first editions disciplines

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- Ten models with the spec's names and result types: Task 1 (table plus test list)
- Exports, admin, migration `0030`: Tasks 1 and 2
- Team sports need no extra code and no `GameEvent`: covered by the Darts-style docstring, since the base class schedules
- Frisbee is plain points with a docstring note: Task 1
- Icons, French names, test list: Tasks 3 and 4
- Server test per discipline plus `makemigrations --check`: Tasks 1 and 2. `npm test` and `npm run build`: Task 4
