# Edition transfer: export from local, import into prod

Date: 2026-09-19
Status: approved design, awaiting implementation plan

## Problem

Production holds the 2025 edition. The 2024 edition (history: teams,
schedule, games, blindtest guesses) and the ongoing 2026 edition (players,
ratings, teams, disciplines, generated schedule) exist only in Hugo's local
database. They must be moved to production once, after which production is
the source of truth for 2026.

A plain `dumpdata`/`loaddata` cannot be used: every table uses auto-increment
ids that differ between the two databases, `loaddata` upserts by id and would
silently overwrite production rows, and `auth.User` is shared across editions
so returning players already exist on production under different ids.

## Goals

- Move a whole edition, all of its dependent rows included, without any local
  id reaching production.
- Reuse existing production users (matched by username) and create the
  missing ones.
- Never trigger the model `save()` side effects on import (scheduling games,
  creating team results, re-parsing the registration CSV, score deltas).
- Refuse to touch an edition that already exists on production unless
  explicitly told to replace it.
- Be verifiable before committing: a dry run that reports counts and rolls
  back.

## Non-goals

- Two-way sync or merging two diverging copies of an edition.
- Moving users that have no player in the exported edition, or the `admin`
  superuser.
- Copying media files inside the JSON. File fields keep their relative media
  path; the files are copied with `scp` separately.
- Any schema change.

## Design

### 1. Two management commands

`server/olympic_warriors/management/commands/export_edition.py`

    python manage.py export_edition 2026 --out edition-2026.json

Writes one JSON document for the edition with that `year`. Errors if the year
is absent or matched twice.

`server/olympic_warriors/management/commands/import_edition.py`

    python manage.py import_edition edition-2026.json [--dry-run] [--replace]

Reads the document and recreates the edition inside one `transaction.atomic()`
block. `--dry-run` runs the full import, prints the per-table counts, then
raises an internal exception that rolls the transaction back. `--replace`
deletes the existing edition with the same year (cascading through its
dependents) inside the same transaction before importing; without it an
existing year aborts before any write.

The serialization logic lives in `server/olympic_warriors/transfer.py` (pure
functions over model instances and dicts, testable without the commands), and
the commands are thin wrappers.

### 2. Document format

    {
      "format": 1,
      "exported_at": "<ISO timestamp>",
      "edition": {"year": 2026, "host": "...", ...all concrete fields except id},
      "users": [{"username": "alicemartin", "first_name": ..., "last_name": ...,
                 "email": ..., "password": "<hash>", "is_active": true}],
      "tables": {
        "Team":            [{"_id": 12, "name": ..., ...}],
        "Player":          [{"_id": 40, "user": "alicemartin", "team": 12, "rating": 8, ...}],
        "PlayerRating":    [{"_id": ..., "player": 40, ...}],
        "Discipline":      [{"_id": 7, "subclass": "Rugby", "child": {...}, ...}],
        "TeamResult":      [{"_id": ..., "team": 12, "discipline": 7, ...}],
        "TeamSportRound":  [...],
        "Game":            [...],
        "GameEvent":       [{"_id": ..., "subclass": "RugbyEvent", "child": {...}, ...}],
        "BlindtestRound":  [...],
        "BlindtestGuess":  [...]
      }
    }

Rules:

- `_id` is the local primary key, used only so rows can reference each other
  inside the document. The importer maps every `_id` to a fresh production id
  and never writes `_id` to the database.
- Foreign keys to a table in the document are written as the target's `_id`.
  Foreign keys to `User` are written as the username. Foreign keys to
  `Edition` are omitted (there is exactly one edition per document).
- All other concrete fields are exported generically from `_meta.concrete_fields`
  (dates as ISO strings, files as their storage name, `None` kept). Inactive
  rows (`is_active=False`) are exported too.
- Multi-table inheritance: a `Discipline` row carries `subclass` (the child
  model name, e.g. `Rugby`, `Blindtest`) and `child` (the child model's own
  concrete fields, usually empty). Same for `GameEvent` with `RugbyEvent` /
  `DodgeballEvent`. The child model is resolved at import with
  `apps.get_model("olympic_warriors", subclass)`, so disciplines added later
  need no change here.
