"""The team builder's server side (spec 2026-10-05-team-builder-design.md): the draft's
shape rules, the roster payload, the stale-checked save and Apply. The generator and the
scoring live in the browser; nothing here balances teams."""
from django.db import transaction

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
            if not isinstance(link, dict) or link.get("kind") not in KINDS:
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
