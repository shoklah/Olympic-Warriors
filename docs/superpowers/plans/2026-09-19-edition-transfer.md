# Edition Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move a whole edition (teams, players, ratings, disciplines, results, schedule, games, events, blindtest data) from one database to another with fresh ids, reusing existing users by username, without triggering any model `save()` side effect.

**Architecture:** A pure module `olympic_warriors/transfer.py` exposes `export_edition(year) -> dict` and `import_edition(document, replace=False) -> report`. Rows are serialised generically from `_meta.concrete_fields`, cross-references use the local id (`_id`) only inside the document, users are referenced by username, multi-table-inheritance children carry `subclass`/`child`. Import inserts with `save_base(raw=True)` (what `loaddata` uses) so overridden `save()` methods never run. Two thin management commands wrap the module.

**Tech Stack:** Django 4.2, PostgreSQL, Django test runner inside the compose `server` container.

Spec: `docs/superpowers/specs/2026-09-19-edition-transfer-design.md`. Branch: `claude/edition-transfer` (off `dev`).

---

## Running tests

Compose stack up (`docker compose up -d`); `./server` is bind-mounted, so host edits are live in the container. From the repo root:

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_transfer -v 2
docker compose exec server python manage.py test olympic_warriors -v 2   # everything (63 tests pass on dev today)
```

## File structure

- Create `server/olympic_warriors/transfer.py` — serialisation and import logic, no I/O, no argparse.
- Create `server/olympic_warriors/management/commands/export_edition.py` — `year --out path`.
- Create `server/olympic_warriors/management/commands/import_edition.py` — `path [--dry-run] [--replace]`.
- Create `server/olympic_warriors/tests/test_transfer.py` — `TestCase` round-trip tests.
- Edit `.gitignore` — ignore `server/edition-*.json`.
- Edit `CLAUDE.md` — two command lines.

Facts the code relies on (verified on the current models):
- Every edition-scoped table and how to select its rows: `Team.edition`, `Player.edition`, `PlayerRating.player__edition`, `Discipline.edition`, `TeamResult.discipline__edition`, `TeamSportRound.discipline__edition`, `Game.edition`, `GameEvent.game__edition`, `BlindtestRound.blindtest__edition`, `BlindtestGuess.blindtest_round__blindtest__edition`.
- MTI children: every discipline model (`Rugby`, `Blindtest`, `Darts`, ...) extends `Discipline` through `discipline_ptr`; `RugbyEvent` and `DodgeballEvent` extend `GameEvent` through `gameevent_ptr`. `BlindtestRound.blindtest` points at `Blindtest`, whose pk equals its `Discipline` pk.
- `Discipline.save()` creates `TeamResult`s and schedules games on first save; `Blindtest.save()` creates 10 rounds and one guess per team; `Game.save()` adds points to `TeamResult`s; `Edition.save()` imports the CSV. None of these may run during import.
- `RugbyEvent.RugbyEventTypes.START == "STA"`.
- Existing commands use `BaseCommand` with a docstring and `help`; `management/` has no `__init__.py` (namespace package) and works.

---

### Task 1: Export

**Files:**
- Create: `server/olympic_warriors/transfer.py`
- Create: `server/olympic_warriors/tests/test_transfer.py`

- [ ] **Step 1: Write the failing tests**

Create `server/olympic_warriors/tests/test_transfer.py`:

```python
"""Round-trip tests for exporting an edition and importing it with fresh ids."""
import copy

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import (
    Blindtest,
    BlindtestGuess,
    Edition,
    Game,
    GameEvent,
    Player,
    PlayerRating,
    Rugby,
    RugbyEvent,
    Team,
    TeamResult,
    TeamSportRound,
)
from olympic_warriors.transfer import FORMAT, TABLES, export_edition


