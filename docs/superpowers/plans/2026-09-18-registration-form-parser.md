# Year-Agnostic Registration Form Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the 2026 Google Forms registration CSV into `User`/`Player`/`PlayerRating` rows without per-year header edits, storing real emails and tolerating first-name-only and multi-token names.

**Architecture:** Parsing moves out of the `Edition` model into a new pure-function module `olympic_warriors/registration.py` (column resolution by stable header fragments, rating maths, name splitting). `Edition.create_players_from_registration_form` keeps its signature and becomes the only place that writes to the database, inside one transaction, with idempotent rating rows.

**Tech Stack:** Django 4.2, pandas, Django test runner (`manage.py test`) run inside the compose `server` container against Postgres.

Spec: `docs/superpowers/specs/2026-09-18-registration-form-parser-design.md`

---

## Running tests

All commands run from the repo root with the compose stack up (`docker compose up -d`). The `server/` directory is bind-mounted into the container, so edits on the host are visible immediately.

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
docker compose exec server python manage.py test olympic_warriors.tests.test_edition_import -v 2
docker compose exec server python manage.py test olympic_warriors -v 2   # everything
```

The existing `test_players.py` may already fail (it calls a protected endpoint without a token). That is a separate task in progress; ignore it here but do not make it worse.

## File structure

- Create `server/olympic_warriors/registration.py` — constants (`RATINGS`, header fragments) and three pure functions: `resolve_columns`, `compute_ratings`, `parse_name`. No Django imports.
- Modify `server/olympic_warriors/models/Edition.py` — delete `header_mapping`, `ratings`, `process_weighted_rating`, `process_global_rating`; rewrite `create_players_from_registration_form` to call the module and do the writes.
- Create `server/olympic_warriors/tests/fixtures/registration_2026_sample.csv` — exact 2026 headers, four fabricated rows.
- Create `server/olympic_warriors/tests/test_registration.py` — `SimpleTestCase` tests for the pure functions.
- Create `server/olympic_warriors/tests/test_edition_import.py` — `TestCase` end-to-end import test.
- Modify `CLAUDE.md` — registration import paragraph.

---

### Task 1: Column resolution

**Files:**
- Create: `server/olympic_warriors/registration.py`
- Create: `server/olympic_warriors/tests/test_registration.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_registration.py`:

```python
"""Tests for the pure registration-form parsing functions (no database)."""
import pandas as pd
from django.test import SimpleTestCase

from olympic_warriors.registration import (
    EMAIL,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    resolve_columns,
)

SKILL_SENTENCE = (
    "Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu "
    "le niveau que tu auras en août selon les critères suivants ? [{}]"
)
GLOBAL_2026 = (
    "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic "
    "Warriors de 2026 : Flag Rugby, Cache-cache, CrossFit, Relais, Maître des Fleurs, Fléchettes."
)
GLOBAL_2025 = (
    "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic "
    "Warriors de 2025 : Pétanque, Basket, Sprint/Relais, Parcours du Combattant, "
    "Kermesse (chamboule-tout, etc) et Géographie ?"
)
CRITERIA = [spec["criterion"] for spec in RATINGS.values()]


def make_df(global_header=GLOBAL_2026, with_email=True, rows=None, drop_criterion=None):
    """Build a DataFrame shaped like a Google Forms export for the given year."""
    headers = ["Horodateur"]
    if with_email:
        headers.append("Adresse e-mail")
    headers += ["Prénom et Nom", "A quelle fréquence pratiques-tu du sport ? "]
    headers += [SKILL_SENTENCE.format(c) for c in CRITERIA if c != drop_criterion]
    headers += [global_header, "Je confirme que je serai là ! 💪"]
    return pd.DataFrame(rows or [], columns=headers)


