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

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations

from .models import Badge
from .profiles import _load, _participations, _sort_key, paris_today

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


TITLE_STREAKS = {2: C.BACK_TO_BACK, 3: C.THREEPEAT, 4: C.DYNASTY}


def _on_podium(seat):
    rank = _rank(seat)
    return rank is not None and rank <= 3


def _runs(h, seats, holds):
    """
    (sequence index, run length) for every edition of the sequence: how many consecutive
    editions end there where holds(seat) is true for the person, 0 when it is not.
    """
    length = 0
    for i in range(len(h.sequence)):
        seat = seats.get(i)
        length = length + 1 if seat is not None and holds(seat) else 0
        yield i, length


def _streaks(h):
    """back-to-back, threepeat, dynasty and podium-regular: once per streak, at the
    edition completing it."""
    for user_id, seats in h.seats.items():
        for i, length in _runs(h, seats, lambda seat: _rank(seat) == 1):
            if length in TITLE_STREAKS:
                yield Earned(user_id, TITLE_STREAKS[length], h.sequence[i].id)
        for i, length in _runs(h, seats, _on_podium):
            if length == 3:
                yield Earned(user_id, C.PODIUM_REGULAR, h.sequence[i].id)


def _career(h):
    """phoenix, legend, full-set, eternal-second, janus, comeback, on-the-rise, icarus and
    lucky-charm."""
    for user_id, seats in h.seats.items():
        yield from _career_of(h, user_id, seats)


def _career_of(h, user_id, seats):
    out, once = [], set()

    def earn(code, edition_id, repeat=False):
        if repeat or code not in once:
            once.add(code)
            out.append(Earned(user_id, code, edition_id))

    titles = seconds = rise = 0
    places, counted = set(), []
    had_last = previous_last = False
    previous_rank = previous_share = None
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        rank = _rank(seat)
        last = rank is not None and rank == h.last_ranks[i]
        edition_id = edition.id

        if rank == 1:
            if titles and previous_rank != 1:
                earn(C.PHOENIX, edition_id, repeat=True)
            titles += 1
            if titles == 3:
                earn(C.LEGEND, edition_id)
        if rank == 2:
            seconds += 1
            if seconds == 2 and not titles:
                earn(C.ETERNAL_SECOND, edition_id)
        if rank is not None and rank <= 3:
            places.add(rank)
            if places == {1, 2, 3}:
                earn(C.FULL_SET, edition_id)
        had_last = had_last or last
        if titles and had_last:
            earn(C.JANUS, edition_id)
        if previous_last and rank is not None and rank <= 3:
            earn(C.COMEBACK, edition_id, repeat=True)
        if previous_rank == 1 and rank is not None and rank > seat.teams / 2:
            earn(C.ICARUS, edition_id, repeat=True)

        # Relative rank: 0 for first, 1 for last, so editions of different sizes compare.
        share = None if rank is None else (rank - 1) / (seat.teams - 1)
        if share is None:
            rise = 0
        elif previous_share is not None and share < previous_share:
            rise += 1
        else:
            rise = 1
        if rise == 3:
            earn(C.ON_THE_RISE, edition_id, repeat=True)

        if rank is not None:
            counted.append(rank)
            if len(counted) == 3 and all(r <= 3 for r in counted):
                earn(C.LUCKY_CHARM, edition_id)

        previous_rank, previous_share, previous_last = rank, share, last
    return out


VETERAN_TIERS = {3: 1, 5: 2, 10: 3}
EVER_PRESENT_TIERS = {4: 1, 6: 2, 8: 3}
NETWORKER_TIERS = ((20, 1), (40, 2), (60, 3))


def _loyalty(h):
    """rookie, veteran, argonaut, ever-present, homecoming and globetrotter: a
    participation is enough, team or rank not needed."""
    for user_id, seats in h.seats.items():
        played = run = 0
        seen = None
        hosts, present = set(), set()
        for i, edition in enumerate(h.sequence):
            if i not in seats:
                run = 0
                continue
            edition_id = edition.id
            played += 1
            run += 1
            if played == 1:
                yield Earned(user_id, C.ROOKIE, edition_id)
            if played in VETERAN_TIERS:
                yield Earned(user_id, C.VETERAN, edition_id, tier=VETERAN_TIERS[played])
            tier = EVER_PRESENT_TIERS.get(run)
            if tier and tier not in present:
                present.add(tier)
                yield Earned(user_id, C.EVER_PRESENT, edition_id, tier=tier)
            if seen is not None and i - seen > 2:  # missed at least 2 consecutive editions
                yield Earned(user_id, C.HOMECOMING, edition_id)
            seen = i
            host = _sort_key(edition.host.strip())
            if host not in hosts:
                hosts.add(host)
                if len(hosts) == 3:
                    yield Earned(user_id, C.GLOBETROTTER, edition_id)
        # The first finished edition is index 0 exactly when it has a roster.
        if 0 in seats and h.sequence[0].id == h.first_edition_id:
            yield Earned(user_id, C.ARGONAUT, h.first_edition_id)


def _teams(h, i):
    """{team id: sorted user ids} of the people seated on a valid team at sequence index i."""
    teams = defaultdict(list)
    for user_id, seats in h.seats.items():
        seat = seats.get(i)
        if seat is not None and seat.team_id is not None:
            teams[seat.team_id].append(user_id)
    return {team_id: sorted(users) for team_id, users in teams.items()}


def _teammates(h):
    """comrades (once per partner, both ways) and networker (tiers)."""
    together = Counter()
    mates = defaultdict(set)
    for i, edition in enumerate(h.sequence):
        edition_id = edition.id
        for users in _teams(h, i).values():
            for a, b in combinations(users, 2):
                together[(a, b)] += 1
                if together[(a, b)] == 3:
                    yield Earned(a, C.COMRADES, edition_id, partner_id=b)
                    yield Earned(b, C.COMRADES, edition_id, partner_id=a)
            for user_id in users:
                before = len(mates[user_id])
                mates[user_id].update(other for other in users if other != user_id)
                for threshold, tier in NETWORKER_TIERS:
                    if before < threshold <= len(mates[user_id]):
                        yield Earned(user_id, C.NETWORKER, edition_id, tier=tier)


RULES = (_places, _streaks, _career, _loyalty, _teammates)


def earned(today=None):
    """Every computed badge on `today` (a Paris date, default today), as a set of Earned."""
    h = history(today)
    found = set()
    for rule in RULES:
        found.update(rule(h))
    return found