def build_edition(year=2024):
    """A small but complete edition: two teams, two players, rugby with a game, a blindtest."""
    edition = Edition.objects.create(
        year=year, host="Test", start_date=f"{year}-08-01", end_date=f"{year}-08-02"
    )
    alice = User.objects.create_user(
        username="alice", first_name="Alice", last_name="A", email="alice@example.com", password="x"
    )
    bob = User.objects.create_user(
        username="bob", first_name="Bob", last_name="B", email="bob@example.com", password="x"
    )
    red = Team.objects.create(name="Red", edition=edition)
    blue = Team.objects.create(name="Blue", edition=edition)
    p_alice = Player.objects.create(user=alice, edition=edition, rating=7, team=red)
    p_bob = Player.objects.create(user=bob, edition=edition, rating=5, team=blue)
    for player in (p_alice, p_bob):
        PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=6)

    rugby = Rugby.objects.create(edition=edition)  # save() creates one TeamResult per team
    round1 = TeamSportRound.objects.create(discipline=rugby, order=1)
    game = Game.objects.create(  # save() gives Red 3 points
        discipline=rugby, round=round1, team1=red, team2=blue, referees=red,
        edition=edition, score1=5, score2=0,
    )
    # Raw saves: RugbyEvent.save() validates and rescores, which is not under test here.
    event = GameEvent(game=game, player1=p_alice, time="2024-08-01T10:00:00+00:00")
    event.save_base(raw=True)
    RugbyEvent(
        gameevent_ptr_id=event.pk, game=game, player1=p_alice,
        time="2024-08-01T10:00:00+00:00", event_type=RugbyEvent.RugbyEventTypes.START,
    ).save_base(raw=True, force_insert=True)

    Blindtest.objects.create(edition=edition)  # save() creates 10 rounds x 2 guesses
    return edition


def snapshot(edition):
    """Row counts per exported table plus the values that save() side effects would change."""
    counts = {name: model.objects.filter(**{lookup: edition}).count() for name, model, lookup in TABLES}
    results = sorted(
        TeamResult.objects.filter(discipline__edition=edition)
        .values_list("team__name", "discipline__name", "points")
    )
    return counts, results


class ExportEditionTests(TestCase):
    def setUp(self):
        self.edition = build_edition()

    def test_fixture_shape(self):
        counts, results = snapshot(self.edition)
        self.assertEqual(
            counts,
            {
                "Team": 2, "Player": 2, "PlayerRating": 2, "Discipline": 2, "TeamResult": 4,
                "TeamSportRound": 1, "Game": 1, "GameEvent": 1, "BlindtestRound": 10,
                "BlindtestGuess": 20,
            },
        )
        self.assertIn(("Red", "Rugby", 3), results)

    def test_document_has_no_database_ids_and_references_users_by_username(self):
        doc = export_edition(2024)

        self.assertEqual(doc["format"], FORMAT)
        self.assertEqual(doc["edition"]["year"], 2024)
        self.assertNotIn("id", doc["edition"])
        self.assertEqual([u["username"] for u in doc["users"]], ["alice", "bob"])
        self.assertNotIn("password", doc["users"][0])
        self.assertNotIn("is_staff", doc["users"][0])
        players = doc["tables"]["Player"]
        self.assertEqual({p["user"] for p in players}, {"alice", "bob"})
        self.assertNotIn("edition", players[0])
        self.assertNotIn("id", players[0])
        self.assertIn("_id", players[0])

    def test_rows_reference_each_other_by_local_id(self):
        doc = export_edition(2024)

        team_ids = {t["_id"] for t in doc["tables"]["Team"]}
        game = doc["tables"]["Game"][0]
        self.assertIn(game["team1"], team_ids)
        self.assertIn(game["referees"], team_ids)
        self.assertIn(game["round"], {r["_id"] for r in doc["tables"]["TeamSportRound"]})
        self.assertEqual(game["score1"], 5)

    def test_subclass_rows_are_marked(self):
        doc = export_edition(2024)

        disciplines = doc["tables"]["Discipline"]
        self.assertEqual({d["subclass"] for d in disciplines}, {"Rugby", "Blindtest"})
        self.assertEqual(disciplines[0]["child"], {})
        event = doc["tables"]["GameEvent"][0]
        self.assertEqual(event["subclass"], "RugbyEvent")
        self.assertEqual(event["child"], {"event_type": "STA"})
        blindtest = next(d for d in disciplines if d["subclass"] == "Blindtest")
        self.assertEqual({r["blindtest"] for r in doc["tables"]["BlindtestRound"]}, {blindtest["_id"]})

    def test_dates_and_files_are_strings(self):
        doc = export_edition(2024)

        self.assertEqual(doc["edition"]["start_date"], "2024-08-01")
        self.assertEqual(doc["edition"]["registration_form"], "")
        self.assertEqual(doc["tables"]["GameEvent"][0]["time"], "2024-08-01T10:00:00+00:00")

    def test_missing_year_raises(self):
        with self.assertRaises(Edition.DoesNotExist):
            export_edition(1999)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_transfer -v 2