class ResolveColumnsTests(SimpleTestCase):
    def test_resolves_all_2026_columns(self):
        columns = resolve_columns(make_df())

        self.assertEqual(columns[NAME], "Prénom et Nom")
        self.assertEqual(columns[EMAIL], "Adresse e-mail")
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2026)
        for name, spec in RATINGS.items():
            self.assertEqual(columns[name], SKILL_SENTENCE.format(spec["criterion"]))
        self.assertEqual(len(columns), 13)

    def test_resolves_2025_columns_without_email(self):
        columns = resolve_columns(make_df(global_header=GLOBAL_2025, with_email=False))

        self.assertNotIn(EMAIL, columns)
        self.assertEqual(columns[GLOBAL_LEVEL], GLOBAL_2025)
        self.assertEqual(len(columns), 12)

    def test_missing_skill_column_raises_with_criterion(self):
        df = make_df(drop_criterion="Cardio")

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("Cardio", str(ctx.exception))

    def test_missing_global_level_raises(self):
        df = make_df(global_header="Une question sans rapport")

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("niveau global", str(ctx.exception))

    def test_duplicate_skill_column_raises(self):
        df = make_df()
        df["Encore une question ? [Cardio]"] = []

        with self.assertRaises(ValueError) as ctx:
            resolve_columns(df)
        self.assertIn("Ambiguous", str(ctx.exception))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `ImportError` / `ModuleNotFoundError: No module named 'olympic_warriors.registration'`.

- [ ] **Step 3: Write the module with constants and `resolve_columns`**

Create `server/olympic_warriors/registration.py`:

```python
"""
Parse a Google Forms registration export into player ratings.

The form wording changes every year, so columns are matched by stable
fragments (the bracketed criterion of each skill question, the prefix of the
global-level question) rather than by full header text.
"""

NAME = "Name"
EMAIL = "Email"
GLOBAL_LEVEL = "Global Level"

NAME_HEADER = "Prénom et Nom"
EMAIL_HEADER = "Adresse e-mail"
GLOBAL_LEVEL_PREFIX = "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global"

# Skill name -> PlayerRating identifier, weighting coefficient, and the French
# criterion that appears between brackets in the form header.
RATINGS = {
    "Cohesion and Team Spirit": {"id": "TEAM", "coef": 2, "criterion": "Cohésion et esprit d'équipe"},
    "Mobility": {"id": "MOB", "coef": 3, "criterion": "Souplesse et coordination"},
    "Accuracy and Aiming": {"id": "ACC", "coef": 2, "criterion": "Précision et lancer"},
    "Running and Speed": {"id": "SPD", "coef": 4, "criterion": "Course et vitesse"},
    "Endurance": {"id": "STMN", "coef": 4, "criterion": "Endurance longue durée"},
    "Cardio": {"id": "CARD", "coef": 4, "criterion": "Cardio"},
    "Cultural Knowledge": {"id": "CULT", "coef": 1, "criterion": "Culture générale"},
    "Strength": {"id": "STR", "coef": 3, "criterion": "Force (soulever, pousser, etc)"},
    "Explosiveness": {"id": "EXPL", "coef": 4, "criterion": "Explosivité (effort puissant en un temps court)"},
    "Strategy and Game Vision": {"id": "STRT", "coef": 2, "criterion": "Stratégie et vision de jeu"},
}


def _find_column(headers, predicate, label):
    """Return the single header satisfying predicate, None if absent, raise if several."""
    matches = [header for header in headers if predicate(header)]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous registration form column for {label!r}: {matches}")
    return matches[0] if matches else None


def resolve_columns(df):
    """
    Map internal column names to the DataFrame's actual headers.

    :param df: DataFrame read from the registration CSV.
    :return: dict {internal name: header}. Contains NAME, GLOBAL_LEVEL, every
             key of RATINGS, and EMAIL only when the form has an email column.
    :raises ValueError: if a required column is missing or matched twice.
    """
    headers = [str(header) for header in df.columns]
    columns = {}
    missing = []

    name_header = _find_column(headers, lambda h: h.strip() == NAME_HEADER, NAME_HEADER)
    if name_header is None:
        missing.append(NAME_HEADER)
    else:
        columns[NAME] = name_header

    email_header = _find_column(headers, lambda h: h.strip() == EMAIL_HEADER, EMAIL_HEADER)
    if email_header is not None:
        columns[EMAIL] = email_header

    global_header = _find_column(
        headers, lambda h: h.startswith(GLOBAL_LEVEL_PREFIX), GLOBAL_LEVEL_PREFIX
    )
    if global_header is None:
        missing.append(f"{GLOBAL_LEVEL_PREFIX}...")
    else:
        columns[GLOBAL_LEVEL] = global_header

    for name, spec in RATINGS.items():
        needle = f"[{spec['criterion']}]"
        header = _find_column(headers, lambda h, needle=needle: needle in h, needle)
        if header is None:
            missing.append(needle)
        else:
            columns[name] = header

    if missing:
        raise ValueError(f"Missing registration form columns: {missing}")
    return columns
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `Ran 5 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/registration.py server/olympic_warriors/tests/test_registration.py
git commit -m "[ADD] registration column resolution by header fragments

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Name parsing

