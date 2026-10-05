# In-app registration, slice 1: foundations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Never write to the dev database from a script or `manage.py shell`** (a past implementer deleted editions that way); tests use the throwaway test database only.

**Goal:** Lay the data and admin foundations of the in-app registration (spec: `docs/superpowers/specs/2026-10-04-in-app-registration-design.md`): per-edition questionnaire data, the new private `Player` answers, one shared rating function, a CSV import that keeps the new answers, the admin tools, and the hub's `dates_confirmed` condition. Nothing player-facing besides the hub.

**Architecture:** Plain Django models in the existing `models/` package, business logic in two plain modules (`registration.py` keeps the pure rating maths and CSV parsing, a new `questionnaire.py` holds the DB-backed questionnaire operations), admin wiring in `admin.py`. The edition transfer excludes the personal fields. The front only learns one boolean.

**Tech Stack:** Django 4.2 + DRF, pandas (CSV import), PostgreSQL via `docker compose`, SvelteKit 2 / Svelte 4 with Vitest.

**Accepted trade-offs (Hugo, 2026-10-05):**
- Between this slice and slice 2, the CSV import stores each player's team wishes, sports history and presence tick, and **account deletion (`accounts.deactivate`) does not yet clear them**; slice 2 adds the clearing. State this gap in the PR description.
- The CSV import **overwrites** the new answers on a re-import, exactly as it overwrites ratings today (the CSV is the truth when uploaded), including answers a player gave in the app.

**Out of this slice (slice 2/3 of the spec):** the six `Edition` fields only the open/closed rule and the form read (`registration_opens`, `registration_closes`, `registration_intro_fr/en`, `skills_month_fr/en`, moved to slice 2 by Hugo on 2026-10-05 so nothing unused ships), `UserProfile.invited`, `LateRegistration`, the `/registration/` API, `/me/`'s `can_register`, the invite and late-pass admin tools, the registration open/closed state shown in the admin, the `/register` page.

**Deviation from the spec, deliberate:** `PlayerSport.notes` is a `TextField` with a 200-character *validator* instead of a 200-character column, because the CSV import stores a whole free-text sports history in one row (2026 answers reach 424 characters) and must not truncate it. The validator still guards admin edits and the slice-2 API writes the field through a serializer that enforces 200.

---

## File Structure

| File | Responsibility |
|---|---|
| `server/olympic_warriors/registration.py` (modify) | Add `rate()` (the one rating formula), `resolve_extras()` and the cell parsers for the optional CSV columns; `compute_ratings` calls `rate()`. |
| `server/olympic_warriors/models/Player.py` (modify) | `SportFrequency`, five new `Player` fields, `PlayerSport`. |
| `server/olympic_warriors/models/RegistrationSkill.py` (create) | The per-edition skill (label, identifier, weight, order). |
| `server/olympic_warriors/models/Edition.py` (modify) | `dates_confirmed`; the CSV import stores the new answers. |
| `server/olympic_warriors/models/__init__.py` (modify) | Export `PlayerSport`, `RegistrationSkill`. |
| `server/olympic_warriors/migrations/0041_registration_foundations.py` (generated) | Schema. |
| `server/olympic_warriors/migrations/0042_seed_registration_skills.py` (create) | Data: skills of the existing editions. |
| `server/olympic_warriors/questionnaire.py` (create) | `skills_locked`, `copy_skills`, `recompute_ratings`. |
| `server/olympic_warriors/transfer.py` (modify) | Private fields never exported, `RegistrationSkill` exported, `PlayerSport` not. |
| `server/olympic_warriors/admin.py` (modify) | Edition `dates_confirmed` + locked skills inline + two actions; Player columns, filters, sports inline. |
| `server/olympic_warriors/serializer.py` (modify) | `dates_confirmed` in `SummaryEditionSerializer`. |
| `front/src/lib/components/EditionHub.svelte` (modify), `front/src/lib/i18n/fr.js`, `en.js` | « Dates à venir » while dates are unconfirmed. |
| Tests | `tests/test_registration.py`, `test_registration_models.py` (new), `test_registration_seed.py` (new), `test_questionnaire.py` (new), `test_registration_admin.py` (new), `test_edition_import.py`, `test_transfer.py`, `test_summary.py`, `test_showcase.py`, `test_player_admin.py`, `EditionHub.test.js`. |
| `CLAUDE.md` (modify) | Document the questionnaire. |

Commands below assume the compose stack is up (`docker compose up -d`) and run from the repo root. A shorthand used throughout: `T=docker compose exec server python manage.py test`.

---

### Task 0: Branch and baseline

- [ ] **Step 1: Cut the feature branch from the spec branch** so the spec and this plan travel with the PR (the spec branch is not merged yet).

```bash
git switch docs/registration-design
git switch -c feat/registration-foundations
```

- [ ] **Step 2: Start the stack and run the baseline**

```bash
docker compose up -d
docker compose exec server python manage.py test olympic_warriors.tests.test_registration olympic_warriors.tests.test_edition_import olympic_warriors.tests.test_transfer
```

Expected: `OK` (all pass). If Postgres is not ready, wait ten seconds and retry.

---

### Task 1: One shared rating function

**Files:**
- Modify: `server/olympic_warriors/registration.py` (the tail of `compute_ratings`)
- Test: `server/olympic_warriors/tests/test_registration.py`

- [ ] **Step 1: Write the failing tests.** In `tests/test_registration.py`, extend the import and append the class.

```python
from olympic_warriors.registration import (
    EMAIL,
    FORM_PROFILES,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    compute_ratings,
    parse_name,
    rate,
    resolve_columns,
)
```

```python
class RateTests(SimpleTestCase):
    WEIGHTS = {"a": 1, "b": 3}

    def test_weights_the_skills_then_blends_the_global_level(self):
        weighted, global_rating = rate({"a": 10, "b": 2}, self.WEIGHTS, 5)

        self.assertEqual(weighted, 4.0)  # (10 + 2 * 3) / 4
        self.assertEqual(global_rating, 4.8)  # (4 + 5 * 4) / 5

    def test_a_weak_weighted_rating_with_a_confident_global_level_is_boosted(self):
        weighted, global_rating = rate({"a": 2, "b": 2}, self.WEIGHTS, 6)

        self.assertEqual(weighted, 5.0)  # 2 * 2.5
        self.assertEqual(global_rating, 5.8)

    def test_no_boost_when_the_global_level_is_low(self):
        weighted, global_rating = rate({"a": 2, "b": 2}, self.WEIGHTS, 3)

        self.assertEqual(weighted, 2)
        self.assertEqual(global_rating, 2.8)

    def test_the_boundaries_do_not_boost(self):
        self.assertEqual(rate({"a": 4, "b": 4}, self.WEIGHTS, 8)[0], 4)  # weighted exactly 4
        self.assertEqual(rate({"a": 3, "b": 3}, self.WEIGHTS, 4)[0], 3)  # global exactly 4

    def test_the_rating_stays_on_the_scale(self):
        self.assertEqual(rate({"a": 1, "b": 1}, self.WEIGHTS, 1), (1, 1.0))
        self.assertEqual(rate({"a": 10, "b": 10}, self.WEIGHTS, 10), (10, 10.0))

    def test_skills_outside_the_weights_are_ignored(self):
        self.assertEqual(rate({"a": 6, "b": 6, "zzz": 1}, self.WEIGHTS, 8), (6, 7.6))
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration.RateTests`
Expected: FAIL / ERROR with `ImportError: cannot import name 'rate'`.

- [ ] **Step 3: Implement `rate()` and make `compute_ratings` use it.** In `registration.py`, add above `compute_ratings`:

```python
# A weak self-assessment on the skills but a confident global estimate is treated as
# under-reporting: the weighted rating is multiplied by 2.5 (historical rule).
BOOST_BELOW = 4
BOOST_GLOBAL_ABOVE = 4
BOOST_FACTOR = 2.5


def rate(skills, weights, global_level):
    """
    The one rating formula, for one player. The CSV import, the in-app registration and
    the "recalculate ratings" admin action all go through it, so they cannot drift.

    :param skills: {key: 1..10 rating} holding at least every key of weights.
    :param weights: {key: positive weight}.
    :param global_level: the player's own global estimate, 1..10.
    :return: (weighted, global_rating): the weights-averaged skills clipped to 1..10 and
             boosted when under-reported, then the blend with the global level, clipped
             to 1..10 and rounded to two decimals. Player.rating is round(global_rating).
    """
    total = sum(weights.values())
    weighted = sum(skills[key] * weight for key, weight in weights.items()) / total
    weighted = min(max(weighted, 1), 10)
    if weighted < BOOST_BELOW and global_level > BOOST_GLOBAL_ABOVE:
        weighted *= BOOST_FACTOR
    global_rating = round(min(max((weighted + global_level * 4) / 5, 1), 10), 2)
    return weighted, global_rating
```

Replace the tail of `compute_ratings` (from `total_coef = ...` to `return df`) with:

```python
    weights = {name: spec["coef"] for name, spec in ratings.items()}
    results = [
        rate({name: row[name] for name in weights}, weights, row[GLOBAL_LEVEL])
        for _, row in df.iterrows()
    ]
    df["Weighted_Rating"] = [weighted for weighted, _ in results]
    df["Global_Rating"] = [global_rating for _, global_rating in results]
    return df
```