```
Expected: `ModuleNotFoundError: No module named 'olympic_warriors.transfer'`.

- [ ] **Step 3: Write the module with the export half**

Create `server/olympic_warriors/transfer.py`:

```python
"""
Move a whole edition between databases without carrying database ids.

export_edition() turns an Edition and every row hanging off it into a JSON
serialisable document; import_edition() recreates that document with fresh
ids. Users are referenced by username. Rows are written with
Model.save_base(raw=True), as loaddata does, so the model save() overrides
(scheduling, team results, CSV import, score deltas) never run.
"""
from datetime import datetime, timezone

from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.crypto import get_random_string

from .models import (
    BlindtestGuess,
    BlindtestRound,
    Discipline,
    Edition,
    Game,
    GameEvent,
    Player,
    PlayerRating,
    Team,
    TeamResult,
    TeamSportRound,
)

FORMAT = 1
USER_FIELDS = ("username", "first_name", "last_name", "email", "is_active")
FILE_FIELDS = ("registration_form", "rules")

# Exported tables in dependency order: (name, model, lookup selecting an edition's rows).
TABLES = (
    ("Team", Team, "edition"),
    ("Player", Player, "edition"),
    ("PlayerRating", PlayerRating, "player__edition"),
    ("Discipline", Discipline, "edition"),
    ("TeamResult", TeamResult, "discipline__edition"),
    ("TeamSportRound", TeamSportRound, "discipline__edition"),
    ("Game", Game, "edition"),
    ("GameEvent", GameEvent, "game__edition"),
    ("BlindtestRound", BlindtestRound, "blindtest__edition"),
    ("BlindtestGuess", BlindtestGuess, "blindtest_round__blindtest__edition"),
)


class TransferError(ValueError):
    """The document cannot be imported as is."""


class EditionExists(TransferError):
    """An edition with that year is already in the database."""


def _root_table(model):
    """Exported table a model's rows belong to; MTI children map to their root parent."""
    parents = model._meta.get_parent_list()
    return (parents[-1] if parents else model).__name__


def _child_models(parent):
    """App models that extend parent through multi-table inheritance."""
    return [
        model
        for model in apps.get_app_config("olympic_warriors").get_models()
        if parent in model._meta.get_parent_list()
    ]


def _serialize_value(field, obj):
    value = getattr(obj, field.attname)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return field.value_to_string(obj)  # dates, times, datetimes, files -> str


def _serialize_fields(obj, fields):
    """Concrete fields of obj as a dict: no pk, no edition link, FKs as _id or username."""
    row = {}
    for field in fields:
        if field.primary_key or field.name == "edition":
            continue
        if field.is_relation:
            target_id = getattr(obj, field.attname)
            if field.related_model is User:
                row[field.name] = getattr(obj, field.name).username if target_id else None
            else:
                row[field.name] = target_id
        else:
            row[field.name] = _serialize_value(field, obj)
    return row


