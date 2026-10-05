"""The team builder's server side (spec 2026-10-05-team-builder-design.md): the draft's
shape rules, the roster payload, the stale-checked save and Apply. The generator and the
scoring live in the browser; nothing here balances teams."""
from django.db import IntegrityError, transaction

from .models import Edition, Player, PlayerRating, PlayerSport, RegistrationSkill, Team, TeamDraft
from .registration_state import registration_state

MIN_PER_TEAM = 2
MAX_PER_TEAM = 20
MAX_LINKS = 200
KINDS = {"with", "avoid"}
SEED_LIMIT = 2**31


class DraftError(Exception):
    """A draft refused: `codes` are the API's (`invalid_draft`, `unknown_player`, `bad_size`, `too_many_links`)."""

    def __init__(self, codes):
        super().__init__(codes)
        self.codes = codes


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_draft(document, player_ids):
    """The cleaned draft (only the five known keys) or a DraftError listing every problem."""
    ids = set(player_ids)
    errors = []

    def fail(code):
        if code not in errors:
            errors.append(code)

    if not isinstance(document, dict):
        raise DraftError(["invalid_draft"])

    per_team = document.get("players_per_team")
    if not _is_int(per_team) or not MIN_PER_TEAM <= per_team <= MAX_PER_TEAM:
        fail("bad_size")
    seed = document.get("seed")
    if not _is_int(seed) or not 0 <= seed < SEED_LIMIT:
        fail("invalid_draft")

    links = document.get("links", [])
    cleaned_links = []
    if not isinstance(links, list):
        fail("invalid_draft")
    elif len(links) > MAX_LINKS:
        fail("too_many_links")
    else:
        for link in links:
            kind = link.get("kind") if isinstance(link, dict) else None
            if not isinstance(kind, str) or kind not in KINDS:
                fail("invalid_draft")
                continue
            player, target = link.get("player"), link.get("target")
            if not _is_int(player) or not _is_int(target) or player == target:
                fail("invalid_draft")
            elif player not in ids or target not in ids:
                fail("unknown_player")
            else:
                cleaned_links.append({"player": player, "kind": link["kind"], "target": target})

    teams = document.get("teams", [])
    cleaned_teams = []
    placed = set()
    if not isinstance(teams, list):
        fail("invalid_draft")
    else:
        for team in teams:
            members = team.get("players") if isinstance(team, dict) else None
            if not isinstance(members, list) or not all(_is_int(m) for m in members):
                fail("invalid_draft")
                continue
            if any(m not in ids for m in members):
                fail("unknown_player")
                continue
            if len(set(members)) != len(members) or placed & set(members):
                fail("invalid_draft")
                continue
            placed |= set(members)
            cleaned_teams.append({"players": list(members)})

    locked = document.get("locked", [])
    if not isinstance(locked, list) or not all(_is_int(p) for p in locked) or not set(locked) <= placed:
        fail("invalid_draft")

    if errors:
        raise DraftError(errors)
    return {
        "players_per_team": per_team,
        "seed": seed,
        "links": cleaned_links,
        "teams": cleaned_teams,
        "locked": list(locked),
    }


# The payload's queries: players (with user and team), ratings, sports, skills, the draft,
# the teams-exist check and the registration state's skills check.
BUILDER_QUERIES = 7


class StaleDraft(Exception):
    """The draft changed (or was cleared) since the page loaded it; `current` is the stored one or None."""

    def __init__(self, current):
        super().__init__("stale_draft")
        self.current = current


def roster(edition):
    """The active players of active users: the ones the builder places."""
    return Player.objects.filter(edition=edition, is_active=True, user__is_active=True)


def _valid_team_id(player, edition):
    team = player.team
    if team is None or not team.is_active or team.edition_id != edition.pk:
        return None
    return team.pk


def draft_payload(draft):
    return {"document": draft.document, "updated_at": draft.updated_at.isoformat()}


