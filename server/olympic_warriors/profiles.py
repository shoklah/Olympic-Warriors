"""
Player records across editions, from the team standings of each edition: a person's rank
in an edition is their team's rank, and nothing is stored.

The rules (see the player profiles design spec under docs/superpowers/specs/):
- a person is a user with an active Player in an active edition; one participation per
  (user, edition): the lowest id among the rows with a valid team (active, of the
  player's edition), else the lowest id;
- an edition is finished once its end_date is before today in Europe/Paris; an
  unfinished edition gives no rank, so its standings are not computed;
- the team rank is None without a team, for an inactive team, for a hand-ranked team
  without a final_rank or with one of 0, and for a computed edition where no result has
  a rank yet (nothing revealed or scored would otherwise tie every team for 1st on
  nothing, and missing data must never count as a win);
- a participation counts when finished, ranked, and the edition has at least 2 teams;
- the average rank is the mean rank over counted participations, to one decimal; it is
  shown on the leaderboard and the profile and plays no part in the order;
- the leaderboard ranks people like a medal table on their places (the ranks of their
  counted participations): more 1st places first, then more 2nd places, and so on; an
  extra lower place counts in a person's favour; identical places share a position and
  are listed by name; people with nothing counted follow by name, without a position.
  The average rank plays no part in the order.
- a counted participation also carries its team's discipline places (rank > 0, by
  discipline name); a person's discipline places aggregate those by name across
  editions, sorted best first, and are ordered and positioned by the same medal-table
  rule as the leaderboard, with the name as tie-break.
"""

import math
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db.models import Count, Q

from .models import Edition, Player
from .standings import compute_standings

PARIS = ZoneInfo("Europe/Paris")


def paris_today():
    """Today's calendar date where the event takes place; the server clock runs in UTC."""
    return datetime.now(PARIS).date()


@dataclass(frozen=True)
class DisciplinePlace:
    """One ranked discipline result of a participation's team: the discipline name, the
    edition's year, and the team's rank there."""

    name: str
    year: int
    rank: int


@dataclass(frozen=True)
class DisciplinePlaces:
    """A person's places in one discipline across editions, best first, with the
    discipline's shared position among the person's own disciplines (see
    _discipline_places)."""

    name: str
    places: tuple[DisciplinePlace, ...]
    position: int


@dataclass(frozen=True)
class Participation:
    """One person's edition: their team, its rank among `teams` active teams, and whether
    the edition is over. rank is None without a team, for an inactive team, for a
    hand-ranked team without a final_rank or with one of 0, before the edition ends, or
    for a computed edition where nothing has a rank yet (see the rules in the module
    docstring above, and "Edition rank" in the design spec). disciplines is filled only
    when the participation counts, from the team's ranked discipline standings."""

    year: int
    team_id: int | None
    team_name: str | None
    rank: int | None
    teams: int
    finished: bool
    disciplines: tuple[DisciplinePlace, ...] = ()

    @property
    def counts(self):
        """Whether the edition feeds the places and the average rank: over, ranked, and more
        than one team."""
        return self.finished and self.rank is not None and self.teams >= 2


def _valid_team(player):
    """The player's team when it is active and belongs to the player's edition."""
    team = player.team
    if team is None or not team.is_active or team.edition_id != player.edition_id:
        return None
    return team


def _one_row_per_edition(players):
    """
    Collapse a person's Player rows within one edition into the one that stands for it:
    the lowest id among the rows with a valid team, else the lowest id overall.
    Returns {(user id, edition id): Player}. `players` must be ordered by id.
    """
    chosen = {}
    for player in players:
        key = (player.user_id, player.edition_id)
        kept = chosen.get(key)
        if kept is None or (_valid_team(kept) is None and _valid_team(player) is not None):
            chosen[key] = player
    return chosen


def _hand_ranked(standing):
    """
    True when the edition ranks teams from Team.final_rank rather than computing it:
    compute_standings then leaves every TeamStanding.total_points at None (see
    TeamStanding in standings.py), instead of the computed sum.
    """
    return any(team.total_points is None for team in standing.teams.values())


def _is_ranked(standing):
    """
    Whether this edition's team ranking can be trusted: a hand-ranked edition always can
    be, a computed edition only once at least one of its results actually has a rank.
    Otherwise compute_standings ties every team for 1st on nothing (no discipline
    revealed or scored), and missing data must never count as a win.
    """
    if _hand_ranked(standing):
        return True
    return any(result.ranking != 0 for result in standing.results.values())


@dataclass(frozen=True)
class Loaded:
    """
    What participations() and badges.earned() both read, from 2 + 3 per finished edition with
    a player queries: the active editions by id (annotated with `team_count`, their active
    teams), the chosen Player row per (user id, edition id), the finished edition ids, the
    standings of the finished editions that have a player, and which of those rank.
    """

    editions: dict
    chosen: dict
    finished: frozenset
    standings: dict
    ranked: frozenset


def _load(today):
    """The data behind the participations on `today` (a Paris date)."""
    editions = {
        edition.id: edition
        for edition in Edition.objects.filter(is_active=True).annotate(
            team_count=Count("team", filter=Q(team__is_active=True))
        )
    }
    players = (
        Player.objects.filter(is_active=True, edition_id__in=editions)
        .select_related("user", "team")
        .order_by("id")
    )
    chosen = _one_row_per_edition(players)

    finished = frozenset(pk for pk, edition in editions.items() if edition.end_date < today)
    with_players = {edition_id for _, edition_id in chosen}
    standings = {pk: compute_standings(editions[pk]) for pk in sorted(with_players & finished)}
    ranked = frozenset(pk for pk, standing in standings.items() if _is_ranked(standing))
    return Loaded(editions, chosen, finished, standings, ranked)


