"""
The in-app registration: validating an answer, storing it, withdrawing and presenting the
form with the caller's saved answers. Views check who the caller is and whether registration
is open; the rules live here (spec 2026-10-04).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .accounts import change_email
from .models import Player, PlayerRating, PlayerSport
from .emails import usable_email  # noqa: F401  (also imported from here by invitations)
from .models.Player import SportFrequency
from .profiles import _valid_team
from .registration import rate
from .registration_state import closing_date

MAX_SPORTS = 15
MAX_SPORT_NAME = 80
MAX_NOTES = 200
MAX_DURATION_MONTHS = 1200
MAX_TEAM = 500
MAX_DIETARY = 500


class RegistrationError(ValueError):
    """An answer that cannot be stored: `codes` lists every problem once, in the order found."""

    def __init__(self, codes):
        super().__init__(", ".join(codes))
        self.codes = codes


def _is_int_between(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _text(data, key, limit, fail):
    """A free-text answer, stripped; absent or None is blank."""
    raw = data.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str) or "\x00" in raw:  # Postgres refuses a NUL in a text column
        fail("invalid_text")
        return ""
    raw = raw.strip()
    if len(raw) > limit:
        fail("too_long")
    return raw


class WithdrawalRefused(Exception):
    """A player already in a team cannot withdraw through the app: a forfeit goes through
    an organiser, who finds the replacement."""


def validate(data, skills, email_editable, user=None):
    """
    The cleaned answer for `data` (the request body), or RegistrationError listing every
    problem. `skills` are the edition's active RegistrationSkill rows; `email_editable` is
    True when the account has no usable email, which then must come with the answer, and
    must not belong to another active account (`user` is the caller, who may keep their own).
    """
    errors = []

    def fail(code):
        if code not in errors:
            errors.append(code)

    given = data.get("ratings")
    given = given if isinstance(given, dict) else {}
    ratings = {}
    for skill in skills:
        value = given.get(skill.identifier)
        if value is None:
            fail("missing_rating")
        elif _is_int_between(value, 1, 10):
            ratings[skill.identifier] = value
        else:
            fail("invalid_rating")

    global_level = data.get("global_level")
    if not _is_int_between(global_level, 1, 10):
        fail("invalid_global_level")

    frequency = data.get("sport_frequency")
    if frequency in (None, ""):
        fail("missing_frequency")
    elif frequency not in SportFrequency.values:
        fail("invalid_frequency")

    sports = []
    raw_sports = data.get("sports")
    if raw_sports is None:
        raw_sports = []
    if not isinstance(raw_sports, list):
        fail("invalid_sport")
    elif len(raw_sports) > MAX_SPORTS:
        fail("too_many_sports")
    else:
        for row in raw_sports:
            sports.append(_sport(row, fail))

    team_with = _text(data, "team_with", MAX_TEAM, fail)
    team_avoid = _text(data, "team_avoid", MAX_TEAM, fail)
    dietary = _text(data, "dietary_restrictions", MAX_DIETARY, fail)

    if data.get("attendance_confirmed") is not True:
        fail("attendance_required")

    email = None
    if email_editable:
        raw = data.get("email")
        raw = raw.strip().lower() if isinstance(raw, str) else ""
        if not usable_email(raw):
            fail("no_email")
        else:
            try:
                validate_email(raw)
            except ValidationError:
                fail("invalid_email")
            else:
                taken = get_user_model().objects.filter(email__iexact=raw, is_active=True)
                if taken.exclude(pk=getattr(user, "pk", None)).exists():
                    fail("email_taken")
                else:
                    email = raw

    if errors:
        raise RegistrationError(errors)
    return {
        "ratings": ratings,
        "global_level": global_level,
        "sport_frequency": frequency,
        "sports": sports,
        "team_with": team_with,
        "team_avoid": team_avoid,
        "dietary_restrictions": dietary,
        "email": email,
    }


def _sport(row, fail):
    """One cleaned sports row; a row that is not usable is reported and replaced by {}."""
    if not isinstance(row, dict):
        fail("invalid_sport")
        return {}
    name = row.get("sport")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > MAX_SPORT_NAME or "\x00" in name:
        fail("invalid_sport")
    level = "" if row.get("level") is None else row["level"]
    if level not in ("", *PlayerSport.Level.values):  # a non-string never matches
        fail("invalid_sport")
    practice = "" if row.get("practice") is None else row["practice"]
    if practice not in ("", *PlayerSport.Practice.values):
        fail("invalid_sport")
    months = row.get("duration_months")
    if months is not None and not _is_int_between(months, 0, MAX_DURATION_MONTHS):
        fail("invalid_sport")
    notes = row.get("notes")
    if notes is None:
        notes = ""
    if not isinstance(notes, str) or "\x00" in notes:
        fail("invalid_sport")
        notes = ""
    notes = notes.strip()
    if len(notes) > MAX_NOTES:
        fail("too_long")
    return {
        "sport": name,
        "level": level,
        "practice": practice,
        "duration_months": months,
        "notes": notes,
    }


def save(user, edition, skills, cleaned):
    """
    Store a validated answer: the caller's Player of this edition (created, or the existing
    row, reactivated if withdrawn, with its team kept), its PlayerRating per skill, the
    sports replaced as a set, and the account email when one was given. One transaction
    under the user's row lock, so two tabs saving at once cannot create two players.
    """
    weights = {skill.identifier: skill.weight for skill in skills}
    _, global_rating = rate(cleaned["ratings"], weights, cleaned["global_level"])
    fields = {
        "rating": round(global_rating),
        "global_level": cleaned["global_level"],
        "dietary_restrictions": cleaned["dietary_restrictions"],
        "sport_frequency": cleaned["sport_frequency"],
        "team_with": cleaned["team_with"],
        "team_avoid": cleaned["team_avoid"],
        "attendance_confirmed": True,
        "is_active": True,
        "withdrawn_at": None,
    }
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().get(pk=user.pk)
        if cleaned["email"] is not None:
            change_email(locked, cleaned["email"])
        player = _player(locked, edition)
        if player is None:
            player = Player.objects.create(user=locked, edition=edition, **fields)
        else:
            for name, value in fields.items():
                setattr(player, name, value)
            player.save()
        for skill in skills:
            PlayerRating.objects.update_or_create(
                player=player,
                identifier=skill.identifier,
                defaults={
                    "name": skill.name_en,
                    "rating": cleaned["ratings"][skill.identifier],
                    "is_active": True,
                },
            )
        player.playersport_set.all().delete()
        PlayerSport.objects.bulk_create(
            PlayerSport(player=player, order=index, **row)
            for index, row in enumerate(cleaned["sports"])
        )
    return player


def withdraw(user, edition):
    """Soft-delete the caller's Player of the edition and mark it withdrawn by the player
    (the answers stay, for a re-registration). Returns how many rows were switched off.
    Raises WithdrawalRefused once the player has a team."""
    players = list(
        Player.objects.filter(user=user, edition=edition, is_active=True).select_related("team")
    )
    if not players:
        return 0
    # A real team only: an inactive or foreign one (profiles._valid_team) holds nobody.
    if any(_valid_team(player) is not None for player in players):
        raise WithdrawalRefused()
    # Every active row: imports skip Player.clean, so a person may hold more than one.
    Player.objects.filter(pk__in=[player.pk for player in players]).update(
        is_active=False, withdrawn_at=timezone.now()
    )
    return len(players)


def removed_by_organiser(user, edition):
    """True when the caller's Player of the edition is inactive although the player never
    withdrew: an organiser removed it. Only a late pass lets that person register again."""
    player = _player(user, edition)
    return player is not None and not player.is_active and player.withdrawn_at is None


def _player(user, edition):
    """The caller's Player of the edition, an active one first, withdrawn or not."""
    return (
        Player.objects.filter(user=user, edition=edition).order_by("-is_active", "id").first()
    )