def payload(edition):
    """What `GET /builder/<year>/` serves: the roster with its private registration answers,
    the questionnaire's skills, whether registration is open and the saved draft."""
    players = list(
        roster(edition).select_related("user", "team").order_by("user__last_name", "user__first_name", "id")
    )
    ids = [p.pk for p in players]
    ratings, sports = {}, {}
    for row in PlayerRating.objects.filter(player_id__in=ids, is_active=True).values(
        "player_id", "identifier", "rating"
    ):
        ratings.setdefault(row["player_id"], {})[row["identifier"]] = row["rating"]
    for row in PlayerSport.objects.filter(player_id__in=ids).order_by("order", "id").values(
        "player_id", "sport", "level"
    ):
        sports.setdefault(row["player_id"], []).append({"sport": row["sport"], "level": row["level"]})
    skills = [
        {"identifier": s.identifier, "name_fr": s.name_fr, "name_en": s.name_en}
        for s in RegistrationSkill.objects.filter(edition=edition, is_active=True).order_by("order", "id")
    ]
    draft = TeamDraft.objects.filter(edition=edition).first()
    return {
        "edition": {"year": edition.year},
        "skills": skills,
        "registration_open": registration_state(edition).is_open,
        "teams_exist": Team.objects.filter(edition=edition, is_active=True).exists(),
        "players": [
            {
                "id": p.pk,
                "first_name": p.user.first_name,
                "last_name": p.user.last_name,
                "rating": p.rating,
                "global_level": p.global_level,
                "ratings": ratings.get(p.pk, {}),
                "sport_frequency": p.sport_frequency,
                "sports": sports.get(p.pk, []),
                "team_with": p.team_with,
                "team_avoid": p.team_avoid,
                "team": _valid_team_id(p, edition),
            }
            for p in players
        ],
        "draft": draft_payload(draft) if draft else None,
    }


def save_draft(edition, user, document, based_on):
    """Store the draft, refusing a save based on a version that is no longer the stored one.
    Returns the row. Raises DraftError (shape) or StaleDraft."""
    cleaned = validate_draft(document, roster(edition).values_list("pk", flat=True))
    with transaction.atomic():
        # The same lock as `apply`, so a save never commits between Apply's version check and its teams.
        Edition.objects.select_for_update().get(pk=edition.pk)
        current = TeamDraft.objects.select_for_update().filter(edition=edition).first()
        if current is None:
            if based_on is not None:
                raise StaleDraft(None)
            try:
                with transaction.atomic():
                    return TeamDraft.objects.create(edition=edition, document=cleaned, updated_by=user)
            except IntegrityError:
                raise StaleDraft(TeamDraft.objects.filter(edition=edition).first())
        if based_on != current.updated_at.isoformat():
            raise StaleDraft(current)
        current.document = cleaned
        current.updated_by = user
        current.save()
        return current


def clear_draft(edition):
    TeamDraft.objects.filter(edition=edition).delete()


class ApplyRefused(Exception):
    """Apply refused: `code` is the API's, `status` 409 for a state conflict, 400 for a draft that cannot be applied."""

    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


def sizes_are_even(teams):
    """At least two teams, sizes differing by at most one."""
    sizes = [len(t["players"]) for t in teams]
    return len(sizes) >= 2 and min(sizes) >= 1 and max(sizes) - min(sizes) <= 1


def apply(edition, based_on):
    """Create the teams of the stored draft (the version `based_on`, the `updated_at` the
    caller saw: any other is refused) and place every player, in one transaction under
    the edition's row lock. Existing disciplines get a result per new team (the base
    `Discipline.register_teams`); their games are not scheduled, the reply lists them."""
    from .models import Discipline

    with transaction.atomic():
        Edition.objects.select_for_update().get(pk=edition.pk)
        draft = TeamDraft.objects.filter(edition=edition).first()
        if draft is None:
            raise ApplyRefused("no_draft", 409)
        if based_on != draft.updated_at.isoformat():
            raise ApplyRefused("stale_draft", 409)
        if Team.objects.filter(edition=edition, is_active=True).exists():
            raise ApplyRefused("teams_exist", 409)
        if not sizes_are_even(draft.document["teams"]):
            raise ApplyRefused("bad_size", 400)
        placed = [pid for team in draft.document["teams"] for pid in team["players"]]
        players = {p.pk: p for p in roster(edition)}
        if len(placed) != len(set(placed)) or set(placed) != set(players):
            raise ApplyRefused("incomplete", 400)

        teams = []
        for index, entry in enumerate(draft.document["teams"], start=1):
            team = Team.objects.create(name=f"Équipe {index}", edition=edition)
            for pid in entry["players"]:
                player = players[pid]
                player.team = team
                player.save()
            teams.append({"id": team.pk, "name": team.name, "players": entry["players"]})

        unscheduled = []
        for discipline in Discipline.objects.filter(edition=edition, is_active=True).order_by("id"):
            discipline.register_teams()
            if (
                discipline.pairing_system != Discipline.PairingSystem.NONE
                and not discipline.rounds.filter(is_active=True).exists()
            ):
                unscheduled.append({"id": discipline.pk, "name": discipline.name})
        draft.delete()
        return {"teams": teams, "unscheduled": unscheduled}
