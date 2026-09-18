# Registration form parser: year-agnostic import (2026 form)

Date: 2026-09-18
Status: approved design, awaiting implementation plan

## Problem

`Edition.create_players_from_registration_form` maps the Google Forms CSV
columns with a dict of full French header strings. Each year the wording of
the global-level question changes (new sports list), and the parser hardcodes
that column name in three places. The 2026 export therefore raises a
`KeyError`, exactly as the 2025 export did before commit `b8c2429`.

The 2026 export also adds an email column, and its names are messier: ten of
21 names carry trailing spaces, one is a first name only ("Adrien "), which
raises `IndexError` on the first/last split, and one has three tokens
("Cédric LE GUEDART"), which stores "LE" as the last name.

The ten skill rating columns are unchanged from 2025 and contain clean 1-10
integers with no blanks.

## Goals

- Import the 2026 form with no per-year code change, and keep working when
  the surrounding wording changes again in 2027.
- Store real emails when the form provides them.
- Tolerate first-name-only and multi-token names.
- Keep rating formulas and coefficients exactly as they are.
- Keep returning players linked to their existing `User`.

## Non-goals

- Changing the username scheme or matching users by email.
- Reading team preferences, sport frequency, sports practiced, or the
  confirmation column. They stay unmapped and unused.
- Any change to the `Player` or `PlayerRating` schema.

## Design

### 1. Module boundary

New module `server/olympic_warriors/registration.py` holding pure functions
and the constants:

- `RATINGS`: the ten skills, each with `id`, `coef`, and a new `criterion`
  (the French text inside the brackets of the header, e.g. `"Cardio"`,
  `"Endurance longue durée"`, `"Force (soulever, pousser, etc)"`).
- `GLOBAL_LEVEL_PREFIX = "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global"`.
- `NAME_HEADER = "Prénom et Nom"`, `EMAIL_HEADER = "Adresse e-mail"`.
- `resolve_columns(df) -> dict[str, str]`: maps internal names
  (`"Name"`, `"Email"` if present, `"Global Level"`, and each skill name) to the
  actual DataFrame column. A skill column is any header containing
  `[<criterion>]`; the global-level column is any header starting with
  `GLOBAL_LEVEL_PREFIX`. Raises `ValueError` listing every missing required
  column. Ambiguous matches (two headers for one criterion) also raise.
- `compute_ratings(df, columns) -> DataFrame`: renames resolved columns to
  their internal names, coerces the eleven numeric columns with
  `pd.to_numeric(errors="raise")`, validates each is within 1-10 (raising
  with the participant's name otherwise), then applies the existing
  weighted-rating and global-rating formulas unchanged.
- `parse_name(raw) -> (first_name, last_name, username)`: strips and
  collapses whitespace; first token is the first name, the remaining tokens
  joined by a space are the last name (may be empty); username is the
  collapsed name with spaces removed and lowercased. Accents are kept, as
  today, so existing usernames still match.

`Edition.create_players_from_registration_form` keeps its signature. It reads
the CSV, calls the three functions, and does the database writes. The
`header_mapping` and `ratings` class attributes and the two `process_*`
methods on `Edition` are removed.

### 2. Rating formulas (unchanged)

- Weighted rating = coefficient-weighted mean of the ten skills, clamped to
  1-10.
- If weighted rating < 4 and global estimate > 4, multiply weighted rating by
  2.5.
- Global rating = (weighted + global estimate × 4) / 5, clamped to 1-10,
  rounded to two decimals. This becomes `Player.rating`.

### 3. Database writes

Wrapped in `transaction.atomic()` so a failure on any row leaves nothing
created.

For each row:

- `User`: get by username, else `create_user` with first name, last name,
  random 8-char password, and email. Email is the form value when present and
  non-blank, otherwise `<username>@olympicwarriors.com` as today. If an
  existing user's email ends with `@olympicwarriors.com` and the form gives a
  real one, the real one is saved on the user.
- `Player`: get by (user, edition), else create with `rating=Global_Rating`.
- `PlayerRating`: `update_or_create` keyed on (player, identifier), setting
  `name` and `rating`. Re-uploading a form updates the ten rows instead of
  appending ten more.

### 4. Error handling

- Missing or ambiguous columns: `ValueError` from `resolve_columns` naming
  them, raised before any write.
- Non-numeric or out-of-range rating: `ValueError` naming the participant.
- Empty name cell: `ValueError` naming the row index.
- These surface as a server error in the admin on `Edition` save, which is
  the current behaviour for parser failures. Improving the admin UX is out of
  scope.

### 5. Tests

Fixture `server/olympic_warriors/tests/fixtures/registration_2026_sample.csv`:
the exact 2026 headers with four fabricated participants covering a two-token
name, a first-name-only name, a three-token name, and a name that already
exists as a user from a prior edition. No real participant data is committed.

`tests/test_registration.py` (no database):

- `resolve_columns` finds all thirteen columns on the 2026 headers (name, email, global level, ten skills).
- `resolve_columns` finds all twelve required columns on the 2025 headers
  (no email), proving the rules are not tied to one year.
- `resolve_columns` raises and names the criterion when one skill header is
  removed.
- `parse_name` on `"Adrien "`, `"Cédric LE GUEDART "`, `"Pauline Fauré "`.
- `compute_ratings` reproduces the current formula on a hand-computed row.

`tests/test_edition_import.py` (`TestCase`, needs Postgres via compose):

- Saving an `Edition` with the fixture creates four users, four players, and
  forty `PlayerRating` rows; the returning player is linked to the existing
  user; the real email is stored; the first-name-only player has an empty
  last name.
- Saving again with the same file leaves the counts unchanged.

Before finishing, the import is run once locally against the real 2026 CSV
and must import all 21 rows.

## Files

- Add `server/olympic_warriors/registration.py`
- Edit `server/olympic_warriors/models/Edition.py`
- Add `server/olympic_warriors/tests/fixtures/registration_2026_sample.csv`
- Add `server/olympic_warriors/tests/test_registration.py`
- Add `server/olympic_warriors/tests/test_edition_import.py`
- Edit `CLAUDE.md` (registration import paragraph)