- [ ] **Step 4: Run the whole registration test modules**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration olympic_warriors.tests.test_edition_import`
Expected: `OK`. The existing `ComputeRatingsTests`, `ComputeRatings2024Tests` and the import tests are the regression net for the refactor.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/registration.py server/olympic_warriors/tests/test_registration.py
git commit -m "[REFACTOR] one shared rating formula for registrations

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Models and schema migration

**Files:**
- Modify: `server/olympic_warriors/models/Player.py`, `models/Edition.py`, `models/__init__.py`
- Create: `server/olympic_warriors/models/RegistrationSkill.py`, `server/olympic_warriors/migrations/0041_registration_foundations.py` (generated)
- Test: `server/olympic_warriors/tests/test_registration_models.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_registration_models.py`:

```python
"""The registration models: the questionnaire's skills, the private answers on a Player."""
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition, Player, PlayerSport, RegistrationSkill
from olympic_warriors.models.Player import SportFrequency


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


class TestEditionDatesConfirmed(TestCase):
    def test_existing_and_new_editions_have_confirmed_dates_by_default(self):
        self.assertTrue(make_edition().dates_confirmed)


class TestPlayerRegistrationFields(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")

    def test_defaults(self):
        player = Player.objects.create(user=self.ana, edition=self.edition, rating=5)

        self.assertIsNone(player.global_level)
        self.assertEqual(player.dietary_restrictions, "")
        self.assertEqual(player.sport_frequency, "")
        self.assertEqual(player.team_wishes, "")
        self.assertFalse(player.attendance_confirmed)

    def test_the_frequency_choices_are_the_five_of_the_form(self):
        self.assertEqual(
            SportFrequency.values, ["rare", "monthly", "hour", "two_hours", "four_hours"]
        )

    def test_sports_come_back_in_order_and_die_with_the_player(self):
        player = Player.objects.create(user=self.ana, edition=self.edition, rating=5)
        PlayerSport.objects.create(player=player, order=2, sport="Judo")
        PlayerSport.objects.create(player=player, order=1, sport="Tennis", level="amateur")

        self.assertEqual([s.sport for s in player.playersport_set.all()], ["Tennis", "Judo"])

        player.delete()
        self.assertEqual(PlayerSport.objects.count(), 0)


class TestRegistrationSkill(TestCase):
    def test_an_identifier_is_unique_per_edition_only(self):
        first, second = make_edition(2027), make_edition(2028)
        RegistrationSkill.objects.create(
            edition=first, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )

        RegistrationSkill.objects.create(
            edition=second, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistrationSkill.objects.create(
                edition=first, name_fr="Autre", name_en="Other", identifier="CARD", weight=1
            )

    def test_skills_are_ordered_and_die_with_their_edition(self):
        edition = make_edition()
        RegistrationSkill.objects.create(
            edition=edition, name_fr="B", name_en="B", identifier="BBB", weight=1, order=2
        )
        RegistrationSkill.objects.create(
            edition=edition, name_fr="A", name_en="A", identifier="AAA", weight=1, order=1
        )

        self.assertEqual([s.identifier for s in edition.registrationskill_set.all()], ["AAA", "BBB"])
        self.assertTrue(RegistrationSkill.objects.get(identifier="AAA").is_active)

        edition.delete()
        self.assertEqual(RegistrationSkill.objects.count(), 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration_models`
Expected: ERROR `ImportError: cannot import name 'PlayerSport'`.

- [ ] **Step 3: Add the Player fields and `PlayerSport`.** In `models/Player.py`, change the validators import and add the choices above `class Player`:

```python
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator


class SportFrequency(models.TextChoices):
    """How often a player does sport: the five answers of the registration form."""

    RARE = "rare", "Moins d'une fois par mois"
    MONTHLY = "monthly", "Moins d'une fois par semaine mais plusieurs fois par mois"
    HOUR = "hour", "Environ une heure par semaine"
    TWO_HOURS = "two_hours", "Au moins deux heures par semaine"
    FOUR_HOURS = "four_hours", "Au moins quatre heures par semaine"
```

In `Player`, after `is_active = ...`, add:

```python
    # What the player says at registration. Private: organisers only, never in a public payload.
    global_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Raw global estimate; `rating` blends it, so it cannot be recovered from it.",
    )
    dietary_restrictions = models.TextField(
        blank=True, default="", validators=[MaxLengthValidator(500)]
    )
    sport_frequency = models.CharField(
        max_length=10, choices=SportFrequency.choices, blank=True, default=""
    )
    team_wishes = models.TextField(blank=True, default="", validators=[MaxLengthValidator(1000)])
    attendance_confirmed = models.BooleanField(
        default=False,
        help_text="The player's own tick: paid and will be there. Nothing checks it.",
    )
```

Append at the end of the file:

```python
class PlayerSport(models.Model):
    """
    One sport a player has practised, as entered at registration. Private.
    """

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Débutant"
        AMATEUR = "amateur", "Amateur"
        CLUB = "club", "Club"
        COMPETITION = "competition", "Compétition"

    class Practice(models.TextChoices):
        NO_LONGER = "no_longer", "Ne pratique plus"
        OCCASIONALLY = "occasionally", "Pratique occasionnelle"
        REGULARLY = "regularly", "Pratique régulière"

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)
    sport = models.CharField(max_length=80)
    level = models.CharField(max_length=12, choices=Level.choices, blank=True, default="")
    practice = models.CharField(max_length=12, choices=Practice.choices, blank=True, default="")
    duration_months = models.PositiveIntegerField(null=True, blank=True)
    # A TextField so the CSV import can keep a whole imported history; the validator guards
    # admin edits and the registration API.
    notes = models.TextField(blank=True, default="", validators=[MaxLengthValidator(200)])

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.sport
```

- [ ] **Step 4: Create `models/RegistrationSkill.py`**

```python
from django.core.validators import MinValueValidator
from django.db import models


class RegistrationSkill(models.Model):
    """
    One self-rated skill of an edition's registration questionnaire. Its weight feeds the
    player's rating (registration.rate); its identifier is the PlayerRating identifier.
    """

    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    name_fr = models.CharField(max_length=100)
    # Also what PlayerRating.name stores, as the CSV import does.
    name_en = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    weight = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "identifier"], name="registration_skill_unique_identifier"
            )
        ]

    def __str__(self) -> str:
        return f"{self.identifier} ({self.edition.year})"
```

- [ ] **Step 5: Add the Edition field.** In `models/Edition.py`, after `photos_url = ...`:

```python
    # False while the dates are provisional (an edition created early so players can
    # register): the hub then hides the date range and the countdown.
    dates_confirmed = models.BooleanField(default=True)
```

(The registration window and the form texts, `registration_opens`, `registration_closes`, `registration_intro_fr/en`, `skills_month_fr/en`, arrive with slice 2, next to the code that reads them.)

- [ ] **Step 6: Export the models.** In `models/__init__.py` replace the first line and add one:

```python
from .Player import Player, PlayerRating, PlayerSport
from .RegistrationSkill import RegistrationSkill
```

(`RegistrationSkill` references `"Edition"` by name, so its position relative to the `Edition` import does not matter.)

- [ ] **Step 7: Generate the migration**

```bash
docker compose exec server python manage.py makemigrations olympic_warriors -n registration_foundations
```

Expected: `0041_registration_foundations.py` creating `RegistrationSkill` and `PlayerSport` and adding the `Edition.dates_confirmed` field and the five `Player` fields. Read the generated file once; if Django also lists unrelated changes, stop and report.

- [ ] **Step 8: Run the model tests and the migration check**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration_models
docker compose exec server python manage.py makemigrations --check --dry-run
```

Expected: `OK`, then `No changes detected`.

- [ ] **Step 9: Commit**

```bash
git add server/olympic_warriors/models server/olympic_warriors/migrations/0041_registration_foundations.py server/olympic_warriors/tests/test_registration_models.py
git commit -m "[FEAT] registration models: skills, private player answers, sports

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Seed the skills of the existing editions

**Files:**
- Create: `server/olympic_warriors/migrations/0042_seed_registration_skills.py`
- Test: `server/olympic_warriors/tests/test_registration_seed.py`

- [x] **Step 1: Check prod before writing the seed — DONE 2026-10-05, read-only, over SSH with Hugo's approval.** Result: editions 2021–2026 exist; ratings exist only for 2024 (24 players, the 2024 identifiers: `OBS` present, `STMN` named « Endurance and Cardio »), 2025 (21) and 2026 (18) (the 2025 identifiers: `CARD` present, `STMN` named « Endurance »); 2021–2023 have none. The mapping below is confirmed, no change. Original instructions kept for reference: The seed maps 2024 to the 2024 profile and every edition from 2025 on to the 2025 profile; earlier editions get nothing. Ask Hugo to run this **read-only** query on prod and paste the output; do not run it yourself.

```bash
docker compose exec server python manage.py shell -c "
from django.db.models import Count
from olympic_warriors.models import PlayerRating
for row in PlayerRating.objects.values('player__edition__year', 'identifier', 'name').annotate(n=Count('id')).order_by('player__edition__year', 'identifier'): print(row)"
```

Compare with the tables in this task. If an edition's identifiers or names differ (for example 2025 on the 2024 skills), adjust the year mapping in `seed()` below before continuing, and say so in the commit message. If Hugo is not available, continue with the mapping below and flag the open check in the PR description.

- [ ] **Step 2: Write the failing tests.** Create `tests/test_registration_seed.py`:

```python
"""The data migration that gives the existing editions their questionnaire."""
import importlib