**Files:**
- Modify: `server/olympic_warriors/registration.py`
- Modify: `server/olympic_warriors/tests/test_registration.py`

- [ ] **Step 1: Write the failing tests**

Add `parse_name` to the import block at the top of `server/olympic_warriors/tests/test_registration.py`:

```python
from olympic_warriors.registration import (
    EMAIL,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    parse_name,
    resolve_columns,
)
```

Append to the file:

```python
class ParseNameTests(SimpleTestCase):
    def test_two_tokens(self):
        self.assertEqual(parse_name("Alice Martin"), ("Alice", "Martin", "alicemartin"))

    def test_trailing_space_and_accent_keep_legacy_username(self):
        self.assertEqual(parse_name("Camille Béziau "), ("Camille", "Béziau", "camillebéziau"))

    def test_first_name_only(self):
        self.assertEqual(parse_name("Adrien "), ("Adrien", "", "adrien"))

    def test_three_tokens_join_last_name(self):
        self.assertEqual(
            parse_name("Cédric DE LA MOTTE "), ("Cédric", "DE LA MOTTE", "cédricdelamotte")
        )

    def test_empty_or_nan_raises(self):
        with self.assertRaises(ValueError):
            parse_name("   ")
        with self.assertRaises(ValueError):
            parse_name(float("nan"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `ImportError: cannot import name 'parse_name'`.

- [ ] **Step 3: Implement `parse_name`**

Append to `server/olympic_warriors/registration.py`:

```python
def parse_name(raw):
    """
    Split a "Prénom et Nom" cell into first name, last name, and username.

    Whitespace is stripped and collapsed. The first token is the first name;
    the remaining tokens, joined by a space, form the last name (may be empty).
    The username is every token concatenated and lowercased, which matches the
    scheme used by earlier editions so returning players keep their account.

    :raises ValueError: if the cell is blank or not a string (pandas NaN).
    """
    tokens = raw.split() if isinstance(raw, str) else []
    if not tokens:
        raise ValueError("Empty participant name")
    first_name = tokens[0]
    last_name = " ".join(tokens[1:])
    username = "".join(tokens).lower()
    return first_name, last_name, username
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `Ran 10 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/registration.py server/olympic_warriors/tests/test_registration.py
git commit -m "[ADD] tolerant participant name parsing

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Rating computation

**Files:**
- Modify: `server/olympic_warriors/registration.py`
- Modify: `server/olympic_warriors/tests/test_registration.py`

The formulas are the existing ones from `Edition.process_weighted_rating` and `Edition.process_global_rating`, reproduced exactly. Coefficients sum to 29. With all ten skills equal to `s` the weighted rating is `s`.

Hand-computed expectations:
- skills all 6, global 8: weighted 6 (no boost, 6 ≥ 4), global rating (6 + 8×4)/5 = 7.6
- skills all 2, global 6: weighted 2 → boosted ×2.5 = 5.0 (2 < 4 and 6 > 4), global rating (5 + 24)/5 = 5.8
- skills all 2, global 3: weighted 2, no boost (3 ≤ 4), global rating (2 + 12)/5 = 2.8

- [ ] **Step 1: Write the failing tests**

Add `compute_ratings` to the import block in `server/olympic_warriors/tests/test_registration.py`:

```python
from olympic_warriors.registration import (
    EMAIL,
    GLOBAL_LEVEL,
    NAME,
    RATINGS,
    compute_ratings,
    parse_name,
    resolve_columns,
)
```

Append to the file:

```python
def make_row(name, skill, global_level, email="x@example.com"):
    """One form response where every skill has the same value."""
    return ["1/1/2026 10:00:00", email, name, "Souvent"] + [skill] * len(CRITERIA) + [global_level, "Oui"]


