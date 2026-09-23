"""
Badges people earn from their editions (see the player badges design spec under
docs/superpowers/specs/). earned() computes every computed badge from the current data;
refresh() stores the difference in the Badge table. The nightly cron job, the Edition admin
action and import_edition call refresh(); a page view only reads the table.

The rules read the sequence: the finished active editions with at least one active player,
by year, so a year without an edition and an edition without a roster never break a
streak. Each rule is evaluated over the history up to each edition in turn, and a badge is
earned at the edition that completes it: playing more never takes a badge away.
"""

from dataclasses import dataclass

from .models import Badge
from .profiles import _load, _participations, paris_today

C = Badge.Codes


@dataclass(frozen=True)
class Earned:
    """One computed badge, keyed like a stored computed Badge row."""

    user_id: int
    code: str
    edition_id: int
    tier: int = 0
    discipline: str = ""
    partner_id: int | None = None


@dataclass(frozen=True)
class History:
    """
    What the rules read:
    - sequence: the editions of the sequence by year (annotated with `team_count`);
    - seats: {user id: {sequence index: Participation}}, sequence editions only;
    - users: {user id: User};
    - last_ranks: per sequence index, the rank of the last place, or None (_last_rank);
    - standings: per sequence index, the edition's Standings;
    - first_edition_id: the first finished active edition, roster or not (argonaut).
    """

    sequence: tuple
    seats: dict
    users: dict
    last_ranks: tuple
    standings: tuple
    first_edition_id: int | None


def _rank(seat):
    """The rank of a seat whose participation counts, else None."""
    return seat.rank if seat is not None and seat.counts else None


def _last_rank(edition, standing, ranked):
    """
    The rank of the edition's last place: every active team has a rank, in an edition of at
    least 4 teams, and the worst rank is below the podium, so a last place is never a
    podium place even when the bottom teams tie (ranks 1, 2, 3, 3). None otherwise.
    """
    if edition.id not in ranked or edition.team_count < 4:
        return None
    ranks = [team.ranking for team in standing.teams.values()]
    if not ranks or not all(ranks) or max(ranks) <= 3:
        return None
    return max(ranks)


def history(today=None):
    """The History of the current data on `today` (a Paris date)."""
    loaded = _load(today or paris_today())
    people = _participations(loaded)
    sequence = tuple(
        sorted((loaded.editions[pk] for pk in loaded.standings), key=lambda e: e.year)
    )
    index = {edition.year: i for i, edition in enumerate(sequence)}
    seats = {}
    for user_id, (_, parts) in people.items():
        mine = {index[part.year]: part for part in parts if part.year in index}
        if mine:
            seats[user_id] = mine
    finished = [loaded.editions[pk] for pk in loaded.finished]
    return History(
        sequence=sequence,
        seats=seats,
        users={user_id: user for user_id, (user, _) in people.items()},
        last_ranks=tuple(
            _last_rank(edition, loaded.standings[edition.id], loaded.ranked)
            for edition in sequence
        ),
        standings=tuple(loaded.standings[edition.id] for edition in sequence),
        first_edition_id=min(finished, key=lambda e: e.year).id if finished else None,
    )


PLACES = {1: C.CHAMPION, 2: C.RUNNER_UP, 3: C.BRONZE}


def _places(h):
    """champion, runner-up, bronze, chocolate and wooden-spoon, at every edition earned."""
    for user_id, seats in h.seats.items():
        for i, seat in seats.items():
            rank = _rank(seat)
            if rank is None:
                continue
            edition_id = h.sequence[i].id
            last = rank == h.last_ranks[i]
            if rank in PLACES:
                yield Earned(user_id, PLACES[rank], edition_id)
            if rank == 4 and seat.teams >= 5 and not last:
                yield Earned(user_id, C.CHOCOLATE, edition_id)
            if last:
                yield Earned(user_id, C.WOODEN_SPOON, edition_id)


RULES = (_places,)


def earned(today=None):
    """Every computed badge on `today` (a Paris date, default today), as a set of Earned."""
    h = history(today)
    found = set()
    for rule in RULES:
        found.update(rule(h))
    return found