def _serialize_row(obj):
    """One exported row: ``_id`` plus fields, plus subclass/child for MTI parents."""
    row = {"_id": obj.pk, **_serialize_fields(obj, obj._meta.concrete_fields)}
    for child_model in _child_models(type(obj)):
        child = child_model.objects.filter(pk=obj.pk).first()
        if child is not None:
            row["subclass"] = child_model.__name__
            row["child"] = _serialize_fields(child, child_model._meta.local_concrete_fields)
            break
    return row


def export_edition(year):
    """
    Build the transfer document for the edition with that year.

    :raises Edition.DoesNotExist, Edition.MultipleObjectsReturned: as Edition.objects.get.
    """
    edition = Edition.objects.get(year=year)
    users = User.objects.filter(player__edition=edition).distinct().order_by("username")
    document = {
        "format": FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "edition": _serialize_fields(edition, edition._meta.concrete_fields),
        "users": [{name: getattr(user, name) for name in USER_FIELDS} for user in users],
        "tables": {},
    }
    for name, model, lookup in TABLES:
        rows = model.objects.filter(**{lookup: edition}).order_by("pk")
        document["tables"][name] = [_serialize_row(obj) for obj in rows]
    return document
```

(`default_storage`, `transaction` and `get_random_string` are imported now for Task 2; pylint will flag them as unused until then, which is fine.)

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_transfer -v 2
```
Expected: `Ran 6 tests ... OK`.

If `test_fixture_shape` fails on `TeamResult` (expected 4) or `BlindtestGuess` (expected 20), the fixture builder is wrong, not the export: `Rugby.objects.create` must create 2 results and `Blindtest.objects.create` must add 2 more plus 10 rounds x 2 guesses. Fix the fixture, never the expectation, and report if the models behave differently.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/transfer.py server/olympic_warriors/tests/test_transfer.py
git commit -m "[ADD] export an edition to an id-free transfer document