class ComputeRatingsTests(SimpleTestCase):
    def compute(self, rows):
        df = make_df(rows=rows)
        return compute_ratings(df, resolve_columns(df))

    def test_global_rating_blends_weighted_and_global_estimate(self):
        out = self.compute([make_row("Alice Martin", 6, 8)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 6)
        self.assertEqual(out.loc[0, "Global_Rating"], 7.6)

    def test_low_weighted_with_high_global_is_boosted(self):
        out = self.compute([make_row("Bob", 2, 6)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 5.0)
        self.assertEqual(out.loc[0, "Global_Rating"], 5.8)

    def test_low_weighted_with_low_global_is_not_boosted(self):
        out = self.compute([make_row("Bob", 2, 3)])

        self.assertEqual(out.loc[0, "Weighted_Rating"], 2)
        self.assertEqual(out.loc[0, "Global_Rating"], 2.8)

    def test_columns_are_renamed_to_internal_names(self):
        out = self.compute([make_row("Alice Martin", 6, 8)])

        self.assertEqual(out.loc[0, NAME], "Alice Martin")
        self.assertEqual(out.loc[0, EMAIL], "x@example.com")
        self.assertEqual(out.loc[0, GLOBAL_LEVEL], 8)
        self.assertEqual(out.loc[0, "Cardio"], 6)

    def test_non_numeric_rating_raises_with_name(self):
        row = make_row("Alice Martin", 6, 8)
        row[4] = "beaucoup"

        with self.assertRaises(ValueError) as ctx:
            self.compute([row])
        self.assertIn("Alice Martin", str(ctx.exception))

    def test_out_of_range_rating_raises_with_name(self):
        with self.assertRaises(ValueError) as ctx:
            self.compute([make_row("Alice Martin", 11, 8)])
        self.assertIn("Alice Martin", str(ctx.exception))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `ImportError: cannot import name 'compute_ratings'`.

- [ ] **Step 3: Implement `compute_ratings`**

Add `import pandas as pd` as the first import line of `server/olympic_warriors/registration.py` (after the module docstring), then append:

```python
def compute_ratings(df, columns):
    """
    Rename resolved columns to internal names and add Weighted_Rating and
    Global_Rating columns using the historical formulas.

    :param df: DataFrame read from the registration CSV.
    :param columns: mapping returned by resolve_columns.
    :return: a new DataFrame with internal column names and the two ratings.
    :raises ValueError: if any rating is blank, non-numeric, or outside 1-10.
    """
    df = df.rename(columns={header: internal for internal, header in columns.items()})

    for column in list(RATINGS) + [GLOBAL_LEVEL]:
        values = pd.to_numeric(df[column], errors="coerce")
        invalid = df[values.isna() | (values < 1) | (values > 10)]
        if not invalid.empty:
            raise ValueError(
                f"Invalid rating for {column!r} on participant {invalid.iloc[0][NAME]!r}: "
                f"{invalid.iloc[0][column]!r}"
            )
        df[column] = values

    total_coef = sum(spec["coef"] for spec in RATINGS.values())
    weighted = sum(df[name] * spec["coef"] for name, spec in RATINGS.items()) / total_coef
    weighted = weighted.clip(lower=1, upper=10)

    # A weak self-assessment on the skills but a confident global estimate is
    # treated as under-reporting: multiply by 2.5 (historical rule).
    boost = (weighted < 4) & (df[GLOBAL_LEVEL] > 4)
    weighted = weighted.where(~boost, weighted * 2.5)
    df["Weighted_Rating"] = weighted

    df["Global_Rating"] = ((weighted + df[GLOBAL_LEVEL] * 4) / 5).clip(lower=1, upper=10).round(2)
    return df
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration -v 2
```
Expected: `Ran 16 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/registration.py server/olympic_warriors/tests/test_registration.py
git commit -m "[ADD] rating computation in registration module

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Edition import uses the module

**Files:**
- Create: `server/olympic_warriors/tests/fixtures/registration_2026_sample.csv`
- Create: `server/olympic_warriors/tests/test_edition_import.py`
- Modify: `server/olympic_warriors/models/Edition.py`

- [ ] **Step 1: Create the fixture**

Create `server/olympic_warriors/tests/fixtures/registration_2026_sample.csv` with exactly this content (the header row is the real 2026 export header; two header cells contain a line break inside quotes, which is valid CSV):

```csv
Horodateur,Adresse e-mail,Prénom et Nom,A quelle fréquence pratiques-tu du sport ? ,"Quels sont les sports que tu as pratiqué (dans toute ta vie et à tout niveau) ? En précisant sur chaque ligne le sport, le nombre d'années, le niveau et ta pratique actuelle (et toute information utile, comme le poste ou la spécialité). 
Exemple : ""Foot - 6 années - Amateur - Ne pratique plus - Défenseur gauche""","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Endurance longue durée]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Cardio]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Explosivité (effort puissant en un temps court)]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Course et vitesse]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Force (soulever, pousser, etc)]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Souplesse et coordination]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Précision et lancer]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Stratégie et vision de jeu]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Cohésion et esprit d'équipe]","Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimes-tu le niveau que tu auras en août selon les critères suivants ? [Culture générale]","Sur une échelle de 1 à 10, comment estimes-tu ton niveau global pour les Olympic Warriors de 2026 : Flag Rugby, Cache-cache, CrossFit, Relais, Maître des Fleurs, Fléchettes.","Idéalement, avec qui souhaiterais-tu être ou ne pas être en équipe ? 
(Ces demandes resteront confidentielles. On ne pourra pas toutes les satisfaire mais on essaiera).",Je confirme que je serai là ! 💪
2/15/2026 18:07:38,alice@example.com,Alice Martin,Au moins deux heures par semaine,Escalade - 10 ans - amateur,6,6,6,6,6,6,6,6,6,6,8,Avec Bob,Oui
2/17/2026 18:14:07,bob@example.com,Bob ,Environ une heure par semaine,Basket - 8 ans,2,2,2,2,2,2,2,2,2,2,6,,Oui
3/2/2026 6:53:55,,Chloé DE LA TOUR ,Moins d'une fois par mois,Danse - 5 ans,5,5,5,5,5,5,5,5,5,5,5,Peu importe,Oui
3/2/2026 11:42:48,thomas@example.com,Thomas Dupont,Au moins quatre heures par semaine,Rugby - 8 ans,9,9,9,9,9,9,9,9,9,9,9,,Oui
```

Verify it parses:
```bash
docker compose exec server python -c "import pandas as pd; df = pd.read_csv('olympic_warriors/tests/fixtures/registration_2026_sample.csv'); print(df.shape); print(list(df['Prénom et Nom']))"
```
Expected: `(4, 18)` and `['Alice Martin', 'Bob ', 'Chloé DE LA TOUR ', 'Thomas Dupont']`.

- [ ] **Step 2: Write the failing end-to-end tests**

Create `server/olympic_warriors/tests/test_edition_import.py`:

```python
"""End-to-end test: saving an Edition with a registration form creates players."""
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from olympic_warriors.models import Edition, Player, PlayerRating

FIXTURE = Path(__file__).parent / "fixtures" / "registration_2026_sample.csv"
MEDIA_TMP = tempfile.mkdtemp()


def upload():
    return SimpleUploadedFile("registration_2026_sample.csv", FIXTURE.read_bytes())


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EditionImportTests(TestCase):
    def setUp(self):
        # Returning player from a previous edition, with the generated fallback email.
        self.thomas = User.objects.create_user(
            username="thomasdupont",
            first_name="Thomas",
            last_name="Dupont",
            email="thomasdupont@olympicwarriors.com",
            password="irrelevant",
        )
        self.edition = Edition.objects.create(
            year=2026,
            host="Toulouse",
            start_date="2026-08-01",
            end_date="2026-08-02",
            registration_form=upload(),
        )

    def test_creates_users_players_and_ratings(self):
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)
        self.assertEqual(PlayerRating.objects.count(), 40)

    def test_returning_player_links_to_existing_user_and_gets_real_email(self):
        player = Player.objects.get(user=self.thomas, edition=self.edition)

        self.thomas.refresh_from_db()
        self.assertEqual(self.thomas.email, "thomas@example.com")
        self.assertEqual(player.rating, 9)

    def test_new_user_gets_form_email_and_fallback_when_blank(self):
        alice = User.objects.get(username="alicemartin")
        chloe = User.objects.get(username="chloédelatour")

        self.assertEqual(alice.email, "alice@example.com")
        self.assertEqual(chloe.email, "chloédelatour@olympicwarriors.com")
        self.assertEqual(chloe.first_name, "Chloé")
        self.assertEqual(chloe.last_name, "DE LA TOUR")

    def test_first_name_only_is_imported_with_empty_last_name(self):
        bob = User.objects.get(username="bob")

        self.assertEqual(bob.first_name, "Bob")
        self.assertEqual(bob.last_name, "")
        self.assertEqual(Player.objects.get(user=bob).rating, 5)

    def test_player_rating_and_skill_ratings_match_formula(self):
        alice = Player.objects.get(user__username="alicemartin")

        self.assertEqual(alice.rating, 7)  # 7.6 truncated by IntegerField
        cardio = PlayerRating.objects.get(player=alice, identifier="CARD")
        self.assertEqual(cardio.name, "Cardio")
        self.assertEqual(cardio.rating, 6)

    def test_reimport_does_not_duplicate_rows(self):
        self.edition.registration_form = upload()
        self.edition.save()

        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)
        self.assertEqual(PlayerRating.objects.count(), 40)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_edition_import -v 2
```
Expected: every test errors in `setUp` with `KeyError: 'Global Level Estimation for Olympic Warriors 2025'` (the old parser cannot read the 2026 headers).

- [ ] **Step 4: Rewrite `Edition.py`**

Replace the entire content of `server/olympic_warriors/models/Edition.py` with:

```python
import pandas as pd

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.crypto import get_random_string

from ..registration import EMAIL, NAME, RATINGS, compute_ratings, parse_name, resolve_columns
from .Player import Player, PlayerRating

FALLBACK_EMAIL_DOMAIN = "olympicwarriors.com"


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place.
    """

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.year} - {self.host}"

    def create_players_from_registration_form(self, registration_form):
        """
        Create or update users, players and skill ratings from the registration form.

        The whole import runs in one transaction: a bad row leaves nothing written.

        :param registration_form: file-like CSV export of the Google Form.
        :raises ValueError: on missing columns, invalid ratings, or a blank name.
        """
        # After Django stores an upload the pointer sits at end-of-file; rewind
        # so pandas sees the header. Plain file objects passed by callers are
        # rewound too, which is harmless.
        if hasattr(registration_form, "seek"):
            registration_form.seek(0)
        df = pd.read_csv(registration_form)
        df = compute_ratings(df, resolve_columns(df))

        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    first_name, last_name, username = parse_name(row[NAME])
                except ValueError as exc:
                    raise ValueError(f"Registration form line {index + 2}: {exc}") from exc

                email = row.get(EMAIL)
                email = email.strip() if isinstance(email, str) else ""

                user = User.objects.filter(username=username).first()
                if user is None:
                    user = User.objects.create_user(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        password=get_random_string(length=8),
                        email=email or f"{username}@{FALLBACK_EMAIL_DOMAIN}",
                    )
                elif email and user.email.endswith(f"@{FALLBACK_EMAIL_DOMAIN}"):
                    user.email = email
                    user.save(update_fields=["email"])

                player, _ = Player.objects.get_or_create(
                    user=user, edition=self, defaults={"rating": row["Global_Rating"]}
                )

                for name, spec in RATINGS.items():
                    PlayerRating.objects.update_or_create(
                        player=player,
                        identifier=spec["id"],
                        defaults={"name": name, "rating": row[name]},
                    )

    def save(self, *args, **kwargs):
        """
        Override the save method to create players from the registration form of the edition.
        """
        # Check if the object is already in the database
        if self.pk is not None:
            # Get the original object from the database
            original_obj = Edition.objects.get(pk=self.pk)
            # Compare registration from to see if it has been updated
            new_registration_form = getattr(self, "registration_form")
            if new_registration_form != getattr(original_obj, "registration_form"):
                super().save(*args, **kwargs)
                self.create_players_from_registration_form(new_registration_form)
        elif self.registration_form:
            super().save(*args, **kwargs)
            self.create_players_from_registration_form(self.registration_form)

        # Call the original save method to save the object
        super().save(*args, **kwargs)
```

`save()` is unchanged from the current file. The `seek(0)` is required: Django's storage reads the uploaded file to disk and leaves its pointer at the end, so without it `pd.read_csv` raises `EmptyDataError` on a fresh upload. `header_mapping`, `ratings`, `process_weighted_rating` and `process_global_rating` are gone; nothing else in the codebase references them (verify with the grep in the next step).

- [ ] **Step 5: Confirm nothing else used the removed attributes**

Run:
```bash
grep -rn "header_mapping\|process_weighted_rating\|process_global_rating\|Edition.ratings\|\.ratings\[" server/olympic_warriors --include=*.py | grep -v "/migrations/"
```
Expected: no output.

- [ ] **Step 6: Run the end-to-end tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_edition_import -v 2
```
Expected: `Ran 6 tests ... OK`.

If `test_reimport_does_not_duplicate_rows` fails on the `User` count, check that `save()` in the second call took the `self.pk is not None` branch: the new `SimpleUploadedFile` gets a different stored filename, so `!=` is true and the import re-runs.

- [ ] **Step 7: Run the pure-function tests too, to confirm nothing regressed**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_registration olympic_warriors.tests.test_edition_import -v 2
```
Expected: `Ran 22 tests ... OK`.

- [ ] **Step 8: Commit**

```bash
git add server/olympic_warriors/models/Edition.py server/olympic_warriors/tests/test_edition_import.py server/olympic_warriors/tests/fixtures/registration_2026_sample.csv
git commit -m "[FIX] year-agnostic registration import with real emails and tolerant names

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Dry-run against the real 2026 export, update docs

**Files:**
- Modify: `CLAUDE.md`

The real export is already on disk inside the container at `/server/mediafiles/registration_forms/2026_Inscription_OW_reponses.xlsx_-_Reponses_au_formulaire_1.csv` (uploaded through the admin earlier; it is gitignored media). Do not commit it: it contains personal remarks and emails.

- [ ] **Step 1: Run a rolled-back import of all 21 rows**

Run:
```bash
docker compose exec server python manage.py shell -c "
from django.db import transaction
from django.contrib.auth.models import User
from olympic_warriors.models import Edition, Player, PlayerRating

class Rollback(Exception):
    pass

path = 'mediafiles/registration_forms/2026_Inscription_OW_reponses.xlsx_-_Reponses_au_formulaire_1.csv'
try:
    with transaction.atomic():
        edition = Edition.objects.create(year=2026, host='dry-run', start_date='2026-08-01', end_date='2026-08-02')
        with open(path, 'rb') as f:
            edition.create_players_from_registration_form(f)
        players = Player.objects.filter(edition=edition).select_related('user')
        print('players:', players.count(), 'ratings:', PlayerRating.objects.filter(player__in=players).count())
        for p in players.order_by('user__username'):
            print(f'{p.user.username:<22} {p.user.first_name!r:<12} {p.user.last_name!r:<14} rating={p.rating} email={p.user.email}')
        raise Rollback()
except Rollback:
    print('rolled back, nothing persisted')
"
```
Expected: `players: 21 ratings: 210`, one line per participant, `adrien` with last name `''`, `cédricdelamotte` with last name `'DE LA MOTTE'`, real emails on every line, then `rolled back, nothing persisted`.

If a `ValueError` is raised instead, its message names the missing column or the offending participant; fix the data or the resolver and re-run.

- [ ] **Step 2: Confirm nothing persisted**

Run:
```bash
docker compose exec server python manage.py shell -c "from olympic_warriors.models import Edition; print(Edition.objects.filter(host='dry-run').count())"
```
Expected: `0`.

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, replace the paragraph starting with `**Registration import:**` with:

```markdown
**Registration import:** saving an `Edition` with a new `registration_form` CSV runs `Edition.create_players_from_registration_form`, which delegates to `olympic_warriors/registration.py`. Columns are matched by stable fragments (the bracketed skill criterion such as `[Cardio]`, the prefix of the global-level question, `Prénom et Nom`, optional `Adresse e-mail`), so yearly wording changes need no code change; add a new skill by adding an entry to `RATINGS` there. The import runs in one transaction, links returning players by name-derived username, stores the form email when present, and uses update-or-create for skill ratings so re-uploads do not duplicate rows.
```

- [ ] **Step 4: Run the whole app test suite**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors -v 2
```
Expected: all tests in `test_registration` and `test_edition_import` pass. `test_players.test_get_players` may fail with a 401 assertion; that failure predates this work and is tracked separately.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOC] describe year-agnostic registration import

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- Module boundary and the three functions: Tasks 1-3.
- `RATINGS` with criterion, header constants: Task 1.
- Missing and ambiguous column errors: Task 1 tests.
- Numeric coercion and range validation naming the participant: Task 3.
- Formulas unchanged, clamp, boost, blend, round: Task 3, hand-computed cases.
- Name split, empty last name, legacy username, blank-name error with row number: Tasks 2 and 4.
- Transaction, email fallback and upgrade, `get_or_create` player, `update_or_create` ratings: Task 4.
- Fixture with exact headers and four fabricated participants, both test modules, 2025 header test: Tasks 1 and 4.
- Real-file run with 21 rows, no personal data committed: Task 5.
- CLAUDE.md paragraph: Task 5.