- `users` holds only users that own a `Player` in this edition. Superusers and
  staff are skipped and a warning names them.
- `Team.edition`, `Discipline.edition`, `Game.edition`, `Player.edition` are
  all set to the new edition on import.

### 3. Import order and id mapping

    Edition -> users (reuse or create) -> Team -> Player -> PlayerRating
    -> Discipline (+ child row) -> TeamResult -> TeamSportRound -> Game
    -> GameEvent (+ child row) -> BlindtestRound -> BlindtestGuess

Each table is inserted with `Model.save_base(raw=True)` per row, the same
call `loaddata` uses, so overridden `save()` methods never run. Child rows of
multi-table inheritance are inserted with `child(discipline_ptr_id=<new parent id>,
**child_fields).save_base(raw=True)`; with `raw=True` Django does not try to
re-save the parent. A dict per table maps `_id` to the new id, and every
foreign key is rewritten through it before insertion. A reference to an `_id`
missing from the document is an error.

User matching: `User.objects.filter(username=...)` first. An existing user is
reused as is (production keeps its email and password). A missing user is
created from the exported fields, password hash included, with
`save_base(raw=True)`; the `post_save` signal still creates the DRF token.

### 4. Safety and reporting

- Existing year without `--replace`: abort with a message before any write.
- `--replace`: `Edition.objects.filter(year=...).delete()` inside the
  transaction, relying on the existing `on_delete=CASCADE` chains. Users are
  never deleted.
- The import prints a table of `table -> rows inserted`, the number of users
  reused and created, and a list of file paths referenced by the document
  that do not exist under `MEDIA_ROOT` on the importing side.
- `--dry-run`: everything above, then rollback, with a final line saying so.
- Any exception rolls the whole edition back; the message names the table and
  `_id` being inserted.
- Document `format` other than 1 is rejected.

### 5. Tests

`server/olympic_warriors/tests/test_transfer.py` (`TestCase`, Postgres):

- Build a small edition in the test database: two users, two teams, two
  players with ratings, one `Rugby` discipline with its team results and one
  round of two games, one `Blindtest` with one round and two guesses.
- Export it, delete it, pre-create one of the two users under a different id,
  import. Assert: per-table counts equal the original, the reused user kept
  its id and email, the other user was created, `Game.team1/team2/referees`
  and `BlindtestGuess.team` point at the new teams, `Discipline` child rows
  exist with the right subclass, and no `Discipline.save()` side effect ran
  (game count did not double).
- Import the same document again: aborts, counts unchanged. With `--replace`:
  counts unchanged and the edition id changed. With `--dry-run`: no edition.
- A document referencing an unknown `_id` rolls back cleanly.
- A document with `format: 2` is rejected.

Before finishing, export the real local 2024 and 2026 editions and import
them with `--dry-run` into the local database (both years pre-exist locally,
so the dry run is combined with `--replace`), confirming counts match.

## Runbook (after implementation)

Locally:

    docker compose exec server python manage.py export_edition 2024 --out /server/edition-2024.json
    docker compose exec server python manage.py export_edition 2026 --out /server/edition-2026.json
    scp server/edition-20*.json hugo@192.168.1.100:/opt/OW/Olympic-Warriors/server/
    scp -r server/mediafiles/registration_forms server/mediafiles/rules hugo@192.168.1.100:/opt/OW/Olympic-Warriors/server/mediafiles/

On the server, for each file:

    docker compose -f docker-compose.prod.yml exec server python manage.py import_edition edition-2024.json --dry-run
    docker compose -f docker-compose.prod.yml exec server python manage.py import_edition edition-2024.json

The JSON files are gitignored (`server/edition-*.json`) because they contain
names and emails.

## Files

- Add `server/olympic_warriors/transfer.py`
- Add `server/olympic_warriors/management/commands/export_edition.py`
- Add `server/olympic_warriors/management/commands/import_edition.py`
- Add `server/olympic_warriors/tests/test_transfer.py`
- Edit `.gitignore` (`server/edition-*.json`)
- Edit `CLAUDE.md` (commands section: the two commands, one line each)