Co-Authored-By: <your required trailer>"
```

---

### Task 2: Import

**Files:**
- Modify: `server/olympic_warriors/transfer.py`
- Modify: `server/olympic_warriors/tests/test_transfer.py`

- [ ] **Step 1: Write the failing tests**

Extend the import line at the top of `test_transfer.py`:

```python
from olympic_warriors.transfer import (
    FORMAT,
    TABLES,
    EditionExists,
    TransferError,
    export_edition,
    import_edition,
)
```

Append to the file:

```python
class ImportEditionTests(TestCase):
    def setUp(self):
        self.edition = build_edition()
        self.before = snapshot(self.edition)
        self.document = export_edition(2024)
        Edition.objects.filter(year=2024).delete()
        # bob must be recreated by the import; alice pre-exists with different data.
        User.objects.filter(username="bob").delete()
        User.objects.filter(username="alice").update(email="kept@example.com")
        self.alice_id = User.objects.get(username="alice").pk

    def test_round_trip_recreates_every_row_without_side_effects(self):
        report = import_edition(self.document)

        edition = Edition.objects.get(year=2024)
        self.assertEqual(snapshot(edition), self.before)
        self.assertEqual(report["counts"], self.before[0])
        self.assertEqual(report["year"], 2024)
        self.assertEqual(report["edition_id"], edition.pk)
        self.assertNotEqual(edition.pk, self.edition.pk)
        self.assertEqual(report["missing_files"], [])

    def test_existing_user_is_reused_untouched_and_missing_user_created(self):
        report = import_edition(self.document)

        alice = User.objects.get(username="alice")
        bob = User.objects.get(username="bob")
        self.assertEqual(alice.pk, self.alice_id)
        self.assertEqual(alice.email, "kept@example.com")
        self.assertEqual((bob.first_name, bob.last_name, bob.email), ("Bob", "B", "bob@example.com"))
        self.assertFalse(bob.is_staff)
        self.assertFalse(bob.is_superuser)
        self.assertTrue(bob.has_usable_password())
        self.assertFalse(bob.check_password("x"))
        self.assertEqual((report["users_reused"], report["users_created"]), (1, 1))
        self.assertEqual(Player.objects.get(user=alice).team.name, "Red")

    def test_foreign_keys_point_at_the_new_rows(self):
        import_edition(self.document)

        edition = Edition.objects.get(year=2024)
        game = Game.objects.get(edition=edition)
        self.assertEqual(
            (game.team1.edition_id, game.team2.edition_id, game.referees.edition_id),
            (edition.pk, edition.pk, edition.pk),
        )
        self.assertEqual(game.round.discipline.edition_id, edition.pk)
        self.assertEqual(Rugby.objects.get(edition=edition).pk, game.discipline_id)
        event = RugbyEvent.objects.get(game=game)
        self.assertEqual(event.event_type, "STA")
        self.assertEqual(event.player1.user.username, "alice")
        guess = BlindtestGuess.objects.filter(blindtest_round__blindtest__edition=edition).first()
        self.assertEqual(guess.team.edition_id, edition.pk)
        self.assertEqual(Blindtest.objects.get(edition=edition).name, "Blindtest")

    def test_existing_year_aborts_unless_replace(self):
        import_edition(self.document)
        first_id = Edition.objects.get(year=2024).pk

        with self.assertRaises(EditionExists):
            import_edition(self.document)
        self.assertEqual(Edition.objects.filter(year=2024).count(), 1)
        self.assertEqual(snapshot(Edition.objects.get(year=2024)), self.before)

        import_edition(self.document, replace=True)
        edition = Edition.objects.get(year=2024)
        self.assertNotEqual(edition.pk, first_id)
        self.assertEqual(snapshot(edition), self.before)
        self.assertEqual(User.objects.filter(username__in=["alice", "bob"]).count(), 2)

    def test_unknown_reference_rolls_back(self):
        broken = copy.deepcopy(self.document)
        broken["tables"]["Game"][0]["team1"] = 999999

        with self.assertRaises(TransferError) as ctx:
            import_edition(broken)
        self.assertIn("Game", str(ctx.exception))
        self.assertIn("999999", str(ctx.exception))
        self.assertFalse(Edition.objects.filter(year=2024).exists())
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_unknown_user_rolls_back(self):
        broken = copy.deepcopy(self.document)
        broken["tables"]["Player"][0]["user"] = "nobody"

        with self.assertRaises(TransferError) as ctx:
            import_edition(broken)
        self.assertIn("nobody", str(ctx.exception))
        self.assertFalse(Edition.objects.filter(year=2024).exists())

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(TransferError):
            import_edition({**self.document, "format": 2})
        self.assertFalse(Edition.objects.filter(year=2024).exists())

    def test_missing_media_files_are_reported(self):
        doc = copy.deepcopy(self.document)
        doc["edition"]["registration_form"] = "registration_forms/nope.csv"

        report = import_edition(doc)

        self.assertEqual(report["missing_files"], ["registration_forms/nope.csv"])
        self.assertEqual(Edition.objects.get(year=2024).registration_form.name, "registration_forms/nope.csv")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_transfer -v 2
```
Expected: `ImportError: cannot import name 'EditionExists'`.

- [ ] **Step 3: Implement the import half**

Append to `server/olympic_warriors/transfer.py`:

```python
def _deserialize_fields(model, fields, row, ids, users, edition):
    """Model kwargs from an exported row, rewriting references through ids and users."""
    kwargs = {}
    for field in fields:
        if field.primary_key:
            continue
        if field.name == "edition":
            kwargs["edition"] = edition
            continue
        if field.name not in row:
            continue  # field added after the export: the model default applies
        value = row[field.name]
        if not field.is_relation:
            kwargs[field.name] = field.to_python(value)
        elif value is None:
            kwargs[field.attname] = None
        elif field.related_model is User:
            if value not in users:
                raise TransferError(f"{model.__name__}.{field.name} references unknown user {value!r}")
            kwargs[field.attname] = users[value].pk
        else:
            table = _root_table(field.related_model)
            if value not in ids.get(table, {}):
                raise TransferError(
                    f"{model.__name__}.{field.name} references unknown {table} _id {value}"
                )
            kwargs[field.attname] = ids[table][value]
    return kwargs