def _participations(loaded):
    """Every person's participations from loaded data, see participations()."""
    by_user = {}
    for (user_id, edition_id), player in loaded.chosen.items():
        edition = loaded.editions[edition_id]
        team = _valid_team(player)
        rank = None
        if team is not None and edition_id in loaded.ranked:
            # A hand-entered final_rank of 0 means no rank too.
            rank = loaded.standings[edition_id].team(team.id).ranking or None
        _, parts = by_user.setdefault(user_id, (player.user, []))
        part = Participation(
            year=edition.year,
            team_id=team.id if team else None,
            team_name=team.name if team else None,
            rank=rank,
            teams=edition.team_count,
            finished=edition_id in loaded.finished,
        )
        if part.counts:
            # counts implies a rank, and rank is only set above for a team in a ranked edition.
            disciplines = tuple(
                DisciplinePlace(
                    discipline.discipline_name, edition.year, discipline.standing.ranking
                )
                for discipline in loaded.standings[edition_id].disciplines_of(team.id)
                if discipline.standing.ranking > 0
            )
            part = replace(part, disciplines=disciplines)
        parts.append(part)

    return {
        user_id: (user, tuple(sorted(parts, key=lambda p: p.year, reverse=True)))
        for user_id, (user, parts) in by_user.items()
    }


def participations(today=None):
    """
    Every person's participations, newest edition first, keyed by user id:
    {user_id: (user, (Participation, ...))}.
    Queries: the editions, the players, then three per finished edition with a player.
    """
    return _participations(_load(today or paris_today()))


@dataclass(frozen=True)
class PlayerRecord:
    """A person's editions, places, discipline places and average rank, with their place
    on the leaderboard."""

    user_id: int
    first_name: str
    last_name: str
    participations: tuple[Participation, ...]
    places: tuple[Participation, ...]  # the counted participations, best rank first
    counted: int
    average_rank: float | None
    disciplines: tuple[DisciplinePlaces, ...] = ()
    position: int | None = None

    @property
    def played(self):
        """Editions taken part in, finished or not."""
        return len(self.participations)


def _record(user, parts):
    """A person's record without a position: counted editions, places, discipline places
    and average rank."""
    counted_parts = [part for part in parts if part.counts]
    average_rank = None
    if counted_parts:
        average_rank = round(sum(part.rank for part in counted_parts) / len(counted_parts), 1)
    return PlayerRecord(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        participations=parts,
        places=tuple(sorted(counted_parts, key=lambda part: (part.rank, -part.year))),
        counted=len(counted_parts),
        average_rank=average_rank,
        disciplines=_discipline_places(counted_parts),
    )


def _sort_key(value):
    """Accent-insensitive, case-insensitive text key: NFKD-decompose the string, drop the
    combining marks, then casefold, so "Élodie" sorts with "E" rather than after "Z"."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _by_name(record):
    return (_sort_key(record.last_name), _sort_key(record.first_name), record.user_id)


def _medal_key(ranks):
    """
    Medal-table key over a sequence of ranks, best first, then a sentinel above every
    rank. Comparing two keys compares the number of 1st places, then of 2nd places, and
    so on: at the first difference the lower rank wins, and a sequence that runs out of
    ranks loses to one that still has one, so an extra lower rank counts in its favour.
    """
    return (*ranks, math.inf)


def _places_key(places):
    """Medal-table key of a sequence of places (Participations or DisciplinePlace items,
    each exposing `.rank`): forwards their ranks, best first, to _medal_key."""
    return _medal_key(place.rank for place in places)


def _positioned(items, key):
    """
    `items` (already sorted by `key`) with their shared position: consecutive items whose
    key compares equal reuse the same position (e.g. 1, 2, 2, 4). Yields (position, item)
    pairs in `items` order.
    """
    position, previous = None, None
    for index, item in enumerate(items, start=1):
        current = key(item)
        if current != previous:
            position, previous = index, current
        yield position, item


def _discipline_places(counted_parts):
    """
    A person's discipline places: their counted participations' places grouped by
    discipline name, each sorted best first (lower rank, then newer year), then the
    groups ordered and positioned like the leaderboard's medal table (identical medal
    keys share a position, see _positioned), with the name as tie-break.
    """
    by_name = defaultdict(list)
    for part in counted_parts:
        for place in part.disciplines:
            by_name[place.name].append(place)

    groups = sorted(
        (
            (name, tuple(sorted(places, key=lambda place: (place.rank, -place.year))))
            for name, places in by_name.items()
        ),
        key=lambda group: (_places_key(group[1]), _sort_key(group[0])),
    )
    return tuple(
        DisciplinePlaces(name=name, places=places, position=position)
        for position, (name, places) in _positioned(groups, lambda group: _places_key(group[1]))
    )


def _place(records):
    """
    The ranked records in medal-table order with shared positions (identical places
    share one, listed by name), then the records with nothing counted, by name and
    without a position.
    """
    ranked = sorted(
        (record for record in records if record.counted),
        key=lambda r: (_places_key(r.places), *_by_name(r)),
    )
    placed = [
        replace(record, position=position)
        for position, record in _positioned(ranked, lambda r: _places_key(r.places))
    ]
    waiting = sorted((record for record in records if not record.counted), key=_by_name)
    return placed + waiting


def leaderboard(today=None):
    """
    Every person: the ranked ones in leaderboard order with their shared positions, then
    the ones with nothing counted yet, by name and without a position.
    """
    return _place([_record(user, parts) for user, parts in participations(today).values()])
