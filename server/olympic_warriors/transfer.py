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
    ("Game", Game, "discipline__edition"),
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