def _insert(model, kwargs, force_insert=False):
    """Insert without running the model's save() override (same path as loaddata)."""
    obj = model(**kwargs)
    obj.save_base(raw=True, force_insert=force_insert)
    return obj


def _file_paths(document):
    paths = [document["edition"].get(name) for name in FILE_FIELDS]
    for row in document["tables"].get("Discipline", []):
        paths += [row.get(name) for name in FILE_FIELDS]
    return [path for path in paths if path]


def import_edition(document, replace=False):
    """
    Recreate an exported edition with fresh ids, in one transaction.

    Existing users are reused by username and left untouched; missing users are
    created with a fresh random password and no staff flags.

    :param document: dict produced by export_edition.
    :param replace: delete an existing edition with the same year first.
    :return: report dict with edition_id, year, users_reused, users_created,
             counts (per table) and missing_files (media paths absent here).
    :raises EditionExists: year already present and replace is False.
    :raises TransferError: unsupported format, dangling reference, or insert failure.
    """
    if document.get("format") != FORMAT:
        raise TransferError(f"Unsupported transfer document format {document.get('format')!r}")
    year = document["edition"]["year"]

    with transaction.atomic():
        existing = Edition.objects.filter(year=year)
        if existing.exists():
            if not replace:
                raise EditionExists(f"Edition {year} already exists; use --replace to overwrite it")
            existing.delete()

        edition = _insert(
            Edition,
            _deserialize_fields(Edition, Edition._meta.concrete_fields, document["edition"], {}, {}, None),
        )

        users, reused, created = {}, 0, 0
        for entry in document["users"]:
            user = User.objects.filter(username=entry["username"]).first()
            if user is None:
                user = User.objects.create_user(
                    password=get_random_string(length=8),
                    **{name: entry[name] for name in USER_FIELDS},
                )
                created += 1
            else:
                reused += 1
            users[entry["username"]] = user

        ids = {name: {} for name, _, _ in TABLES}
        counts = {}
        for name, model, _ in TABLES:
            rows = document["tables"].get(name, [])
            for row in rows:
                try:
                    kwargs = _deserialize_fields(model, model._meta.concrete_fields, row, ids, users, edition)
                    obj = _insert(model, kwargs)
                    ids[name][row["_id"]] = obj.pk
                    if row.get("subclass"):
                        child_model = apps.get_model("olympic_warriors", row["subclass"])
                        link = child_model._meta.get_ancestor_link(model)
                        child_kwargs = _deserialize_fields(
                            child_model, child_model._meta.local_concrete_fields,
                            row.get("child", {}), ids, users, edition,
                        )
                        child_kwargs[link.attname] = obj.pk
                        _insert(child_model, child_kwargs, force_insert=True)
                except TransferError:
                    raise
                except Exception as exc:
                    raise TransferError(f"{name} _id {row.get('_id')}: {exc}") from exc
            counts[name] = len(rows)

        return {
            "edition_id": edition.pk,
            "year": year,
            "users_reused": reused,
            "users_created": created,
            "counts": counts,
            "missing_files": [path for path in _file_paths(document) if not default_storage.exists(path)],
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_transfer -v 2
```
Expected: `Ran 14 tests ... OK`.

Known pitfalls if something fails:
- `IntegrityError` on a `Discipline` child: `force_insert=True` is required on the child insert because its pk is preset; the parent insert must have `force_insert=False` (pk is None).
- `TeamResult` points doubled: a `save()` override ran; every insert must go through `_insert`.
- `test_unknown_reference_rolls_back` fails on the `User` assertion: the `atomic()` block must wrap user creation too (it does, users are created inside it).
- `DateTimeField` warning about naive datetimes: the fixture uses an explicit `+00:00` offset; if the exported string lacks it, `value_to_string` was bypassed.

- [ ] **Step 5: Line length and commit**

```bash
awk 'length > 100 {print FILENAME": "FNR": "length}' server/olympic_warriors/transfer.py server/olympic_warriors/tests/test_transfer.py
```
Wrap anything reported, re-run the tests, then:

```bash
git add server/olympic_warriors/transfer.py server/olympic_warriors/tests/test_transfer.py
git commit -m "[ADD] import a transfer document with fresh ids and reused users

Co-Authored-By: <your required trailer>"
```

---

### Task 3: Management commands, real-data dry run, docs

**Files:**
- Create: `server/olympic_warriors/management/commands/export_edition.py`
- Create: `server/olympic_warriors/management/commands/import_edition.py`
- Modify: `.gitignore`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write the export command**

Create `server/olympic_warriors/management/commands/export_edition.py`:

```python
"""
Export an edition and everything attached to it to a JSON file without database ids.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from olympic_warriors.models import Edition
from olympic_warriors.transfer import export_edition


class Command(BaseCommand):
    """
    Export an edition to a transfer document (see olympic_warriors.transfer).
    """

    help = "Export an edition and all its rows to a JSON document without database ids."

    def add_arguments(self, parser):
        parser.add_argument("year", type=int)
        parser.add_argument("--out", required=True, help="Path of the JSON file to write.")

    def handle(self, *args, **options):
        year = options["year"]
        try:
            document = export_edition(year)
        except Edition.DoesNotExist as exc:
            raise CommandError(f"No edition for year {year}") from exc
        except Edition.MultipleObjectsReturned as exc:
            raise CommandError(f"Several editions for year {year}; fix the data first") from exc

        with open(options["out"], "w", encoding="utf-8") as out:
            json.dump(document, out, ensure_ascii=False, indent=2)

        counts = ", ".join(f"{name}={len(rows)}" for name, rows in document["tables"].items())
        self.stdout.write(
            f"Exported edition {year} to {options['out']}: "
            f"{len(document['users'])} users, {counts}"
        )
```

- [ ] **Step 2: Write the import command**

Create `server/olympic_warriors/management/commands/import_edition.py`:

```python
"""
Import an edition exported with export_edition, giving every row a fresh id.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from olympic_warriors.transfer import TransferError, import_edition


class DryRun(Exception):
    """Raised inside the transaction to roll a dry run back."""


class Command(BaseCommand):
    """
    Import a transfer document (see olympic_warriors.transfer).
    """

    help = "Import an edition JSON document, matching users by username and creating fresh ids."

    def add_arguments(self, parser):
        parser.add_argument("path", help="JSON file written by export_edition.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Run the import, print the report, roll back."
        )
        parser.add_argument(
            "--replace", action="store_true",
            help="Delete an existing edition with the same year first (users are kept).",
        )

    def handle(self, *args, **options):
        with open(options["path"], encoding="utf-8") as src:
            document = json.load(src)

        try:
            with transaction.atomic():
                report = import_edition(document, replace=options["replace"])
                self._print(report)
                if options["dry_run"]:
                    raise DryRun
        except DryRun:
            self.stdout.write(self.style.WARNING("Dry run: rolled back, nothing persisted."))
        except TransferError as exc:
            raise CommandError(str(exc)) from exc
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported edition {report['year']}."))

    def _print(self, report):
        self.stdout.write(f"Edition {report['year']} -> id {report['edition_id']}")
        self.stdout.write(
            f"Users: {report['users_reused']} reused, {report['users_created']} created"
        )
        for table, count in report["counts"].items():
            self.stdout.write(f"  {table:<16} {count}")
        for path in report["missing_files"]:
            self.stdout.write(self.style.WARNING(f"Missing media file: {path}"))
```

- [ ] **Step 3: Smoke-test the commands on the fixture edition**

There is no fixture edition in the dev database, so exercise the commands against the real local data with a dry run only (no writes):

```bash
docker compose exec server python manage.py export_edition 2024 --out /server/edition-2024.json
docker compose exec server python manage.py export_edition 2026 --out /server/edition-2026.json
docker compose exec server python manage.py import_edition /server/edition-2024.json --dry-run --replace
docker compose exec server python manage.py import_edition /server/edition-2026.json --dry-run --replace
docker compose exec server python manage.py import_edition /server/edition-2026.json --dry-run
```
Expected, in order: two "Exported edition ..." lines (2024 with 6 users and Team=8, Discipline=6, Game=56, BlindtestGuess=80; 2026 with 18 users, Team=6, Discipline=3, Game=15); two reports ending in "Dry run: rolled back"; then `CommandError: Edition 2026 already exists; use --replace to overwrite it`. Confirm nothing changed:

```bash
docker compose exec server python manage.py shell -c "from olympic_warriors.models import Edition; print(sorted(Edition.objects.values_list('year','id')))"
```
Expected: `[(2020, 13), (2024, 8), (2025, 9), (2026, 21)]` (unchanged ids).

If the export reports a `MultipleObjectsReturned` or a dry run raises a `TransferError`, stop and report the message: it is a real data problem in the local database.

- [ ] **Step 4: Ignore the documents, document the commands**

Append to `.gitignore`:

```
# edition transfer documents contain names and emails
server/edition-*.json
```

Verify: `git status --short` shows no `edition-*.json`.

In `CLAUDE.md`, inside the `## Commands` code block, after the `create_tokens_for_users` line add:

```bash
docker compose exec server python manage.py export_edition 2026 --out /server/edition-2026.json   # edition -> JSON without ids
docker compose exec server python manage.py import_edition /server/edition-2026.json --dry-run     # add --replace to overwrite that year
```

And after the "Registration import" paragraph in the backend architecture section add:

```markdown
**Edition transfer:** `olympic_warriors/transfer.py` moves a whole edition between databases (local to prod). The export carries no database ids (users by username, rows cross-referenced by throwaway `_id`s, MTI children as `subclass`/`child`); the import inserts with `save_base(raw=True)` so no model `save()` side effect runs, reuses existing users by username and creates missing ones with a random password. Media files are not in the document: copy `server/mediafiles/` separately.
```

- [ ] **Step 5: Full test run and commit**

```bash
docker compose exec server python manage.py test olympic_warriors -v 2 2>&1 | tail -6
awk 'length > 100 {print FILENAME": "FNR": "length}' server/olympic_warriors/management/commands/export_edition.py server/olympic_warriors/management/commands/import_edition.py
```
Expected: all tests OK (63 existing + 14 new = 77), no awk output. Then:

```bash
git add server/olympic_warriors/management/commands/export_edition.py server/olympic_warriors/management/commands/import_edition.py .gitignore CLAUDE.md
git commit -m "[ADD] export_edition and import_edition management commands

Co-Authored-By: <your required trailer>"
```

---

## Self-review against the spec

- Two commands, thin wrappers over `transfer.py`: Task 3 / Tasks 1-2.
- Document format (`format`, `edition` without id, `users` with the five fields, `tables` in order, `_id`, usernames, omitted edition FK, generic fields, inactive rows, `subclass`/`child`, `BlindtestRound.blindtest` as the Discipline `_id`): Task 1, tested by `test_document_has_no_database_ids...`, `test_subclass_rows_are_marked`, `test_dates_and_files_are_strings`.
- Import order and id mapping through `_root_table`, raw saves, child rows with `force_insert`: Task 2.
- User matching (reuse untouched, create with random password and no flags): Task 2, `test_existing_user_is_reused_untouched_and_missing_user_created`.
- Existing year aborts / `--replace` cascades and keeps users / `--dry-run` rolls back / report contents / missing files / format check / dangling `_id` rollback: Tasks 2 and 3.
- Tests as listed in spec section 5, plus the real-data dry runs: Tasks 1-3.
- Runbook lives in the spec; `.gitignore` and CLAUDE.md: Task 3.