from django.apps import apps
from django.test import TestCase

from olympic_warriors.models import Edition, RegistrationSkill
from olympic_warriors.registration import FORM_PROFILES

migration = importlib.import_module("olympic_warriors.migrations.0042_seed_registration_skills")


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


class TestSeedLiteralsMatchTheFormProfiles(TestCase):
    """The migration holds literals (a migration must not follow later code changes); this
    keeps them equal to the profiles the CSV import knows today."""

    def literals(self, skills):
        return {(i, fr, en, w) for i, fr, en, w in skills}

    def profile(self, name):
        return {
            (spec["id"], spec["criterion"], skill, spec["coef"])
            for skill, spec in FORM_PROFILES[name].items()
        }

    def test_2025_skills(self):
        self.assertEqual(self.literals(migration.SKILLS_2025), self.profile("2025"))

    def test_2024_skills(self):
        self.assertEqual(self.literals(migration.SKILLS_2024), self.profile("2024"))


class TestSeed(TestCase):
    def test_each_edition_gets_the_skills_of_its_form(self):
        old, y2024, y2025, y2026 = (make_edition(y) for y in (2023, 2024, 2025, 2026))

        migration.seed(apps, None)

        self.assertEqual(old.registrationskill_set.count(), 0)
        self.assertEqual(y2024.registrationskill_set.count(), 10)
        self.assertTrue(y2024.registrationskill_set.filter(identifier="OBS", weight=1).exists())
        for edition in (y2025, y2026):
            self.assertEqual(edition.registrationskill_set.count(), 10)
            self.assertTrue(edition.registrationskill_set.filter(identifier="CARD").exists())
            self.assertFalse(edition.registrationskill_set.filter(identifier="OBS").exists())

    def test_names_orders_and_weights(self):
        edition = make_edition(2026)

        migration.seed(apps, None)

        first = edition.registrationskill_set.first()
        self.assertEqual(
            (first.identifier, first.name_fr, first.name_en, first.weight, first.order),
            ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2, 0),
        )
        self.assertEqual(
            list(edition.registrationskill_set.values_list("order", flat=True)), list(range(10))
        )

    def test_it_is_idempotent_and_leaves_an_existing_questionnaire_alone(self):
        seeded, custom = make_edition(2025), make_edition(2026)
        RegistrationSkill.objects.create(
            edition=custom, name_fr="Mien", name_en="Mine", identifier="MINE", weight=3
        )

        migration.seed(apps, None)
        migration.seed(apps, None)

        self.assertEqual(seeded.registrationskill_set.count(), 10)
        self.assertEqual(list(custom.registrationskill_set.values_list("identifier", flat=True)), ["MINE"])
```

- [ ] **Step 3: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration_seed`
Expected: ERROR `ModuleNotFoundError` for the migration.

- [ ] **Step 4: Write the migration**

```python
from django.db import migrations

# (identifier, French label, English name, weight), in form order. Literals on purpose:
# a migration must not change when registration.py later does (a test keeps them equal to
# FORM_PROFILES). The English name is what PlayerRating.name stores.
SKILLS_2025 = [
    ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2),
    ("MOB", "Souplesse et coordination", "Mobility", 3),
    ("ACC", "Précision et lancer", "Accuracy and Aiming", 2),
    ("SPD", "Course et vitesse", "Running and Speed", 4),
    ("STMN", "Endurance longue durée", "Endurance", 4),
    ("CARD", "Cardio", "Cardio", 4),
    ("CULT", "Culture générale", "Cultural Knowledge", 1),
    ("STR", "Force (soulever, pousser, etc)", "Strength", 3),
    ("EXPL", "Explosivité (effort puissant en un temps court)", "Explosiveness", 4),
    ("STRT", "Stratégie et vision de jeu", "Strategy and Game Vision", 2),
]

SKILLS_2024 = [
    ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2),
    ("OBS", "Observation et orientation", "Observation and Orientation", 1),
    ("MOB", "Souplesse et coordination", "Mobility", 3),
    ("ACC", "Précision et lancer", "Accuracy and Aiming", 2),
    ("SPD", "Course et vitesse", "Running and Speed", 4),
    ("STMN", "Endurance et cardio", "Endurance and Cardio", 4),
    ("CULT", "Culture", "Cultural Knowledge", 1),
    ("STR", "Force", "Strength", 3),
    ("EXPL", "Explosivité (effort puissant en un temps court)", "Explosiveness", 4),
    ("STRT", "Stratégie et vision de jeu", "Strategy and Game Vision", 2),
]


def seed(apps, schema_editor):
    """2024 gets its own skill set, every later edition the 2025 one, earlier ones nothing;
    an edition that already has a questionnaire is left alone."""
    Edition = apps.get_model("olympic_warriors", "Edition")
    RegistrationSkill = apps.get_model("olympic_warriors", "RegistrationSkill")
    for edition in Edition.objects.filter(year__gte=2024):
        if RegistrationSkill.objects.filter(edition=edition).exists():
            continue
        skills = SKILLS_2024 if edition.year == 2024 else SKILLS_2025
        RegistrationSkill.objects.bulk_create(
            RegistrationSkill(
                edition=edition,
                identifier=identifier,
                name_fr=name_fr,
                name_en=name_en,
                weight=weight,
                order=order,
            )
            for order, (identifier, name_fr, name_en, weight) in enumerate(skills)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("olympic_warriors", "0041_registration_foundations"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
```

- [ ] **Step 5: Run the tests, then the migration on the dev database**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration_seed
docker compose exec server python manage.py makemigrations --check --dry-run
```

Expected: `OK`, `No changes detected`. (Applying the migration to the dev database with `migrate` is the developer's step; the tests build their own database.)

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/migrations/0042_seed_registration_skills.py server/olympic_warriors/tests/test_registration_seed.py
git commit -m "[FEAT] seed the questionnaire of existing editions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Questionnaire operations

**Files:**
- Create: `server/olympic_warriors/questionnaire.py`
- Test: `server/olympic_warriors/tests/test_questionnaire.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_questionnaire.py`:

```python
"""Copying a questionnaire, locking its skill set, recomputing ratings after a weight change."""
from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, Player, PlayerRating, RegistrationSkill
from olympic_warriors.questionnaire import (
    QuestionnaireError,
    copy_skills,
    recompute_ratings,
    skills_locked,
)


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


def add_skill(edition, identifier, weight, order=0, is_active=True):
    return RegistrationSkill.objects.create(
        edition=edition,
        name_fr=identifier,
        name_en=identifier,
        identifier=identifier,
        weight=weight,
        order=order,
        is_active=is_active,
    )


def add_player(edition, username, rating, global_level, **ratings):
    player = Player.objects.create(
        user=User.objects.create(username=username),
        edition=edition,
        rating=rating,
        global_level=global_level,
    )
    for identifier, value in ratings.items():
        PlayerRating.objects.create(
            player=player, name=identifier, identifier=identifier, rating=value
        )
    return player


class TestSkillsLocked(TestCase):
    def test_locked_once_a_player_has_a_rating(self):
        edition = make_edition(2027)
        self.assertFalse(skills_locked(edition))

        add_player(edition, "ana", 5, 5)
        self.assertFalse(skills_locked(edition))  # a player without ratings does not lock

        add_player(edition, "bob", 5, 5, AAA=6)
        self.assertTrue(skills_locked(edition))

    def test_another_editions_ratings_do_not_lock(self):
        add_player(make_edition(2026), "ana", 5, 5, AAA=6)

        self.assertFalse(skills_locked(make_edition(2027)))


class TestCopySkills(TestCase):
    def test_copies_the_active_skills_of_the_closest_earlier_questionnaire(self):
        make_edition(2024)  # no questionnaire: skipped
        older, previous, new = make_edition(2025), make_edition(2026), make_edition(2027)
        add_skill(older, "OLD", 9)
        add_skill(previous, "AAA", 2, order=0)
        add_skill(previous, "BBB", 3, order=1)
        add_skill(previous, "OFF", 1, order=2, is_active=False)

        year, count = copy_skills(new)

        self.assertEqual((year, count), (2026, 2))
        self.assertEqual(
            list(new.registrationskill_set.values_list("identifier", "weight", "order")),
            [("AAA", 2, 0), ("BBB", 3, 1)],
        )
        self.assertEqual(previous.registrationskill_set.count(), 3)  # untouched

    def test_refuses_an_edition_that_already_has_a_questionnaire(self):
        previous, new = make_edition(2026), make_edition(2027)
        add_skill(previous, "AAA", 2)
        add_skill(new, "ZZZ", 1)

        with self.assertRaises(QuestionnaireError):
            copy_skills(new)
        self.assertEqual(new.registrationskill_set.count(), 1)

    def test_refuses_when_no_earlier_edition_has_a_questionnaire(self):
        with self.assertRaises(QuestionnaireError):
            copy_skills(make_edition(2027))