def _sport_rows(player):
    return [
        {
            "sport": sport.sport,
            "level": sport.level,
            "practice": sport.practice,
            "duration_months": sport.duration_months,
            "notes": sport.notes,
        }
        for sport in player.playersport_set.all()
    ]


def _answers(player):
    """What the caller saved, with `registered` False once withdrawn (answers are kept)."""
    return {
        "registered": player.is_active,
        "removed_by_organiser": not player.is_active and player.withdrawn_at is None,
        "ratings": {
            rating.identifier: int(rating.rating)
            for rating in player.playerrating_set.filter(is_active=True)
        },
        "global_level": player.global_level,
        "sport_frequency": player.sport_frequency,
        "sports": _sport_rows(player),
        "team_with": player.team_with,
        "team_avoid": player.team_avoid,
        "dietary_restrictions": player.dietary_restrictions,
        "attendance_confirmed": player.attendance_confirmed,
    }


def _suggested(user, edition):
    """The stable answers of the caller's most recent earlier registration, offered as
    defaults: sports, frequency and dietary restrictions. Never ratings, global level,
    wishes or the tick, which change every year."""
    previous = (
        Player.objects.filter(user=user, edition__year__lt=edition.year)
        .order_by("-edition__year", "-is_active", "-id")
        .first()
    )
    if previous is None:
        return None
    return {
        "year": previous.edition.year,
        "sport_frequency": previous.sport_frequency,
        "dietary_restrictions": previous.dietary_restrictions,
        "sports": _sport_rows(previous),
    }


def _choices(enum):
    return [{"value": value, "label": label} for value, label in enum.choices]


def form_payload(user, edition, state):
    """The GET /registration/ body for `user` and `edition` in registration `state`."""
    skills = edition.registrationskill_set.filter(is_active=True)
    player = _player(user, edition)
    return {
        "edition": {
            "year": edition.year,
            "opens": edition.registration_opens.isoformat() if edition.registration_opens else None,
            "closes": closing_date(edition).isoformat(),
            "start_date": edition.start_date.isoformat(),
            "dates_confirmed": edition.dates_confirmed,
        },
        "state": {"is_open": state.is_open, "reason": state.reason},
        "intro": {"fr": edition.registration_intro_fr, "en": edition.registration_intro_en},
        "skills_month": {"fr": edition.skills_month_fr, "en": edition.skills_month_en},
        "skills": [
            {"identifier": s.identifier, "name_fr": s.name_fr, "name_en": s.name_en}
            for s in skills
        ],
        "disciplines": list(
            edition.discipline_set.filter(is_active=True)
            .order_by("id")
            .values_list("name", flat=True)
        ),
        "choices": {
            "frequency": _choices(SportFrequency),
            "level": _choices(PlayerSport.Level),
            "practice": _choices(PlayerSport.Practice),
        },
        "email": {
            "value": user.email if usable_email(user.email) else "",
            "editable": not usable_email(user.email),
        },
        "registration": _answers(player) if player is not None else None,
        "suggested": _suggested(user, edition) if player is None else None,
    }
