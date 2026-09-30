"""
Badges people earn from their editions (see the player badges design spec under
docs/superpowers/specs/). earned() computes every computed badge from the current data, and
compute() also each person's progress toward the badges whose rule is a count, in the same
pass (the badge progress design spec); refresh() stores the difference in the Badge table.
The monthly cron job, the Edition admin action and import_edition call refresh(); a page
view only reads the table.

The rules read the sequence: the finished active editions with at least one active player,
by year, so a year without an edition and an edition without a roster never break a
streak. Each rule is evaluated over the history up to each edition in turn, and a badge is
earned at the edition that completes it: playing more never takes a badge away. The one
exception is master, a title held rather than earned: the next edition of its discipline
that the person does not win takes it away.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from itertools import combinations

from django.db import transaction
from django.utils import timezone

from .avatars import small_photo_url
from .models import Badge, BadgeRefresh, BlindtestGuess, Game
from .models.ResultTypes import ResultTypes
from .profiles import _contested, _load, _participations, _place, _record, _sort_key, paris_today

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
    # loaded.standings is keyed by exactly the finished editions with a player (see Loaded).
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


MIND, PHYSICAL = "mind", "physical"

# The god of each discipline, by database name. Adding a discipline means picking its god
# here and its kind in KINDS: test_badges fails otherwise.
FAMILIES = {
    "General Culture Quizz": C.ATHENA,
    "Geography Quizz": C.ATHENA,
    "Geoguessr": C.ATHENA,
    "Burger Quizz": C.ATHENA,
    "Blindtest": C.APOLLO,
    "Dance": C.APOLLO,
    "Darts": C.ARTEMIS,
    "Petanque": C.ARTEMIS,
    "Disc Throw": C.ARTEMIS,
    "Frisbee": C.ARTEMIS,
    "Relay": C.HERMES,
    "Jumping Rope": C.HERMES,
    "Obstacle Course": C.HERMES,
    "Blindfolded Obstacle Course": C.HERMES,
    "Crossfit": C.HERACLES,
    "Orienteering": C.THESEUS,
    "Rugby": C.ARES,
    "Football": C.ARES,
    "Handball": C.ARES,
    "Basketball": C.ARES,
    "Volleyball": C.ARES,
    "Dodgeball": C.ARES,
    "Hide and Seek": C.HADES,
    "Fair": C.DIONYSUS,
}
GODS = tuple(dict.fromkeys(FAMILIES.values()))  # the nine, in catalogue order

# Mind or physical, for brains-and-brawn: the Athena disciplines and Blindtest are the mind
# ones. Fair is neither.
MINDS = {name for name, god in FAMILIES.items() if god == C.ATHENA} | {"Blindtest"}
KINDS = {name: MIND if name in MINDS else PHYSICAL for name in FAMILIES if name != "Fair"}

# The target of each non-tiered badge whose rule is a count (see the badge progress design
# spec), read by its rule and by its progress; the tiered ones keep their thresholds in
# VETERAN_TIERS and the other tier tables. full-set's rule compares the places won with
# {1, 2, 3}, which its target of 3 counts.
PROGRESS_TARGETS = {
    C.LEGEND: 3,
    C.FULL_SET: 3,
    C.DECATHLETE: 10,
    C.OLYMPUS: len(GODS),
    C.BACK_TO_BACK: 2,
    C.THREEPEAT: 3,
    C.DYNASTY: 4,
    C.PODIUM_REGULAR: 3,
    C.ON_THE_RISE: 2,
    C.REIGN: 3,
    C.COMRADES: 3,
    C.CLEAN_SWEEP: 3,
    C.ETERNAL_SECOND: 2,
    C.LUCKY_CHARM: 3,
}

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


TITLE_STREAKS = {PROGRESS_TARGETS[code]: code for code in (C.BACK_TO_BACK, C.THREEPEAT, C.DYNASTY)}


def _won(seat):
    return _rank(seat) == 1


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
        for i, length in _runs(h, seats, _won):
            if length in TITLE_STREAKS:
                yield Earned(user_id, TITLE_STREAKS[length], h.sequence[i].id)
        for i, length in _runs(h, seats, _on_podium):
            if length == PROGRESS_TARGETS[C.PODIUM_REGULAR]:
                yield Earned(user_id, C.PODIUM_REGULAR, h.sequence[i].id)


def _career(h):
    """phoenix, legend, full-set, eternal-second, janus, comeback, on-the-rise, icarus and
    lucky-charm."""
    for user_id, seats in h.seats.items():
        yield from _career_of(h, user_id, seats)


def _rises(h, seats):
    """
    (sequence index, rise) for every edition of the sequence, as on-the-rise counts: 1 at a
    ranked edition (a counted participation) no better than the previous edition, one more
    at each one better than the previous, 0 at an unranked or missed edition.
    """
    rise, previous = 0, None
    for i in range(len(h.sequence)):
        seat = seats.get(i)
        rank = _rank(seat)
        # Relative rank: 0 for first, 1 for last, so editions of different sizes compare.
        share = None if rank is None else (rank - 1) / (seat.teams - 1)
        if share is None:
            rise = 0
        elif previous is not None and share < previous:
            rise += 1
        else:
            rise = 1
        previous = share
        yield i, rise


def _career_of(h, user_id, seats):
    out, once = [], set()

    def earn(code, edition_id, repeat=False):
        if repeat or code not in once:
            once.add(code)
            out.append(Earned(user_id, code, edition_id))

    titles = seconds = 0
    places, counted = set(), []
    had_last = previous_last = False
    previous_rank = None
    rises = dict(_rises(h, seats))
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        rank = _rank(seat)
        last = rank is not None and rank == h.last_ranks[i]
        edition_id = edition.id

        if rank == 1:
            if titles and previous_rank != 1:
                earn(C.PHOENIX, edition_id, repeat=True)
            titles += 1
            if titles == PROGRESS_TARGETS[C.LEGEND]:
                earn(C.LEGEND, edition_id)
        if rank == 2:
            seconds += 1
            if seconds == PROGRESS_TARGETS[C.ETERNAL_SECOND] and not titles:
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

        # The first ranked edition of a run is a rise of 1, before any climb.
        if rises[i] == PROGRESS_TARGETS[C.ON_THE_RISE] + 1:
            earn(C.ON_THE_RISE, edition_id, repeat=True)

        if rank is not None:
            counted.append(rank)
            if len(counted) == PROGRESS_TARGETS[C.LUCKY_CHARM] and all(r <= 3 for r in counted):
                earn(C.LUCKY_CHARM, edition_id)

        previous_rank, previous_last = rank, last
    return out


VETERAN_TIERS = {3: 1, 5: 2, 10: 3}
EVER_PRESENT_TIERS = {4: 1, 6: 2, 8: 3}
NETWORKER_TIERS = ((5, 1), (10, 2), (20, 3))


def _loyalty(h):
    """rookie, veteran, argonaut, ever-present and homecoming: a participation is enough,
    team or rank not needed."""
    for user_id, seats in h.seats.items():
        played = run = 0
        seen = None
        present = set()
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
        if _argonaut(h, seats):
            yield Earned(user_id, C.ARGONAUT, h.first_edition_id)


def _argonaut(h, seats):
    """Whether the person played the first finished edition, which is index 0 of the sequence
    exactly when it has a roster."""
    return 0 in seats and h.sequence[0].id == h.first_edition_id


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
                if together[(a, b)] == PROGRESS_TARGETS[C.COMRADES]:
                    yield Earned(a, C.COMRADES, edition_id, partner_id=b)
                    yield Earned(b, C.COMRADES, edition_id, partner_id=a)
            for user_id in users:
                before = len(mates[user_id])
                mates[user_id].update(other for other in users if other != user_id)
                for threshold, tier in NETWORKER_TIERS:
                    if before < threshold <= len(mates[user_id]):
                        yield Earned(user_id, C.NETWORKER, edition_id, tier=tier)


def _tables(h):
    """
    (sequence index, counted, {user id: position}) for every all-time table the hall of fame
    reads: the /players leaderboard built from the editions up to that index, from the first
    index at which two editions of the sequence have counted participations (the table after
    a single edition is only that edition's ranking, which the place badges cover). counted
    says whether the edition at that index has counted participations of its own.
    """
    with_counted = 0
    for i in range(len(h.sequence)):
        counted = any(i in seats and seats[i].counts for seats in h.seats.values())
        if counted:
            with_counted += 1
        if with_counted < 2:
            continue
        records = []
        for user_id, seats in h.seats.items():
            parts = tuple(seats[j] for j in sorted(seats, reverse=True) if j <= i)
            if parts:
                records.append(_record(h.users[user_id], parts))
        yield i, counted, {record.user_id: record.position for record in _place(records)}


FAME = ((C.HALL_OF_FAME_PODIUM, 3), (C.HALL_OF_FAMER, 10))


def _hall_of_fame(h):
    """
    goat, alone-at-the-top, hall-of-fame-podium and hall-of-famer (once each), reign (once
    per streak), kingslayer and rocket (at every table earned). A table after an edition
    where no participation counts (nothing ranked yet) breaks every reign, as an unranked
    edition breaks a place streak: missing data never counts. It is the previous table
    unchanged, so it gives none of the other badges anyway.

    Returns ([Earned], {user id: (current, best)}): the badges, and every seated person's
    reign runs after the last table, which _counters reads rather than replaying the tables.
    """
    out, reached = [], set()
    reign, longest = Counter(), Counter()
    previous = None
    for i, counted, positions in _tables(h):
        edition_id = h.sequence[i].id
        leaders = [user_id for user_id, position in positions.items() if position == 1]
        for user_id, position in positions.items():
            if position is None:
                continue
            candidates = [(C.GOAT, position == 1), (C.ALONE_AT_THE_TOP, leaders == [user_id])]
            candidates += [(code, position <= top) for code, top in FAME]
            for code, holds in candidates:
                if holds and (user_id, code) not in reached:
                    reached.add((user_id, code))
                    out.append(Earned(user_id, code, edition_id))
        for user_id in h.seats:
            on_top = counted and positions.get(user_id) == 1
            reign[user_id] = reign[user_id] + 1 if on_top else 0
            longest[user_id] = max(longest[user_id], reign[user_id])
            if reign[user_id] == PROGRESS_TARGETS[C.REIGN]:
                out.append(Earned(user_id, C.REIGN, edition_id))
        if previous is not None:
            for user_id in leaders:
                if previous.get(user_id) != 1:
                    out.append(Earned(user_id, C.KINGSLAYER, edition_id))
            climbs = {
                user_id: previous[user_id] - position
                for user_id, position in positions.items()
                if position is not None and previous.get(user_id) is not None
            }
            best = max(climbs.values(), default=0)
            if best >= 1:
                for user_id, climb in climbs.items():
                    if climb == best:
                        out.append(Earned(user_id, C.ROCKET, edition_id))
        previous = positions
    return out, {user_id: (reign[user_id], longest[user_id]) for user_id in h.seats}


SPECIALIST_TIERS = {2: 1, 3: 2, 4: 3}
ALL_ROUNDER_TIERS = ((3, 1), (5, 2), (8, 3))


@dataclass(frozen=True)
class DisciplineResult:
    """A team's result in one discipline of a sequence edition, with its standing's rank
    (0 when hidden, unscored, or in an uncontested discipline: see _discipline_results)."""

    team_id: int
    discipline_id: int
    name: str
    result_type: str
    points: int | None
    ranking: int


def _discipline_results(h):
    """
    {sequence index: [DisciplineResult]}: the active results of the sequence's active teams
    and disciplines, read from each edition's Standings (disciplines_of), which
    compute_standings already loaded: no query of its own. A discipline whose ranked results
    all share one rank (profiles._contested: a lone scored result, or every team tied on 0
    before any game) beats nobody, so its results rank 0 here as they give no place on the
    profiles: no win, no podium, and no ranked discipline for the metronome.
    """
    results = {}
    for i, standing in enumerate(h.standings):
        contested = _contested(standing)
        results[i] = [
            DisciplineResult(
                team_id,
                discipline.discipline_id,
                discipline.discipline_name,
                discipline.result_type,
                discipline.points,
                discipline.standing.ranking if discipline.discipline_id in contested else 0,
            )
            for team_id, disciplines in standing.team_disciplines.items()
            for discipline in disciplines
        ]
    return results


def _disciplines(h):
    """specialist, master, all-rounder, decathlete, brains-and-brawn, clean-sweep, metronome,
    uncrowned, photo-finish, the gods and olympus."""
    if not h.sequence:
        return
    results = _discipline_results(h)
    for user_id, seats in h.seats.items():
        yield from _disciplines_of(h, results, user_id, seats)
    yield from _masters(h, results)


MASTER_EDITIONS = 2


def _held(results):
    """
    {discipline name: {sequence index: team ids}}: for each edition of the sequence that
    ranked a discipline of that name, the teams 1st in every ranked discipline of that name
    there (two disciplines of one name in an edition are two events to win, not one).
    """
    held = defaultdict(dict)
    for i, rows in results.items():
        events = defaultdict(dict)  # name -> {discipline id: teams ranked 1st}
        for r in rows:
            if r.ranking:
                firsts = events[r.name].setdefault(r.discipline_id, set())
                if r.ranking == 1:
                    firsts.add(r.team_id)
        for name, by_discipline in events.items():
            held[name][i] = set.intersection(*by_discipline.values())
    return held


def _masters(h, results):
    """
    master: won every edition of the sequence that ranked a discipline (matched by name), at
    least MASTER_EDITIONS of them, earned at the one that completed it. Unlike every other
    badge it is judged on the whole sequence, not up to each edition: the next edition of the
    discipline that the person does not win, played or missed, takes it away (the refresh
    deletes the row). A hidden, unscored or uncontested discipline ranks nothing here
    (_discipline_results), so it neither extends nor breaks the run, and an unfinished
    edition is not in the sequence yet.
    """
    held = _held(results)
    for name in sorted(held):
        editions = held[name]
        if len(editions) < MASTER_EDITIONS:
            continue
        completed = h.sequence[sorted(editions)[MASTER_EDITIONS - 1]].id
        for user_id, seats in h.seats.items():
            if all(
                i in seats and seats[i].team_id in winners for i, winners in editions.items()
            ):
                yield Earned(user_id, C.MASTER, completed, discipline=name)


def _disciplines_of(h, results, user_id, seats):
    won_times = Counter()
    won, podiums, gods = set(), set(), set()
    decathlete = False
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        if seat is None or seat.team_id is None:
            continue
        edition_id = edition.id
        rows = results.get(i, [])
        mine = [r for r in rows if r.team_id == seat.team_id]
        wins = [r for r in mine if r.ranking == 1]
        names = sorted({r.name for r in wins})

        for name in names:
            won_times[name] += 1
            tier = SPECIALIST_TIERS.get(won_times[name])
            if tier:
                yield Earned(user_id, C.SPECIALIST, edition_id, tier=tier, discipline=name)
        before = len(won)
        won.update(names)
        for threshold, tier in ALL_ROUNDER_TIERS:
            if before < threshold <= len(won):
                yield Earned(user_id, C.ALL_ROUNDER, edition_id, tier=tier)
        podium = _podium(edition, mine)
        podiums.update(r.name for r in podium)
        if not decathlete and len(podiums) >= PROGRESS_TARGETS[C.DECATHLETE]:
            decathlete = True
            yield Earned(user_id, C.DECATHLETE, edition_id)

        kinds = {KINDS.get(name) for name in names}
        if MIND in kinds and PHYSICAL in kinds:
            yield Earned(user_id, C.BRAINS_AND_BRAWN, edition_id)
        if len(wins) >= PROGRESS_TARGETS[C.CLEAN_SWEEP]:
            yield Earned(user_id, C.CLEAN_SWEEP, edition_id)
        ranked = {r.discipline_id for r in rows if r.ranking}
        on_podium = {r.discipline_id for r in podium}
        if len(ranked) >= 4 and ranked <= on_podium:
            yield Earned(user_id, C.METRONOME, edition_id)
        if _uncrowned(rows, seat, wins):
            yield Earned(user_id, C.UNCROWNED, edition_id)
        if _photo_finish(h, i, rows, seat, wins):
            yield Earned(user_id, C.PHOTO_FINISH, edition_id)

        for name in names:
            god = FAMILIES.get(name)
            if god and god not in gods:
                gods.add(god)
                yield Earned(user_id, god, edition_id)
                if len(gods) == PROGRESS_TARGETS[C.OLYMPUS]:
                    yield Earned(user_id, C.OLYMPUS, edition_id)


def _podium(edition, mine):
    """The results among `mine` (one team's, in `edition`) on a discipline podium. A podium
    needs an edition of at least 4 teams: in a smaller one every result is on the podium,
    the last place included."""
    return [r for r in mine if 1 <= r.ranking <= 3] if edition.team_count >= 4 else []


def _uncrowned(rows, seat, wins):
    """The most discipline wins of the edition (at least 2, no team with more), without the
    title (the person's participation counts and is not 1st)."""
    per_team = Counter(r.team_id for r in rows if r.ranking == 1)
    rank = _rank(seat)
    return len(wins) >= 2 and len(wins) == max(per_team.values()) and rank not in (None, 1)


def _photo_finish(h, i, rows, seat, wins):
    """A points discipline won on the points-difference tie-breaker (a rank-2 result with the
    same points), or a computed edition won alone by 1 total point."""
    for win in wins:
        if win.result_type == ResultTypes.POINTS and any(
            r.discipline_id == win.discipline_id and r.ranking == 2 and r.points == win.points
            for r in rows
        ):
            return True
    if _rank(seat) != 1:
        return False
    teams = h.standings[i].teams
    mine = teams.get(seat.team_id)
    if mine is None or mine.total_points is None:  # hand-ranked: no totals
        return False
    leaders = [team_id for team_id, team in teams.items() if team.ranking == 1]
    others = [team.total_points for team_id, team in teams.items() if team_id != seat.team_id]
    return leaders == [seat.team_id] and bool(others) and mine.total_points - max(others) <= 1


@dataclass(frozen=True)
class GameRow:
    """One game of a sequence edition, as the game badges read it."""

    discipline_name: str
    revealed: bool
    team1_id: int
    score1: int
    team2_id: int
    score2: int


@dataclass(frozen=True)
class GameFacts:
    """What one edition's games say about its teams."""

    records: dict  # team id -> {discipline name: (played, won, lost)}, revealed games only
    shutouts: frozenset
    steamrollers: dict  # team id -> discipline names of that team's biggest margin there


def _game_rows(h):
    """{sequence index: [GameRow]}: the active, played games of active rounds of active
    disciplines, the filter compute_standings uses (1 query)."""
    index = {edition.id: i for i, edition in enumerate(h.sequence)}
    rows = Game.objects.filter(
        discipline__edition_id__in=index,
        discipline__is_active=True,
        round__is_active=True,
        is_active=True,
        is_played=True,
    ).values_list(
        "discipline__edition_id", "discipline__name", "discipline__reveal_score",
        "team1_id", "score1", "team2_id", "score2",
    )
    games = defaultdict(list)
    for edition_id, *game in rows:
        games[index[edition_id]].append(GameRow(*game))
    return games


def _game_facts(games):
    """The GameFacts of one edition's games. Steamroller margins are judged discipline by
    discipline, so raw scores never compare across sports: a darts leg's 301-141 does not
    outweigh a rugby 13-0."""
    records = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    shutouts = set()
    margins = defaultdict(list)  # discipline name -> [(margin, team id)], revealed wins only
    for game in games:
        if not game.revealed:  # a badge never leaks a hidden score
            continue
        for team_id, mine, theirs in (
            (game.team1_id, game.score1, game.score2),
            (game.team2_id, game.score2, game.score1),
        ):
            record = records[team_id][game.discipline_name]
            record[0] += 1
            if mine > theirs:
                record[1] += 1
                margins[game.discipline_name].append((mine - theirs, team_id))
                if theirs == 0:
                    shutouts.add(team_id)
            elif mine < theirs:
                record[2] += 1
    steamrollers = defaultdict(set)
    for name, entries in margins.items():
        best = max(margin for margin, _ in entries)
        for margin, team_id in entries:
            if margin == best:
                steamrollers[team_id].add(name)
    return GameFacts(
        records={
            team_id: {name: tuple(r) for name, r in by_name.items()}
            for team_id, by_name in records.items()
        },
        shutouts=frozenset(shutouts),
        steamrollers={team_id: frozenset(names) for team_id, names in steamrollers.items()},
    )


def _perfect_pitch(h):
    """
    {sequence index: team ids} that found artist and song in every round of a revealed,
    active blindtest (1 query): every active round that has at least one active guess. A
    round without any is left out rather than missed, which only matters for data made
    outside Blindtest.save(): it creates a guess per team for every round.
    """
    index = {edition.id: i for i, edition in enumerate(h.sequence)}
    rows = BlindtestGuess.objects.filter(
        blindtest_round__blindtest__edition_id__in=index,
        blindtest_round__blindtest__is_active=True,
        blindtest_round__blindtest__reveal_score=True,
        blindtest_round__is_active=True,
        is_active=True,
    ).values_list(
        "blindtest_round__blindtest__edition_id", "blindtest_round__blindtest_id",
        "blindtest_round_id", "team_id", "is_artist_correct", "is_song_correct",
    )
    rounds, found, edition_of = defaultdict(set), defaultdict(set), {}
    for edition_id, blindtest_id, round_id, team_id, artist, song in rows:
        rounds[blindtest_id].add(round_id)
        edition_of[blindtest_id] = index[edition_id]
        if artist and song:
            found[(blindtest_id, team_id)].add(round_id)
    teams = defaultdict(set)
    for (blindtest_id, team_id), rounds_found in found.items():
        if rounds_found == rounds[blindtest_id]:
            teams[edition_of[blindtest_id]].add(team_id)
    return teams


def _games(h):
    """unbeaten, perfect-run, shutout, steamroller and perfect-pitch."""
    if not h.sequence:
        return
    games = _game_rows(h)
    pitch = _perfect_pitch(h)
    facts = [_game_facts(games.get(i, [])) for i in range(len(h.sequence))]
    for user_id, seats in h.seats.items():
        for i, edition in enumerate(h.sequence):
            seat = seats.get(i)
            if seat is None or seat.team_id is None:
                continue
            edition_id, team_id, fact = edition.id, seat.team_id, facts[i]
            for name, (played, won, lost) in sorted(fact.records.get(team_id, {}).items()):
                if played >= 3 and lost == 0:
                    code = C.PERFECT_RUN if won == played else C.UNBEATEN
                    yield Earned(user_id, code, edition_id, discipline=name)
            if team_id in fact.shutouts:
                yield Earned(user_id, C.SHUTOUT, edition_id)
            for name in sorted(fact.steamrollers.get(team_id, ())):
                yield Earned(user_id, C.STEAMROLLER, edition_id, discipline=name)
            if team_id in pitch.get(i, ()):
                yield Earned(user_id, C.PERFECT_PITCH, edition_id)


# The hall of fame runs apart, in _earned(), which also keeps its reign runs.
RULES = (_places, _streaks, _career, _loyalty, _teammates, _disciplines, _games)


def _earned(h):
    """Every computed badge of the History `h`, as a set of Earned, and the reign runs the
    hall of fame kept (see _hall_of_fame)."""
    found, reigns = _hall_of_fame(h)
    found = set(found)
    for rule in RULES:
        found.update(rule(h))
    return found, reigns


@dataclass(frozen=True)
class Progress:
    """
    One person's progress toward a badge whose rule is a count, keyed like a stored
    BadgeProgress row (one per user and code): the count (None once out of reach), the best
    run for a streak, and what the count is about: the discipline name (specialist), the
    partner (comrades) or the edition's year (clean-sweep), never set on a count of 0. The
    target is not stored: it follows from the code and the count (PROGRESS_TARGETS and the
    tier tables). See the badge progress design spec.
    """

    user_id: int
    code: str
    value: int | None
    best: int | None = None
    reachable: bool = True
    discipline: str = ""
    partner_id: int | None = None
    year: int | None = None


@dataclass(frozen=True)
class Counters:
    """
    One person's raw progress counters now, after the last edition of the sequence (all 0
    for someone without a seat), each the number its rule counts. A run is (current, best):
    the run ending at the last edition, 0 after a break, and the longest one. "latest" is
    the sequence index of the last edition that added to a count.
    """

    played: int  # veteran: editions played
    present: tuple  # ever-present: the run of editions played
    mates: int  # networker: distinct teammates
    wins: dict  # specialist: {discipline name: (editions won, latest)}
    won: int  # all-rounder: discipline names won
    titles: int  # legend: editions won
    places: int  # full-set: places won among 1st, 2nd and 3rd
    podiums: int  # decathlete: discipline names with a podium (see _podium)
    gods: int  # olympus: gods with a discipline won
    title_run: tuple  # back-to-back, threepeat and dynasty: the run of editions won
    podium_run: tuple  # podium-regular: the run of podiums
    rise: tuple  # on-the-rise: the run of rises, max(rise - 1, 0) over _rises
    reign: tuple  # reign: the run at 1st of the all-time table (_hall_of_fame)
    together: dict  # comrades: {partner id: (editions on the same team, latest)}
    sweeps: dict  # clean-sweep: {sequence index: discipline results won}, wins only
    seconds: int  # eternal-second: 2nd places
    seconds_closed: bool  # out of reach: an edition won before the second 2nd place
    lucky: int  # lucky-charm: podiums among the first three counted editions
    lucky_closed: bool  # out of reach: one of those three off the podium
    argonaut_closed: bool  # out of reach: the first edition is over, without the person


def _run(runs):
    """(current, best) of (sequence index, length) pairs such as _runs() yields: the length
    at the last edition and the longest, (0, 0) over an empty sequence."""
    current = best = 0
    for _, length in runs:
        current, best = length, max(best, length)
    return current, best


def _partners(h):
    """{user id: {partner id: (editions together, latest index)}}, both ways: comrades' keyed
    count over the teams _teammates reads, whose keys are networker's teammates."""
    together = defaultdict(dict)
    for i in range(len(h.sequence)):
        for users in _teams(h, i).values():
            for a, b in combinations(users, 2):
                for user_id, partner in ((a, b), (b, a)):
                    shared, _ = together[user_id].get(partner, (0, None))
                    together[user_id][partner] = (shared + 1, i)
    return together


def _discipline_counts(h, results, seats):
    """
    One person's discipline counters, as _disciplines_of counts them: ({discipline name:
    (editions won, latest index)}, {sequence index: discipline results won}, the discipline
    names with a podium). A name counts once per edition, a result won once each.
    """
    wins, sweeps, podiums = {}, {}, set()
    for i, edition in enumerate(h.sequence):
        seat = seats.get(i)
        if seat is None or seat.team_id is None:
            continue
        mine = [r for r in results.get(i, []) if r.team_id == seat.team_id]
        firsts = [r for r in mine if r.ranking == 1]
        for name in {r.name for r in firsts}:
            won, _ = wins.get(name, (0, None))
            wins[name] = (won + 1, i)
        if firsts:
            sweeps[i] = len(firsts)
        podiums.update(r.name for r in _podium(edition, mine))
    return wins, sweeps, podiums


def _counters(h, reigns):
    """
    Every person's raw progress counters now: {user id: Counters} for every person of
    h.users, including those without a finished edition yet. They read what the rules read
    (_runs, _rises, _partners over _teams, _discipline_results), and `reigns` are
    _hall_of_fame's reign runs, so the all-time tables are not replayed: no query.
    """
    results = _discipline_results(h)
    partners = _partners(h)
    seconds, lucky = PROGRESS_TARGETS[C.ETERNAL_SECOND], PROGRESS_TARGETS[C.LUCKY_CHARM]
    counters = {}
    for user_id in h.users:
        seats = h.seats.get(user_id, {})
        ranks = [_rank(seats.get(i)) for i in range(len(h.sequence))]
        counted = [rank for rank in ranks if rank is not None]
        first_three = counted[:lucky]
        # eternal-second closes at an edition won before the second 2nd place.
        crowned_first = 1 in ranks and ranks[: ranks.index(1)].count(2) < seconds
        wins, sweeps, podiums = _discipline_counts(h, results, seats)
        counters[user_id] = Counters(
            played=len(seats),
            present=_run(_runs(h, seats, lambda seat: True)),
            mates=len(partners[user_id]),
            wins=wins,
            won=len(wins),
            titles=ranks.count(1),
            places=len({rank for rank in counted if rank <= 3}),
            podiums=len(podiums),
            gods=len({FAMILIES[name] for name in wins if name in FAMILIES}),
            title_run=_run(_runs(h, seats, _won)),
            podium_run=_run(_runs(h, seats, _on_podium)),
            rise=_run((i, max(rise - 1, 0)) for i, rise in _rises(h, seats)),
            reign=reigns.get(user_id, (0, 0)),
            together=partners[user_id],
            sweeps=sweeps,
            seconds=ranks.count(2),
            seconds_closed=crowned_first,
            lucky=sum(rank <= 3 for rank in first_three),
            lucky_closed=any(rank > 3 for rank in first_three),
            argonaut_closed=h.first_edition_id is not None and not _argonaut(h, seats),
        )
    return counters


def _specialist(wins):
    """The discipline name specialist's row follows (None without a win): the most editions
    won below the top tier, then the latest won, then the name; when every name is at the
    top tier, the most won, then the latest, then the name."""
    top = max(SPECIALIST_TIERS)
    names = [name for name, (won, _) in wins.items() if won < top] or list(wins)
    return min(
        names,
        key=lambda name: (-wins[name][0], -wins[name][1], _sort_key(name), name),
        default=None,
    )


def _comrade(h, together):
    """The partner comrades' row follows (None when every partner is at the target, or
    without any): among those below the target, the most editions together, then the
    latest, then the last name, first name and id, as _grouped orders partners."""

    def key(partner):
        shared, latest = together[partner]
        user = h.users[partner]
        return (-shared, -latest, _sort_key(user.last_name), _sort_key(user.first_name), partner)

    target = PROGRESS_TARGETS[C.COMRADES]
    return min((p for p, (shared, _) in together.items() if shared < target), key=key, default=None)


def _progress(h, counters, found):
    """
    The Progress rows of every person's `counters`, given the badges `found` (from the same
    History, so a revoked badge is still earned here) as the design spec's "Which rows
    exist" says:
    - a tiered code: always, 0 included;
    - a non-tiered code: only while not earned, without a value once out of reach;
    - comrades: unless earned with no partner left below the target, so someone without
      any teammate reads 0;
    - argonaut: only once out of reach (it has no count to show before);
    - no row for the other codes.
    """
    held = {(badge.user_id, badge.code) for badge in found}
    rows = set()
    for user_id, c in counters.items():
        row = partial(Progress, user_id)
        name = _specialist(c.wins)
        rows.update(
            (
                row(C.VETERAN, c.played),
                row(C.EVER_PRESENT, c.present[0], best=c.present[1]),
                row(C.NETWORKER, c.mates),
                row(C.SPECIALIST, c.wins[name][0] if name else 0, discipline=name or ""),
                row(C.ALL_ROUNDER, c.won),
            )
        )

        sweep = row(C.CLEAN_SWEEP, 0)
        if c.sweeps:  # the edition with the most wins, the latest of equals
            won, i = max((won, i) for i, won in c.sweeps.items())
            sweep = row(C.CLEAN_SWEEP, won, year=h.sequence[i].year)
        until_earned = [
            row(C.LEGEND, c.titles),
            row(C.FULL_SET, c.places),
            row(C.DECATHLETE, c.podiums),
            row(C.OLYMPUS, c.gods),
            *(row(code, c.title_run[0], best=c.title_run[1]) for code in TITLE_STREAKS.values()),
            row(C.PODIUM_REGULAR, c.podium_run[0], best=c.podium_run[1]),
            row(C.ON_THE_RISE, c.rise[0], best=c.rise[1]),
            row(C.REIGN, c.reign[0], best=c.reign[1]),
            sweep,
        ]
        for code, count, closed in (
            (C.ETERNAL_SECOND, c.seconds, c.seconds_closed),
            (C.LUCKY_CHARM, c.lucky, c.lucky_closed),
        ):
            until_earned.append(row(code, None, reachable=False) if closed else row(code, count))
        if c.argonaut_closed:
            until_earned.append(row(C.ARGONAUT, None, reachable=False))
        rows.update(p for p in until_earned if (user_id, p.code) not in held)

        partner = _comrade(h, c.together)
        if partner is not None:
            rows.add(row(C.COMRADES, c.together[partner][0], partner_id=partner))
        elif (user_id, C.COMRADES) not in held:
            rows.add(row(C.COMRADES, 0))
    return rows


def compute(today=None):
    """
    Every computed badge and every progress row on `today` (a Paris date, default today),
    in one pass over one History, so a bar and the badges always agree: (set of Earned, set
    of Progress). The progress adds no query to the badges'.
    """
    h = history(today)
    found, reigns = _earned(h)
    return found, _progress(h, _counters(h, reigns), found)


def earned(today=None):
    """Every computed badge on `today` (a Paris date, default today), as a set of Earned."""
    return compute(today)[0]


@dataclass(frozen=True)
class RefreshReport:
    """What a refresh changed."""

    added: int
    removed: int
    kept: int
    refreshed_at: datetime


KEY_FIELDS = ("user_id", "code", "edition_id", "tier", "discipline", "partner_id")


def refresh(today=None):
    """
    Store earned(today) in the Badge table, in one transaction under the BadgeRefresh row
    lock: delete the computed rows no longer earned (active or not), bulk-create the new
    ones, and leave the others alone, so created_at and a revoked row's is_active survive.
    Of the duplicates of a key still earned, one row stays: an inactive one first, so a
    revocation is never lost, else the lowest id.

    Only the rows of active editions are read. An inactive edition is out of the sequence
    and earns nothing, so its rows are left as they are (profiles already hide them) and
    come back unchanged, revocations and created_at included, once it is reactivated.
    Manual rows are never read or written.
    """
    with transaction.atomic():
        BadgeRefresh.objects.get_or_create(pk=1)  # a flushed test database loses the row
        state = BadgeRefresh.objects.select_for_update().get(pk=1)
        wanted = {tuple(getattr(e, f) for f in KEY_FIELDS): e for e in earned(today)}
        stored, active = defaultdict(list), {}
        computed = Badge.objects.filter(is_manual=False, edition__is_active=True)
        for pk, is_active, *key in computed.values_list("id", "is_active", *KEY_FIELDS):
            stored[tuple(key)].append(pk)
            active[pk] = is_active
        gone = []
        for key, pks in stored.items():
            if key in wanted:  # one row stays: an inactive one first, else the lowest id
                pks = sorted(pks, key=lambda pk: (active[pk], pk))[1:]
            gone += pks
        new = [
            Badge(
                user_id=e.user_id, code=e.code, edition_id=e.edition_id, tier=e.tier,
                discipline=e.discipline, partner_id=e.partner_id,
            )
            for key, e in wanted.items()
            if key not in stored
        ]
        if gone:
            Badge.objects.filter(id__in=gone).delete()
        if new:
            Badge.objects.bulk_create(new)
        state.refreshed_at = timezone.now()
        state.save(update_fields=["refreshed_at"])
    return RefreshReport(
        added=len(new), removed=len(gone), kept=len(wanted) - len(new),
        refreshed_at=state.refreshed_at,
    )


CATALOGUE_ORDER = {code: n for n, code in enumerate(Badge.Codes.values)}


def _shown_rows():
    """The badge rows a profile shows: active rows of active editions, with what grouping
    them reads (the edition's year, the partner's names and profile row, for the photo),
    all joined in: a partner without a profile row is cached as None, so still no query."""
    return Badge.objects.filter(is_active=True, edition__is_active=True).select_related(
        "edition", "partner__profile"
    )


def profile_badges(user_id):
    """
    The person's active badges of active editions for GET /profile/<id>/ (1 query), grouped
    by (code, discipline, partner) in catalogue order: [{code, tier, years, discipline,
    partner}], `tier` the highest, `years` sorted, the partner as {id, first_name,
    last_name, photo} (the small photo URL or None; never the login name).
    """
    return _grouped(_shown_rows().filter(user_id=user_id))


def badges_by_user(user_ids):
    """
    profile_badges() for each of `user_ids` (a collection of ids) in 1 query, none for no
    id: {user id: entries}, every given id included, [] for someone without a badge.
    """
    by_user = {user_id: [] for user_id in user_ids}
    rows = defaultdict(list)
    for row in _shown_rows().filter(user_id__in=list(by_user)):
        rows[row.user_id].append(row)
    for user_id, mine in rows.items():
        by_user[user_id] = _grouped(mine)
    return by_user


def _grouped(rows):
    """One person's badge rows as profile_badges() entries (see there)."""
    groups = {}
    for row in rows:
        partner = row.partner
        group = groups.setdefault(
            (row.code, row.discipline, row.partner_id),
            {
                "code": row.code,
                "tier": 0,
                "years": set(),
                "discipline": row.discipline or None,
                "partner": None
                if partner is None
                else {
                    "id": partner.id,
                    "first_name": partner.first_name,
                    "last_name": partner.last_name,
                    # select_related: no query, and no row reads as no photo.
                    "photo": small_photo_url(getattr(partner, "profile", None)),
                },
            },
        )
        group["tier"] = max(group["tier"], row.tier)
        group["years"].add(row.edition.year)

    def order(badge):
        partner = badge["partner"] or {"last_name": "", "first_name": "", "id": 0}
        return (
            CATALOGUE_ORDER.get(badge["code"], len(CATALOGUE_ORDER)),
            _sort_key(badge["discipline"] or ""),
            _sort_key(partner["last_name"]),
            _sort_key(partner["first_name"]),
            partner["id"],
        )

    return sorted(({**g, "years": sorted(g["years"])} for g in groups.values()), key=order)


SHOWCASE_SIZE = 5  # UserProfile.showcase repeats it as its size (test_showcase.py)


def valid_pins(codes, entries):
    """
    Whether `codes`, the `codes` of a PUT /me/showcase/ body (any JSON value), can be stored
    as a person's pins: a list of at most SHOWCASE_SIZE distinct catalogue codes, each earned
    (in the person's profile_badges() `entries`). [] is valid: back to the automatic
    showcase.
    """
    if not isinstance(codes, list) or len(codes) > SHOWCASE_SIZE:
        return False
    if not all(isinstance(code, str) for code in codes) or len(set(codes)) != len(codes):
        return False
    held = {entry["code"] for entry in entries}
    return all(code in CATALOGUE_ORDER and code in held for code in codes)


def showcase(entries, pins, holders):
    """
    The badges a person's profile shows (no query), from their profile_badges() `entries`,
    their stored `pins` (UserProfile.showcase) and the rarity counts of badge_stats() over
    the leaderboard's people (its `holders`): {"auto": bool, "badges": [{code, tier,
    discipline}]}, at most SHOWCASE_SIZE, in the order shown.

    - Pinned: the pins still earned, in the person's order. A pin stops showing once its
      badge is revoked or recomputed away, and none left means automatic.
    - Automatic: the rarest earned codes, fewest holders first (a code without a count has
      none), then the higher tier held, then catalogue order.
    - Each code is drawn from its entry with the highest tier, the first one among equals,
      as the front's badgeCollection picks a collection slot's medallion: the metal, the
      pips and specialist's discipline icon match the slot's. A partner is never shown.
    """
    medals = {}
    for entry in entries:
        best = medals.get(entry["code"])
        if best is None or entry["tier"] > best["tier"]:
            medals[entry["code"]] = entry
    codes = [code for code in dict.fromkeys(pins) if code in medals][:SHOWCASE_SIZE]
    auto = not codes
    if auto:
        codes = sorted(
            medals,
            key=lambda code: (
                holders.get(code, 0),
                -medals[code]["tier"],
                CATALOGUE_ORDER.get(code, len(CATALOGUE_ORDER)),
            ),
        )[:SHOWCASE_SIZE]
    return {
        "auto": auto,
        "badges": [
            {"code": code, "tier": medals[code]["tier"], "discipline": medals[code]["discipline"]}
            for code in codes
        ],
    }


# The five tiered codes (see VETERAN_TIERS, EVER_PRESENT_TIERS, NETWORKER_TIERS,
# SPECIALIST_TIERS and ALL_ROUNDER_TIERS above): badge_stats reports an at-least-k holder
# count for these codes only.
TIERED_CODES = frozenset({C.VETERAN, C.EVER_PRESENT, C.NETWORKER, C.SPECIALIST, C.ALL_ROUNDER})


def badge_stats(user_ids):
    """
    Rarity stats for the profile and the showcases (1 query, none for no id), over the given
    user ids (the leaderboard's people): how many hold each badge code (any tier, discipline,
    partner or year, each counted once) and, for the five tiered codes, how many hold at least
    each tier (the person's own highest tier of that code). Same filter as profile_badges:
    active rows of active editions only. `holders` only lists codes with at least one holder;
    `tiers` only lists the tiered codes with one. See the "Rarity" design spec.

    {"players": 47, "holders": {"champion": 12, "veteran": 20}, "tiers": {"veteran": [20, 6, 1]}}
    """
    rows = Badge.objects.filter(
        is_active=True, edition__is_active=True, user_id__in=user_ids
    ).values_list("code", "user_id", "tier")
    highest = {}
    for code, user_id, tier in rows:
        key = (code, user_id)
        if tier > highest.get(key, -1):
            highest[key] = tier
    holders = Counter()
    tiers = defaultdict(lambda: [0, 0, 0])
    for (code, _), tier in highest.items():
        holders[code] += 1
        if code in TIERED_CODES:
            for k in (1, 2, 3):
                if tier >= k:
                    tiers[code][k - 1] += 1
    return {
        "players": len(user_ids),
        "holders": dict(holders),
        "tiers": dict(tiers),
    }