class TestRecomputeRatings(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        add_skill(self.edition, "AAA", 1)
        add_skill(self.edition, "BBB", 1)

    def test_a_weight_change_moves_the_stored_rating(self):
        # Equal weights: weighted 6, blend (6 + 5 * 4) / 5 = 5.2, stored 5.
        player = add_player(self.edition, "ana", 5, 5, AAA=10, BBB=2)
        RegistrationSkill.objects.filter(identifier="AAA").update(weight=3)

        report = recompute_ratings(self.edition)

        # Weights 3 and 1: weighted 8, blend (8 + 20) / 5 = 5.6, stored 6.
        player.refresh_from_db()
        self.assertEqual(player.rating, 6)
        self.assertEqual((report.updated, report.unchanged), (1, 0))
        self.assertTrue(report.has_questionnaire)

    def test_a_second_run_changes_nothing(self):
        add_player(self.edition, "ana", 5, 5, AAA=10, BBB=2)
        RegistrationSkill.objects.filter(identifier="AAA").update(weight=3)
        recompute_ratings(self.edition)

        report = recompute_ratings(self.edition)

        self.assertEqual((report.updated, report.unchanged), (0, 1))

    def test_players_without_a_global_level_are_skipped_and_counted(self):
        player = add_player(self.edition, "old", 7, None, AAA=10, BBB=2)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual(report.no_global_level, 1)
        self.assertEqual(report.updated, 0)

    def test_players_missing_a_skill_are_skipped_and_counted(self):
        player = add_player(self.edition, "ana", 7, 5, AAA=10)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual(report.incomplete, 1)

    def test_inactive_players_are_left_alone(self):
        player = add_player(self.edition, "ana", 7, 5, AAA=10, BBB=2)
        Player.objects.filter(pk=player.pk).update(is_active=False)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual((report.updated, report.unchanged), (0, 0))

    def test_an_edition_without_a_questionnaire_changes_nothing(self):
        bare = make_edition(2028)
        player = add_player(bare, "ana", 7, 5, AAA=10, BBB=2)

        report = recompute_ratings(bare)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertFalse(report.has_questionnaire)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_questionnaire`
Expected: ERROR `ModuleNotFoundError: olympic_warriors.questionnaire`.

- [ ] **Step 3: Implement.** Create `questionnaire.py`:

```python
"""
The per-edition registration questionnaire: its skills are data (RegistrationSkill), so
organisers copy them from the previous edition, the skill set freezes once players have
answered, and stored ratings are recomputed on demand after a weight change.
"""
from dataclasses import dataclass

from django.db import transaction

from .models import Edition, Player, PlayerRating, RegistrationSkill
from .registration import rate


class QuestionnaireError(ValueError):
    """An organiser action that cannot apply; the message is French, for the admin."""


def skills_locked(edition):
    """True once any player of the edition has a rating: adding, deleting or renaming the
    identifier of a skill would leave existing answers incomplete or orphaned."""
    return PlayerRating.objects.filter(player__edition=edition).exists()


@transaction.atomic
def copy_skills(edition):
    """
    Copy the active skills of the closest earlier edition that has any into an edition
    that has none.

    :return: (source year, number of skills copied).
    :raises QuestionnaireError: the edition already has skills, or no earlier edition does.
    """
    if edition.registrationskill_set.exists():
        raise QuestionnaireError("cette édition a déjà un questionnaire.")
    previous = (
        Edition.objects.filter(
            year__lt=edition.year, is_active=True, registrationskill__is_active=True
        )
        .order_by("-year")
        .distinct()
        .first()
    )
    if previous is None:
        raise QuestionnaireError("aucune édition précédente n'a de questionnaire.")
    skills = list(previous.registrationskill_set.filter(is_active=True))
    RegistrationSkill.objects.bulk_create(
        RegistrationSkill(
            edition=edition,
            name_fr=skill.name_fr,
            name_en=skill.name_en,
            identifier=skill.identifier,
            weight=skill.weight,
            order=skill.order,
        )
        for skill in skills
    )
    return previous.year, len(skills)


@dataclass(frozen=True)
class RecomputeReport:
    """What recompute_ratings did, for the admin message."""

    updated: int
    unchanged: int
    no_global_level: int  # skipped: the raw global answer was never stored (older editions)
    incomplete: int  # skipped: no stored rating for one of the active skills
    has_questionnaire: bool  # False: the edition has no active skill, nothing was touched


def recompute_ratings(edition):
    """
    Recompute Player.rating of the edition's active players from their stored raw skill
    ratings and global level, with the current active skills and weights. Idempotent. A
    player without a stored global level (every edition imported before the in-app
    registration) or without a rating for each active skill is skipped and counted.
    """
    weights = {
        skill.identifier: skill.weight
        for skill in edition.registrationskill_set.filter(is_active=True)
    }
    if not weights:
        return RecomputeReport(0, 0, 0, 0, False)
    players = Player.objects.filter(edition=edition, is_active=True).prefetch_related(
        "playerrating_set"
    )
    changed, unchanged, no_global_level, incomplete = [], 0, 0, 0
    for player in players:
        if player.global_level is None:
            no_global_level += 1
            continue
        ratings = {r.identifier: r.rating for r in player.playerrating_set.all() if r.is_active}
        if not set(weights) <= set(ratings):
            incomplete += 1
            continue
        _, global_rating = rate(ratings, weights, player.global_level)
        rating = round(global_rating)
        if rating == player.rating:
            unchanged += 1
        else:
            player.rating = rating
            changed.append(player)
    Player.objects.bulk_update(changed, ["rating"])
    return RecomputeReport(len(changed), unchanged, no_global_level, incomplete, True)
```

- [ ] **Step 4: Run the tests**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_questionnaire`
Expected: `OK` (11 tests).

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/questionnaire.py server/olympic_warriors/tests/test_questionnaire.py
git commit -m "[FEAT] questionnaire operations: copy, lock, recompute

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The CSV import keeps the new answers

**Files:**
- Modify: `server/olympic_warriors/registration.py`, `server/olympic_warriors/models/Edition.py`
- Test: `server/olympic_warriors/tests/test_registration.py`, `server/olympic_warriors/tests/test_edition_import.py`

The 2026 sample fixture (`tests/fixtures/registration_2026_sample.csv`) already carries the frequency, sports, wishes and confirmation columns: Alice (`two_hours`, wishes « Avec Bob », global 8), Bob (`hour`, global 6), Chloé (`rare`, wishes « Peu importe », global 5), Thomas (`four_hours`, global 9), all confirming « Oui ».

- [ ] **Step 1: Write the failing parser tests.** In `tests/test_registration.py`, extend the import with `CONFIRMED, FREQUENCY, SPORTS, WISHES, clean_text, parse_confirmation, parse_frequency, resolve_extras` and append:

```python
class ExtrasTests(SimpleTestCase):
    def test_finds_the_optional_columns_that_are_present(self):
        extras = resolve_extras(make_df())  # frequency and confirmation, no sports or wishes

        self.assertEqual(
            extras,
            {
                FREQUENCY: "A quelle fréquence pratiques-tu du sport ? ",
                CONFIRMED: "Je confirme que je serai là ! 💪",
            },
        )

    def test_finds_all_four_in_the_2026_wording(self):
        df = pd.DataFrame(
            columns=[
                "A quelle fréquence pratiques-tu du sport ? ",
                "Quels sont les sports que tu as pratiqué (dans toute ta vie et à tout niveau) ?",
                "Idéalement, avec qui souhaiterais-tu être ou ne pas être en équipe ? \n(Ces demandes)",
                "Je confirme que je serai là ! 💪",
            ]
        )

        self.assertEqual(set(resolve_extras(df)), {FREQUENCY, SPORTS, WISHES, CONFIRMED})

    def test_the_2024_wording(self):
        df = pd.DataFrame(
            columns=[
                "Avec qui souhaiterais-tu être ou ne pas être en équipe ? (confidentiel)",
                "J'ai payé mon inscription et je confirme que je serai là.",
            ]
        )

        self.assertEqual(set(resolve_extras(df)), {WISHES, CONFIRMED})

    def test_nothing_is_required(self):
        self.assertEqual(resolve_extras(pd.DataFrame(columns=["Prénom et Nom"])), {})

    def test_parse_frequency_maps_the_five_answers(self):
        answers = {
            "Moins d'une fois par mois": "rare",
            "Moins d'une fois par semaine mais plusieurs fois par mois": "monthly",
            "Environ une heure par semaine": "hour",
            "Au moins deux heures par semaine": "two_hours",
            "Au moins quatre heures par semaine": "four_hours",
        }
        for text, code in answers.items():
            self.assertEqual(parse_frequency(text), code)

    def test_parse_frequency_tolerates_spacing_case_and_curly_apostrophes(self):
        self.assertEqual(parse_frequency("  moins d’une fois par MOIS "), "rare")

    def test_parse_frequency_leaves_the_unknown_blank(self):
        self.assertEqual(parse_frequency("Souvent"), "")
        self.assertEqual(parse_frequency(float("nan")), "")

    def test_the_frequency_codes_are_the_models(self):
        from olympic_warriors.models.Player import SportFrequency  # imports Django models

        codes = {parse_frequency(t) for t in (
            "Moins d'une fois par mois", "Environ une heure par semaine",
            "Au moins deux heures par semaine", "Au moins quatre heures par semaine",
            "Moins d'une fois par semaine mais plusieurs fois par mois",
        )}
        self.assertEqual(codes, set(SportFrequency.values))

    def test_parse_confirmation(self):
        self.assertTrue(parse_confirmation("Oui"))
        self.assertTrue(parse_confirmation(" oui "))
        self.assertFalse(parse_confirmation("Non"))
        self.assertFalse(parse_confirmation(float("nan")))

    def test_clean_text(self):
        self.assertEqual(clean_text("  Avec Bob \n"), "Avec Bob")
        self.assertEqual(clean_text(float("nan")), "")
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration.ExtrasTests`
Expected: ERROR `ImportError: cannot import name 'CONFIRMED'`.

- [ ] **Step 3: Implement the parsers in `registration.py`.** Add after the `GLOBAL_LEVEL_PREFIX` constant:

```python
# Optional columns that rode along in every form but were never stored: how often the
# person does sport, their sports history, who they want (or not) in their team, and the
# "I will be there" confirmation. Matched like the others, by a stable fragment; a form
# without one simply leaves the answer blank.
FREQUENCY = "Frequency"
SPORTS = "Sports"
WISHES = "Wishes"
CONFIRMED = "Confirmed"

FREQUENCY_HEADER_PREFIX = "A quelle fréquence pratiques-tu du sport"
SPORTS_HEADER_PREFIX = "Quels sont les sports que tu as pratiqué"
WISHES_FRAGMENT = "souhaiterais-tu être ou ne pas être en équipe"
CONFIRMATION_PREFIXES = ("Je confirme que je serai là", "J'ai payé mon inscription")

# What the sports history of an imported row is filed under (PlayerSport.sport).
IMPORTED_SPORT = "Historique (import)"
```

Add after `parse_name`:

```python
def _normalise(text):
    """Lower-case, single-spaced, straight apostrophes: how answers are compared."""
    return " ".join(str(text).replace("’", "'").lower().split())


# Normalised form answer -> SportFrequency value (a test keeps the values equal).
FREQUENCIES = {
    "moins d'une fois par mois": "rare",
    "moins d'une fois par semaine mais plusieurs fois par mois": "monthly",
    "environ une heure par semaine": "hour",
    "au moins deux heures par semaine": "two_hours",
    "au moins quatre heures par semaine": "four_hours",
}


def parse_frequency(raw):
    """The SportFrequency value of a form answer, "" for a blank or unknown one."""
    return FREQUENCIES.get(_normalise(raw), "") if isinstance(raw, str) else ""


def parse_confirmation(raw):
    """True for a "Oui" in the confirmation column."""
    return isinstance(raw, str) and _normalise(raw) in {"oui", "yes"}


def clean_text(raw):
    """A free-text cell, stripped; "" for a blank one (pandas NaN)."""
    return raw.strip() if isinstance(raw, str) else ""


def resolve_extras(df):
    """
    Map the optional answers to the DataFrame's actual headers.

    :return: {FREQUENCY | SPORTS | WISHES | CONFIRMED: header} for the columns present.
    :raises ValueError: if a fragment matches two headers.
    """
    headers = list(df.columns)
    wanted = {
        FREQUENCY: lambda h: str(h).strip().startswith(FREQUENCY_HEADER_PREFIX),
        SPORTS: lambda h: str(h).strip().startswith(SPORTS_HEADER_PREFIX),
        WISHES: lambda h: WISHES_FRAGMENT in str(h),
        CONFIRMED: lambda h: str(h).strip().startswith(CONFIRMATION_PREFIXES),
    }
    extras = {}
    for key, predicate in wanted.items():
        header = _find_column(headers, predicate, key)
        if header is not None:
            extras[key] = header
    return extras
```

- [ ] **Step 4: Run the parser tests**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration`
Expected: `OK`. (`test_the_frequency_codes_are_the_models` imports the Django models inside a `SimpleTestCase`; that is fine because it only reads the enum, no database.)

- [ ] **Step 5: Write the failing import tests.** In `tests/test_edition_import.py`, add `PlayerSport` to the models import and append to `EditionImportTests`:

```python
    def test_stores_the_global_level_and_the_private_answers(self):
        alice = Player.objects.get(user__username="alicemartin", edition=self.edition)

        self.assertEqual(alice.global_level, 8)
        self.assertEqual(alice.sport_frequency, "two_hours")
        self.assertEqual(alice.team_wishes, "Avec Bob")
        self.assertTrue(alice.attendance_confirmed)
        self.assertEqual(alice.dietary_restrictions, "")  # not in the form
        chloe = Player.objects.get(user__username="chloédelatour", edition=self.edition)
        self.assertEqual(chloe.sport_frequency, "rare")
        self.assertEqual(chloe.global_level, 5)

    def test_keeps_the_sports_history_whole_as_one_row(self):
        alice = Player.objects.get(user__username="alicemartin", edition=self.edition)

        sports = list(alice.playersport_set.all())
        self.assertEqual([s.sport for s in sports], ["Historique (import)"])
        self.assertEqual(sports[0].notes, "Escalade - 10 ans - amateur")

    def test_reimport_replaces_the_answers_without_duplicating_the_sports_row(self):
        original = FIXTURE.read_text(encoding="utf-8")
        changed = original.replace("Avec Bob", "Plutôt avec Thomas")
        self.assertNotEqual(changed, original)
        self.edition.registration_form = SimpleUploadedFile("changed.csv", changed.encode("utf-8"))
        self.edition.save()

        alice = Player.objects.get(user__username="alicemartin", edition=self.edition)
        self.assertEqual(alice.team_wishes, "Plutôt avec Thomas")
        self.assertEqual(alice.playersport_set.count(), 1)
        self.assertEqual(PlayerSport.objects.count(), 4)
```

- [ ] **Step 6: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_edition_import.EditionImportTests`
Expected: the three new tests FAIL (`global_level` is `None`, no `PlayerSport`).

- [ ] **Step 7: Implement in `models/Edition.py`.** Change the registration imports:

```python
from ..registration import (
    CONFIRMED,
    EMAIL,
    FREQUENCY,
    GLOBAL_LEVEL,
    IMPORTED_SPORT,
    NAME,
    SPORTS,
    WISHES,
    clean_text,
    compute_ratings,
    parse_confirmation,
    parse_frequency,
    parse_name,
    resolve_columns,
    resolve_extras,
)
from .Player import Player, PlayerRating, PlayerSport
```

In `create_players_from_registration_form`, right after `columns, ratings = resolve_columns(df)` add `extras = resolve_extras(df)` (before `df = compute_ratings(...)` rebinds `df`; the extras headers are not renamed by it). Replace the `update_or_create` of the player and add the sports row:

```python
                try:
                    defaults = {
                        "rating": round(row["Global_Rating"]),
                        "global_level": round(row[GLOBAL_LEVEL]),
                        "is_active": True,
                    }
                    if FREQUENCY in extras:
                        defaults["sport_frequency"] = parse_frequency(row[extras[FREQUENCY]])
                    if WISHES in extras:
                        defaults["team_wishes"] = clean_text(row[extras[WISHES]])
                    if CONFIRMED in extras:
                        defaults["attendance_confirmed"] = parse_confirmation(
                            row[extras[CONFIRMED]]
                        )
                    player, _ = Player.objects.update_or_create(
                        user=user, edition=self, defaults=defaults
                    )
                    history = clean_text(row[extras[SPORTS]]) if SPORTS in extras else ""
                    if history:
                        PlayerSport.objects.update_or_create(
                            player=player, sport=IMPORTED_SPORT, defaults={"notes": history}
                        )
                    for name, spec in ratings.items():
                        PlayerRating.objects.update_or_create(
                            player=player,
                            identifier=spec["id"],
                            defaults={"name": name, "rating": row[name], "is_active": True},
                        )
                except MultipleObjectsReturned as exc:
                    # Editions imported before ratings were update-or-created may
                    # hold duplicate (player, identifier) rows.
                    raise ValueError(
                        f"Duplicate player or rating rows already exist for {username!r}; "
                        "remove them in the admin before re-importing."
                    ) from exc
```

The `PlayerRating` loop and the `except` are the existing code, shown here so nothing is lost; only the lines above them change.

- [ ] **Step 8: Run all import tests**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_edition_import olympic_warriors.tests.test_registration`
Expected: `OK`. The 2024 fixture has no sports column header match issues: it carries frequency, sports, wishes and payment columns, so `EditionImport2024Tests` also exercises the extras.

- [ ] **Step 9: Commit**

```bash
git add server/olympic_warriors/registration.py server/olympic_warriors/models/Edition.py server/olympic_warriors/tests/test_registration.py server/olympic_warriors/tests/test_edition_import.py
git commit -m "[FEAT] CSV import keeps the global level and the private answers

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The edition transfer

**Files:**
- Modify: `server/olympic_warriors/transfer.py`
- Test: `server/olympic_warriors/tests/test_transfer.py`

The export serialises every concrete field of every exported row, so the new private `Player` fields would travel without this task. `global_level` travels (it is part of the rating); `PlayerSport` is a root model that must be listed in `NOT_EXPORTED` or `test_tables_cover_every_root_model` fails.

- [ ] **Step 1: Update and add tests.** In `tests/test_transfer.py`: add `PlayerSport, RegistrationSkill` to the models import; in `build_edition`, after `PlayerRating` creation add:

```python
    RegistrationSkill.objects.create(
        edition=edition, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
    )
    RegistrationSkill.objects.create(
        edition=edition, name_fr="Force", name_en="Strength", identifier="STR", weight=3, order=1
    )
    Player.objects.filter(pk=p_alice.pk).update(
        global_level=8,
        dietary_restrictions="Végétarienne",
        sport_frequency="two_hours",
        team_wishes="Avec Bob",
        attendance_confirmed=True,
    )
    PlayerSport.objects.create(player=p_alice, sport="Judo", notes="Ceinture orange")
```

In `test_fixture_shape` add `"RegistrationSkill": 2,` to the expected `counts` dict. Append to `ExportEditionTests`:

```python
    def test_personal_registration_answers_are_not_exported(self):
        doc = export_edition(self.edition.year)

        alice = next(p for p in doc["tables"]["Player"] if p["user"] == "alice")
        for private in ("dietary_restrictions", "sport_frequency", "team_wishes", "attendance_confirmed"):
            self.assertNotIn(private, alice)
        self.assertEqual(alice["global_level"], 8)  # part of the rating, it travels
        self.assertNotIn("PlayerSport", doc["tables"])
        self.assertNotIn("Végétarienne", str(doc))
        self.assertNotIn("Ceinture orange", str(doc))

    def test_the_questionnaire_is_exported(self):
        doc = export_edition(self.edition.year)

        skills = doc["tables"]["RegistrationSkill"]
        self.assertEqual([s["identifier"] for s in skills], ["CARD", "STR"])
        self.assertNotIn("edition", skills[0])
```

Append to `ImportEditionTests`:

```python
    def test_the_questionnaire_round_trips_and_private_answers_come_back_blank(self):
        import_edition(self.document)

        edition = Edition.objects.get(year=2024)
        self.assertEqual(
            list(edition.registrationskill_set.values_list("identifier", "weight")),
            [("CARD", 4), ("STR", 3)],
        )
        alice = Player.objects.get(edition=edition, user__username="alice")
        self.assertEqual(alice.global_level, 8)
        self.assertEqual(alice.dietary_restrictions, "")
        self.assertFalse(alice.attendance_confirmed)
        self.assertEqual(PlayerSport.objects.count(), 0)
```

(`setUp` deleted the 2024 edition, which cascades its players' sports, so `PlayerSport` is empty after the import.)

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_transfer`
Expected: failures: `test_tables_cover_every_root_model` (unlisted `PlayerSport` and `RegistrationSkill`), the private fields exported, `KeyError: 'RegistrationSkill'`.

- [ ] **Step 3: Implement.** In `transfer.py` add `PlayerSport, RegistrationSkill` handling:

```python
from .models import (
    BlindtestGuess,
    BlindtestRound,
    Discipline,
    Edition,
    Game,
    GameEvent,
    Player,
    PlayerRating,
    RegistrationSkill,
    Team,
    TeamResult,
    TeamSportRound,
)
```

In `TABLES`, add after the `Team` entry:

```python
    ("RegistrationSkill", RegistrationSkill, "edition"),
```

Replace `NOT_EXPORTED` and its comment:

```python
# Root models an edition export leaves out on purpose: badges and their progress
# (BadgeProgress) are derived from the edition's data, and badges.refresh() rebuilds them
# after an import (import_edition runs it). Manual badges are not transferred, and
# --replace cascade-deletes the replaced edition's ones. A UserProfile (photo, showcase,
# claim) is about a person, not an edition, and lives on prod only. PlayerSport is a
# person's private sports history, like the Player fields in PRIVATE_FIELDS.
NOT_EXPORTED = frozenset({"Badge", "BadgeProgress", "BadgeRefresh", "UserProfile", "PlayerSport"})

# Personal answers given at registration never leave their database; an import leaves
# them at the model default. (Player.global_level is not here: it is part of the rating.)
PRIVATE_FIELDS = {
    "Player": frozenset(
        {"dietary_restrictions", "sport_frequency", "team_wishes", "attendance_confirmed"}
    )
}
```

In `_serialize_fields`, skip the private fields:

```python
def _serialize_fields(obj, fields):
    """Concrete fields of obj as a dict: no pk, no edition link, no private answer, FKs as
    _id or username."""
    private = PRIVATE_FIELDS.get(type(obj).__name__, ())
    row = {}
    for field in fields:
        if field.primary_key or field.name == "edition" or field.name in private:
            continue
```

(Keep the rest of the function body unchanged.)

- [ ] **Step 4: Run**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_transfer`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/transfer.py server/olympic_warriors/tests/test_transfer.py
git commit -m "[FEAT] edition transfer: export the questionnaire, never the private answers

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Admin

**Files:**
- Modify: `server/olympic_warriors/admin.py`, `server/olympic_warriors/tests/test_player_admin.py`
- Test: `server/olympic_warriors/tests/test_registration_admin.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_registration_admin.py`:

```python
"""The questionnaire in the admin: the locked skills inline, the two Edition actions, the
Player columns and filters, the sports inline."""
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.test import TestCase, override_settings

from olympic_warriors.admin import LockedSkillFormSet
from olympic_warriors.models import Edition, Player, PlayerRating, PlayerSport, RegistrationSkill

EDITIONS = "/admin/olympic_warriors/edition/"
PLAYERS = "/admin/olympic_warriors/player/"
FIELDS = ("order", "identifier", "name_fr", "name_en", "weight", "is_active")


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


def make_skill(edition, identifier="CARD", weight=4, order=0):
    return RegistrationSkill.objects.create(
        edition=edition,
        name_fr=identifier,
        name_en=identifier,
        identifier=identifier,
        weight=weight,
        order=order,
    )


def skill_row(skill, **changes):
    """The posted values of an existing skill, with changes applied."""
    row = {
        "id": skill.pk,
        "order": skill.order,
        "identifier": skill.identifier,
        "name_fr": skill.name_fr,
        "name_en": skill.name_en,
        "weight": skill.weight,
        "is_active": "on",
    }
    row.update(changes)
    return row


NEW_ROW = {
    "order": 5,
    "identifier": "NEW",
    "name_fr": "Nouvelle",
    "name_en": "New",
    "weight": 2,
    "is_active": "on",
}


def bound_formset(edition, rows):
    """LockedSkillFormSet bound to posted rows; rows with an id come first."""
    factory = inlineformset_factory(
        Edition, RegistrationSkill, formset=LockedSkillFormSet, fields=FIELDS, extra=0
    )
    prefix = factory.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": str(sum("id" in row for row in rows)),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        data[f"{prefix}-{index}-edition"] = str(edition.pk)
        for key, value in row.items():
            data[f"{prefix}-{index}-{key}"] = str(value)
    return factory(data, instance=edition)


class TestLockedSkillFormSet(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        self.skill = make_skill(self.edition)

    def lock(self):
        player = Player.objects.create(
            user=User.objects.create(username="ana"), edition=self.edition, rating=5
        )
        PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=6)

    def test_free_while_nobody_has_answered(self):
        formset = bound_formset(self.edition, [skill_row(self.skill, identifier="CRD"), NEW_ROW])
        self.assertTrue(formset.is_valid(), formset.errors)

        deletion = bound_formset(self.edition, [skill_row(self.skill, DELETE="on")])
        self.assertTrue(deletion.is_valid(), deletion.errors)

    def test_locked_allows_weights_labels_order_and_activation(self):
        self.lock()
        row = skill_row(self.skill, weight=9, name_fr="Cardio !", order=3)
        row.pop("is_active")  # switched off

        formset = bound_formset(self.edition, [row])

        self.assertTrue(formset.is_valid(), formset.errors)

    def test_locked_refuses_a_new_skill(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill), NEW_ROW])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_locked_refuses_a_deletion(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill, DELETE="on")])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_locked_refuses_an_identifier_change(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill, identifier="CRD")])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_an_unsaved_edition_is_never_locked(self):
        factory = inlineformset_factory(
            Edition, RegistrationSkill, formset=LockedSkillFormSet, fields=FIELDS, extra=1
        )
        formset = factory(instance=Edition())

        self.assertEqual(len(formset.forms), 1)


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestEditionAdmin(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.previous = make_edition(2026)
        make_skill(self.previous, "CARD", 4)
        make_skill(self.previous, "STR", 3, order=1)
        self.current = make_edition(2027)

    def run_action(self, action, *editions):
        response = self.client.post(
            EDITIONS,
            {"action": action, "_selected_action": [e.pk for e in editions], "index": 0},
            follow=True,
        )
        return response, [str(m) for m in response.context["messages"]]

    def test_the_change_page_renders_with_dates_confirmed_and_the_skills(self):
        response = self.client.get(f"{EDITIONS}{self.previous.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dates_confirmed")
        self.assertContains(response, "registrationskill_set-TOTAL_FORMS")

    def test_copy_action(self):
        _, messages = self.run_action("copy_questionnaire", self.current)

        self.assertEqual(messages, ["2027 : 2 compétence(s) copiée(s) depuis 2026."])
        self.assertEqual(self.current.registrationskill_set.count(), 2)

    def test_copy_action_reports_an_edition_that_already_has_skills(self):
        _, messages = self.run_action("copy_questionnaire", self.previous)

        self.assertEqual(messages, ["2026 : cette édition a déjà un questionnaire."])

    def test_recompute_action_reports_each_edition(self):
        player = Player.objects.create(
            user=User.objects.create(username="ana"), edition=self.previous,
            rating=5, global_level=5,
        )
        PlayerRating.objects.create(player=player, name="C", identifier="CARD", rating=10)
        PlayerRating.objects.create(player=player, name="S", identifier="STR", rating=2)
        old = Player.objects.create(
            user=User.objects.create(username="old"), edition=self.previous, rating=7
        )
        PlayerRating.objects.create(player=old, name="C", identifier="CARD", rating=10)

        _, messages = self.run_action("recompute_player_ratings", self.previous, self.current)

        # CARD 10 (4), STR 2 (3): weighted 6.57, blend (6.57 + 20) / 5 = 5.31, stored 5: unchanged.
        self.assertEqual(
            messages,
            [
                "2026 : 0 note(s) mise(s) à jour, 1 inchangée(s), "
                "1 joueur(s) ignoré(s) : réponse globale inconnue.",
                "2027 : Aucun questionnaire pour cette édition.",
            ],
        )


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestPlayerAdminRegistration(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        edition = make_edition(2027)
        self.vegan = Player.objects.create(
            user=User.objects.create(username="ana", first_name="Ana"), edition=edition,
            rating=5, dietary_restrictions="Végane", attendance_confirmed=True,
            sport_frequency="hour",
        )
        self.plain = Player.objects.create(
            user=User.objects.create(username="bob", first_name="Bob"), edition=edition, rating=5,
        )

    def names(self, response):
        return {str(p) for p in response.context["cl"].result_list}

    def test_dietary_filter(self):
        yes = self.client.get(PLAYERS, {"dietary": "yes", "is_active__exact": "1"})
        no = self.client.get(PLAYERS, {"dietary": "no", "is_active__exact": "1"})

        self.assertEqual(self.names(yes), {"Ana "})
        self.assertEqual(self.names(no), {"Bob "})

    def test_confirmation_and_frequency_filters(self):
        confirmed = self.client.get(PLAYERS, {"attendance_confirmed__exact": "1", "is_active__exact": "1"})
        weekly = self.client.get(PLAYERS, {"sport_frequency__exact": "hour", "is_active__exact": "1"})

        self.assertEqual(self.names(confirmed), {"Ana "})
        self.assertEqual(self.names(weekly), {"Ana "})

    def test_the_change_page_has_the_sports_inline(self):
        PlayerSport.objects.create(player=self.vegan, sport="Judo")

        response = self.client.get(f"{PLAYERS}{self.vegan.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "playersport_set-TOTAL_FORMS")
        self.assertContains(response, "Judo")
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration_admin`
Expected: ERROR `ImportError: cannot import name 'LockedSkillFormSet'`.

- [ ] **Step 3: Implement in `admin.py`.** Imports: add `BaseInlineFormSet` to the `django.forms` import (`from django.forms import BaseInlineFormSet, ModelChoiceField, ModelForm`), `PlayerSport, RegistrationSkill` to the models import list, and:

```python
from .questionnaire import QuestionnaireError, copy_skills, recompute_ratings, skills_locked
```

Add after `PlayerRatingInline`:

```python
class PlayerSportInline(TabularInline):
    """
    Inline for the PlayerSport model to be accessed from the Player model.
    """

    model = PlayerSport
    extra = 0


class LockedSkillFormSet(BaseInlineFormSet):
    """
    The skills of an edition whose players have answered: weights, labels, order and
    activation stay editable, but adding or deleting a skill or changing an identifier
    would leave stored answers incomplete or orphaned, so it is refused.
    """

    LOCKED = (
        "Le jeu de compétences est verrouillé : des joueurs ont déjà une note pour cette "
        "édition. Seuls les poids, libellés, l'ordre et l'activation sont modifiables."
    )

    def clean(self):
        super().clean()
        if self.instance.pk is None or not skills_locked(self.instance):
            return
        for form in self.forms:
            existing = form.instance.pk is not None
            if existing and (self._should_delete_form(form) or "identifier" in form.changed_data):
                raise ValidationError(self.LOCKED)
            if not existing and form.has_changed():
                raise ValidationError(self.LOCKED)


class RegistrationSkillInline(TabularInline):
    """
    Inline for the RegistrationSkill model to be accessed from the Edition model.
    """

    model = RegistrationSkill
    formset = LockedSkillFormSet
    fields = ("order", "identifier", "name_fr", "name_en", "weight", "is_active")

    def get_extra(self, request, obj=None, **kwargs):
        """No blank rows on a locked edition: adding is refused there anyway."""
        return 0 if obj is not None and skills_locked(obj) else 3
```

Add the two actions next to `refresh_badges`:

```python
@action(description="Copier le questionnaire de l'édition précédente", permissions=["change"])
def copy_questionnaire(modeladmin, request, queryset):
    """Seed an edition's skills from the closest earlier edition that has any."""
    for edition in queryset.order_by("year"):
        try:
            year, count = copy_skills(edition)
        except QuestionnaireError as error:
            modeladmin.message_user(request, f"{edition.year} : {error}", messages.WARNING)
        else:
            modeladmin.message_user(
                request, f"{edition.year} : {count} compétence(s) copiée(s) depuis {year}."
            )


@action(description="Recalculer les notes", permissions=["change"])
def recompute_player_ratings(modeladmin, request, queryset):
    """Recompute Player.rating from the stored answers with the current weights, after a
    weight change. Any edition; players without a stored global answer are skipped."""
    for edition in queryset.order_by("year"):
        report = recompute_ratings(edition)
        if not report.has_questionnaire:
            modeladmin.message_user(
                request,
                f"{edition.year} : Aucun questionnaire pour cette édition.",
                messages.WARNING,
            )
            continue
        text = (
            f"{edition.year} : {report.updated} note(s) mise(s) à jour, "
            f"{report.unchanged} inchangée(s)"
        )
        if report.no_global_level:
            text += f", {report.no_global_level} joueur(s) ignoré(s) : réponse globale inconnue"
        if report.incomplete:
            text += f", {report.incomplete} joueur(s) ignoré(s) : compétences manquantes"
        modeladmin.message_user(request, text + ".")
```

Replace `EditionAdmin`'s attributes (keep `changelist_view`):

```python
    list_display = ["year"]
    list_filter = ["is_active"]
    search_fields = ["year"]
    actions = [refresh_badges, copy_questionnaire, recompute_player_ratings]
    inlines = [RegistrationSkillInline]
    fields = (
        "year",
        "host",
        "start_date",
        "end_date",
        "dates_confirmed",
        "photos_url",
        "registration_form",
        "is_active",
    )
```

Add the dietary filter above `PlayerAdmin` and change `PlayerAdmin`:

```python
class DietaryFilter(SimpleListFilter):
    """Players who gave dietary restrictions, or none."""

    title = "restrictions alimentaires"
    parameter_name = "dietary"

    def lookups(self, request, model_admin):
        return (("yes", "Renseignées"), ("no", "Aucune"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(dietary_restrictions="")
        if self.value() == "no":
            return queryset.filter(dietary_restrictions="")
        return queryset
```

In `PlayerAdmin`: `list_display = ["user", "rating", "team", "edition", "attendance_confirmed", "has_dietary"]`, `list_filter = ["team", "edition", "is_active", "attendance_confirmed", "sport_frequency", DietaryFilter]`, `inlines = [PlayerRatingInline, PlayerSportInline]`, and the column:

```python
    @display(boolean=True, description="Restrictions alimentaires")
    def has_dietary(self, obj):
        """Whether the player gave dietary restrictions."""
        return bool(obj.dietary_restrictions)
```

- [ ] **Step 4: Fix the player admin tests' management forms.** In `tests/test_player_admin.py`, extend `NO_RATINGS` (rename nothing) with the new inline:

```python
    "playersport_set-TOTAL_FORMS": "0",
    "playersport_set-INITIAL_FORMS": "0",
    "playersport_set-MIN_NUM_FORMS": "0",
    "playersport_set-MAX_NUM_FORMS": "1000",
```

and update its comment to « The Player change/add form always carries the PlayerRatingInline and PlayerSportInline management forms ».

- [ ] **Step 5: Run the admin tests and every other admin-touching module**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration_admin olympic_warriors.tests.test_player_admin olympic_warriors.tests.test_badge_refresh olympic_warriors.tests.test_admin olympic_warriors.tests.test_claims
```

Expected: `OK`. If the expected-message test for the recompute action fails on arithmetic, recompute by hand: CARD 10 (weight 4), STR 2 (weight 3): weighted = 46/7 = 6.571; blend (6.571 + 5 × 4)/5 = 5.31; stored 5, so unchanged. Fix the test's comment, not the maths.

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/admin.py server/olympic_warriors/tests/test_registration_admin.py server/olympic_warriors/tests/test_player_admin.py
git commit -m "[FEAT] admin: questionnaire inline with locking, copy and recompute actions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The public payload and the privacy walk

**Files:**
- Modify: `server/olympic_warriors/serializer.py`, `server/olympic_warriors/tests/test_summary.py`, `server/olympic_warriors/tests/test_showcase.py`
- Test: `server/olympic_warriors/tests/test_registration_models.py`

- [ ] **Step 1: Write the failing tests.** In `tests/test_summary.py` change `test_edition_fields` so the expected dict gains `"dates_confirmed": True,` after `"photos_url"`. In `tests/test_showcase.py` extend the set:

```python
PRIVATE_KEYS = {
    "username", "email", "photo_locked", "claimed_at", "updated_at", "codes", "pins",
    "global_level", "dietary_restrictions", "sport_frequency", "team_wishes",
    "attendance_confirmed",
}
```

Append to `tests/test_registration_models.py`:

```python
from olympic_warriors.tests.test_showcase import PRIVATE_KEYS, keys_in


class TestPrivateAnswersStayPrivate(TestCase):
    def test_no_public_payload_carries_a_registration_answer(self):
        edition = make_edition(2026)
        player = Player.objects.create(
            user=User.objects.create(username="ana", first_name="Ana", last_name="Lopez"),
            edition=edition,
            rating=5,
            global_level=7,
            dietary_restrictions="Sans gluten",
            sport_frequency="hour",
            team_wishes="Avec Bob",
            attendance_confirmed=True,
        )
        PlayerSport.objects.create(player=player, sport="Judo", notes="Ceinture orange")

        for url in ("/edition/year/2026/summary/", "/profiles/", f"/profile/{player.user_id}/"):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(keys_in(response.json()) & PRIVATE_KEYS, set())
                for secret in ("Sans gluten", "Avec Bob", "Ceinture orange"):
                    self.assertNotIn(secret.encode(), response.content)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_summary.TestEditionSummarySerializer olympic_warriors.tests.test_registration_models`
Expected: `test_edition_fields` FAILS (no `dates_confirmed`); the privacy test passes already (explicit field lists), which is the point: it guards the future.

- [ ] **Step 3: Implement.** In `serializer.py`:

```python
class SummaryEditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ("id", "year", "host", "start_date", "end_date", "photos_url", "dates_confirmed")
```

- [ ] **Step 4: Run the server suite's affected modules, then the whole suite**

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_summary olympic_warriors.tests.test_showcase olympic_warriors.tests.test_registration_models
docker compose exec server python manage.py test
```

Expected: `OK` for both. Any other test that compares the summary's edition dict or `/editions/` payload exactly will fail here: fix its expected dict (`dates_confirmed: True`, and for `/editions/` the new `EditionSerializer` fields), do not loosen the assertion.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/serializer.py server/olympic_warriors/tests
git commit -m "[FEAT] summary edition carries dates_confirmed; privacy walk covers the new answers

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The hub hides unconfirmed dates

**Files:**
- Modify: `front/src/lib/components/EditionHub.svelte`, `front/src/lib/i18n/fr.js`, `front/src/lib/i18n/en.js`
- Test: `front/src/lib/components/EditionHub.test.js`

An older server does not send `dates_confirmed`; only an explicit `false` hides the dates.

- [ ] **Step 1: Write the failing tests.** Append inside the `describe('EditionHub', ...)` block of `EditionHub.test.js`:

```js
	describe('with unconfirmed dates', () => {
		const unconfirmed = { ...summary, edition: { ...summary.edition, dates_confirmed: false } };

		it('hides the countdown and the date range', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions });

			expect(screen.getByText('Paris · Dates to be announced')).toBeInTheDocument();
			expect(screen.queryByText('Days')).toBeNull();
			expect(screen.queryByText(/September/)).toBeNull();
		});

		it('never offers the ranking, even once the provisional start has passed', () => {
			vi.setSystemTime(new Date('2026-09-19T08:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions });

			expect(screen.queryByRole('link', { name: 'Ranking' })).toBeNull();
			expect(screen.getByRole('link', { name: 'Players' })).toBeInTheDocument();
		});

		it('says it in French', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary: unconfirmed, editions }, 'fr');

			expect(screen.getByText('Paris · Dates à venir')).toBeInTheDocument();
		});

		it('treats a payload without the flag as confirmed', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions });

			expect(screen.getByText('Paris · 19 – 20 September 2026')).toBeInTheDocument();
		});
	});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd front && npx vitest run src/lib/components/EditionHub.test.js`
Expected: the three unconfirmed tests FAIL; the last passes.

- [ ] **Step 3: Implement.** In `EditionHub.svelte` replace the `phase` and `.where` lines:

```svelte
	// An explicit false only: a server that predates the flag sends none.
	$: confirmed = edition.dates_confirmed !== false;
	$: phase = confirmed ? editionPhase(edition, now) : 'upcoming';
	$: parts = countdownParts(edition, now);
```

```svelte
<p class="where">
	{edition.host} · {confirmed
		? formatDateRange(edition.start_date, edition.end_date, locale)
		: t('hub.datesTbc')}
</p>
```

and wrap the countdown: `{#if phase === 'upcoming'}` becomes `{#if confirmed && phase === 'upcoming'}`. Add the keys beside `hub.seconds`: in `fr.js` `'hub.datesTbc': 'Dates à venir',` and in `en.js` `'hub.datesTbc': 'Dates to be announced',`.

- [ ] **Step 4: Run the front tests and the build**

```bash
cd front && npm test && npm run build
```

Expected: all Vitest files pass (the parity test checks the new key in both dictionaries) and the build succeeds.

- [ ] **Step 5: Commit**

```bash
git add front/src
git commit -m "[FEAT] hub: Dates à venir while the dates are unconfirmed

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Documentation and final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document the questionnaire.** In `CLAUDE.md`, after the paragraph that starts `**Registration import:**`, add:

```markdown
**Registration questionnaire** (spec `2026-10-04-in-app-registration-design.md`, slice 1): an edition's skills are data, `RegistrationSkill` (`name_fr`, `name_en`, `identifier`, `weight`, `order`, `is_active`; unique `(edition, identifier)`), seeded by migration `0042` (2024 from the 2024 profile, every later edition from the 2025 one, earlier ones nothing); `FORM_PROFILES` stays only for importing old CSVs. `registration.rate(skills, weights, global_level)` is the one rating formula (weights-averaged skills clipped to 1..10, ×2.5 when under 4 with a global answer above 4, blended `(weighted + 4 × global) / 5`, rounded to two decimals; `Player.rating` is its rounded value), shared by the CSV import and `questionnaire.recompute_ratings`. `Player` gains private per-edition answers: `global_level` (the raw global answer, stored because the blend cannot be inverted; null on editions imported before it), `dietary_restrictions`, `sport_frequency` (`SportFrequency`, the five answers of the form), `team_wishes`, `attendance_confirmed` (the self-declared « payé et présent » tick), and `PlayerSport` rows (sport, level, practice, `duration_months`, `notes`; `notes` is a `TextField` with a 200-character validator so the import keeps a whole history). The CSV import fills `global_level`, frequency, wishes and the tick through `resolve_extras` (optional columns, matched by header fragment) and files the free-text sports answer as one `PlayerSport` row named « Historique (import) ». None of it is in a public payload (`PRIVATE_KEYS` in `test_showcase.py`), and `transfer.PRIVATE_FIELDS`/`NOT_EXPORTED` keep it out of `export_edition` (`global_level` travels; `RegistrationSkill` is exported). `Edition` gains `dates_confirmed` (default true): while it is false the hub shows « Dates à venir » instead of the date range and countdown and never offers the ranking, and `SummaryEditionSerializer` carries it. Admin: the Edition page edits them with a `RegistrationSkill` inline whose `LockedSkillFormSet` refuses adding, deleting or re-identifying a skill once any player of the edition has a `PlayerRating` (`questionnaire.skills_locked`), plus the actions « Copier le questionnaire de l'édition précédente » (`copy_skills`) and « Recalculer les notes » (`recompute_ratings`, any edition, skipping players without a `global_level` or missing a skill and counting them); the Player admin shows the tick and a dietary column, filters on them and on frequency, and edits the sports inline. Not built yet (slices 2 and 3): the registration window and form texts on `Edition`, invitations, the late pass, the `/registration/` API, the open/closed rule and the `/register` page; `accounts.deactivate` does not yet clear the private answers either (slice 2).
```

- [ ] **Step 2: Run every check CI runs**

```bash
docker compose exec server python manage.py makemigrations --check --dry-run
docker compose exec server python manage.py test
cd front && npm ci && npm test && npm run build
```

Expected: `No changes detected`; the whole Django suite `OK`; every Vitest file passes and the build succeeds.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOCS] document the registration questionnaire

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Hand over.** Report to Hugo: the branch (`feat/registration-foundations`, cut from `docs/registration-design`), the test results, the prod check from Task 3 (done or still open), and the deploy order for this slice: `migrate` (0041, 0042), rebuild the server image, then the front. Do not open the PR to `dev` or touch `main` unasked.

---

## Self-review (spec coverage for slice 1)

| Spec requirement | Task |
|---|---|
| `RegistrationSkill`, locked skill set, weights/labels editable | 2, 4, 7 |
| Copy action; recompute action skipping players without `global_level`, any edition | 4, 7 |
| Seeding by year (2024 profile, 2025+ profile, nothing earlier), prod check | 3 |
| Edition fields incl. `dates_confirmed`; hub « Dates à venir » | 2, 8, 9 |
| `Player.global_level` and the four private fields; `PlayerSport` | 2 |
| Shared rating function with the 2.5 rule, equal across paths | 1, 4, 5 |
| CSV import stores `global_level`, frequency, wishes, tick, sports row | 5 |
| Transfer excludes personal fields, exports skills | 6 |
| PRIVATE_KEYS walk, `deactivate()` clearing | 8 (the walk); **`deactivate()` clearing is slice 2** with the rest of the account code, since nothing writes these fields in-app yet |
| `PlayerAdmin` columns, filters, sports inline | 7 |
| `CLAUDE.md` | 10 |
| Registration state in the admin, `invited`, `LateRegistration`, API, front `/register` | slices 2–3 (stated in the header) |

Types and names used across tasks: `rate`, `resolve_extras`, `parse_frequency`, `parse_confirmation`, `clean_text`, `IMPORTED_SPORT`, `FREQUENCY/SPORTS/WISHES/CONFIRMED` (Task 1, 5), `skills_locked`, `copy_skills`, `recompute_ratings`, `RecomputeReport(updated, unchanged, no_global_level, incomplete, has_questionnaire)`, `QuestionnaireError` (Task 4, used by Task 7), `LockedSkillFormSet` (Task 7), `PRIVATE_FIELDS` (Task 6), related names `registrationskill_set`, `playersport_set`.
