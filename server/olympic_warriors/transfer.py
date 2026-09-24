"""
Move a whole edition between databases without carrying database ids.

export_edition() turns an Edition and every row hanging off it into a JSON
serialisable document; import_edition() recreates that document with fresh
ids. Users are referenced by username. Rows are written with
Model.save_base(raw=True), as loaddata does, so the model save() overrides
(scheduling, team results, CSV import, score deltas) never run.
"""
import functools
from datetime import datetime, timezone

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.db import models, transaction
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

# Exported tables in dependency order: (name, model, lookup selecting an edition's rows).
TABLES = (
    ("Team", Team, "edition"),
    ("Player", Player, "edition"),
    ("PlayerRating", PlayerRating, "player__edition"),
    ("Discipline", Discipline, "edition"),
    ("TeamResult", TeamResult, "discipline__edition"),
    ("TeamSportRound", TeamSportRound, "discipline__edition"),
    ("Game", Game, "discipline__edition"),
    ("GameEvent", GameEvent, "game__edition"),
    ("BlindtestRound", BlindtestRound, "blindtest__edition"),
    ("BlindtestGuess", BlindtestGuess, "blindtest_round__blindtest__edition"),
)

# Root models an edition export leaves out on purpose: badges are derived from the
# edition's data, and badges.refresh() rebuilds them after an import (import_edition runs
# it). Manual badges are not transferred, and --replace cascade-deletes the replaced
# edition's ones. A UserProfile (photo, showcase, claim) is about a person, not an
# edition, and lives on prod only.
NOT_EXPORTED = frozenset({"Badge", "BadgeRefresh", "UserProfile"})


class TransferError(ValueError):
    """The document cannot be imported as is."""


class EditionExists(TransferError):
    """An edition with that year is already in the database."""


def _root_table(model):
    """Exported table a model's rows belong to; MTI children map to their root parent."""
    parents = model._meta.get_parent_list()
    return (parents[-1] if parents else model).__name__


@functools.lru_cache(maxsize=None)
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
    matches = []
    for child_model in _child_models(type(obj)):
        child = child_model.objects.filter(pk=obj.pk).first()
        if child is not None:
            matches.append((child_model, child))
    if len(matches) > 1:
        raise TransferError(
            f"{type(obj).__name__} {obj.pk} has rows in several child tables"
        )
    if matches:
        subclass, child = matches[0]
        row["subclass"] = subclass.__name__
        row["child"] = _serialize_fields(child, subclass._meta.local_concrete_fields)
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
                raise TransferError(
                    f"{model.__name__}.{field.name} references unknown user {value!r}"
                )
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


def _file_field_names(model, fields=None):
    return [
        f.name
        for f in (model._meta.concrete_fields if fields is None else fields)
        if isinstance(f, models.FileField)
    ]


def _file_paths(document):
    """Every media path referenced by the document (edition, tables, and MTI child payloads)."""
    paths = [document["edition"].get(name) for name in _file_field_names(Edition)]
    for name, model, _ in TABLES:
        names = _file_field_names(model)
        for row in document["tables"].get(name, []):
            paths += [row.get(field) for field in names]
            if row.get("subclass"):
                child = apps.get_model("olympic_warriors", row["subclass"])
                paths += [
                    row.get("child", {}).get(field)
                    for field in _file_field_names(child, child._meta.local_concrete_fields)
                ]
    return [path for path in paths if path]


def _missing_files(document):
    """Media paths the document references that are absent from this side's storage."""
    missing = []
    for path in _file_paths(document):
        try:
            present = default_storage.exists(path)
        except SuspiciousFileOperation:
            present = False
        if not present:
            missing.append(path)
    return missing


def import_edition(document, replace=False):
    """
    Recreate an exported edition with fresh ids, in one transaction.

    Existing users are reused by username and left untouched; missing users are
    created with a fresh random password and no staff flags.

    :param document: dict produced by export_edition.
    :param replace: delete an existing edition with the same year first.
    :return: report dict with edition_id, year, users_reused, users_created,
             created_users (their usernames), counts (per table) and missing_files
             (media paths absent here).
    :raises EditionExists: year already present and replace is False.
    :raises TransferError: unsupported format, dangling reference, or insert failure.
    """
    if document.get("format") != FORMAT:
        raise TransferError(f"Unsupported transfer document format {document.get('format')!r}")
    tables_ok = isinstance(document.get("tables"), dict)
    edition_ok = isinstance(document.get("edition"), dict)
    users_ok = isinstance(document.get("users"), list)
    if not tables_ok or not edition_ok or not users_ok:
        raise TransferError(
            "Malformed transfer document: 'edition' and 'tables' must be objects and "
            "'users' a list"
        )
    unknown = set(document["tables"]) - {name for name, _, _ in TABLES}
    if unknown:
        raise TransferError(f"Document holds unknown tables {sorted(unknown)}")
    year = document["edition"]["year"]

    with transaction.atomic():
        existing = Edition.objects.filter(year=year)
        if existing.exists():
            if not replace:
                raise EditionExists(
                    f"Edition {year} already exists; use --replace to overwrite it"
                )
            existing.delete()

        edition = _insert(
            Edition,
            _deserialize_fields(
                Edition, Edition._meta.concrete_fields, document["edition"], {}, {}, None
            ),
        )

        users, reused, created, created_users = {}, 0, 0, []
        for entry in document["users"]:
            try:
                user = User.objects.filter(username=entry["username"]).first()
                if user is None:
                    user = User.objects.create_user(
                        password=get_random_string(length=8),
                        **{name: entry[name] for name in USER_FIELDS},
                    )
                    created += 1
                    created_users.append(user.username)
                else:
                    reused += 1
                users[entry["username"]] = user
            except TransferError:
                raise
            except Exception as exc:
                raise TransferError(f"user {entry!r}: {exc}") from exc

        ids = {name: {} for name, _, _ in TABLES}
        counts = {}
        for name, model, _ in TABLES:
            rows = document["tables"].get(name, [])
            for row in rows:
                try:
                    kwargs = _deserialize_fields(
                        model, model._meta.concrete_fields, row, ids, users, edition
                    )
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
            counts[name] = len(ids[name])

        return {
            "edition_id": edition.pk,
            "year": year,
            "users_reused": reused,
            "users_created": created,
            "created_users": created_users,
            "counts": counts,
            "missing_files": _missing_files(document),
        }
