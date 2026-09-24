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
from datetime import datetime
from itertools import combinations

from django.db import transaction
from django.utils import timezone

from .models import Badge, BadgeRefresh, BlindtestGuess, Game
from .models.ResultTypes import ResultTypes
from .profiles import _load, _participations, _place, _record, _sort_key, paris_today

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
    """goat, alone-at-the-top, hall-of-fame-podium and hall-of-famer (once each), reign
    (once per streak), kingslayer and rocket (at every table earned). A table after an
    edition where no participation counts (nothing ranked yet) breaks every reign, as an
    unranked edition breaks a place streak: missing data never counts. It is the previous
    table unchanged, so it gives none of the other badges anyway."""
    reached = set()
    reign = Counter()
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
                    yield Earned(user_id, code, edition_id)
        for user_id in h.seats:
            on_top = counted and positions.get(user_id) == 1
            reign[user_id] = reign[user_id] + 1 if on_top else 0
            if reign[user_id] == 3:
                yield Earned(user_id, C.REIGN, edition_id)
        if previous is not None:
            for user_id in leaders:
                if previous.get(user_id) != 1:
                    yield Earned(user_id, C.KINGSLAYER, edition_id)
            climbs = {
                user_id: previous[user_id] - position
                for user_id, position in positions.items()
                if position is not None and previous.get(user_id) is not None
            }
            best = max(climbs.values(), default=0)
            if best >= 1:
                for user_id, climb in climbs.items():
                    if climb == best:
                        yield Earned(user_id, C.ROCKET, edition_id)
        previous = positions


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

SPECIALIST_TIERS = {2: 1, 3: 2, 4: 3}
ALL_ROUNDER_TIERS = ((3, 1), (5, 2), (8, 3))


@dataclass(frozen=True)
class DisciplineResult:
    """A team's result in one discipline of a sequence edition, with its standing's rank
    (0 when hidden or unscored)."""

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
    compute_standings already loaded: no query of its own.
    """
    results = {}
    for i, standing in enumerate(h.standings):
        results[i] = [
            DisciplineResult(
                team_id,
                discipline.discipline_id,
                discipline.discipline_name,
                discipline.result_type,
                discipline.points,
                discipline.standing.ranking,
            )
            for team_id, disciplines in standing.team_disciplines.items()
            for discipline in disciplines
        ]
    return results


def _disciplines(h):
    """specialist, all-rounder, decathlete, brains-and-brawn, clean-sweep, metronome,
    uncrowned, photo-finish, the gods and olympus."""
    if not h.sequence:
        return
    results = _discipline_results(h)
    for user_id, seats in h.seats.items():
        yield from _disciplines_of(h, results, user_id, seats)


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
        podiums.update(r.name for r in mine if 1 <= r.ranking <= 3)
        if not decathlete and len(podiums) >= 10:
            decathlete = True
            yield Earned(user_id, C.DECATHLETE, edition_id)

        kinds = {KINDS.get(name) for name in names}
        if MIND in kinds and PHYSICAL in kinds:
            yield Earned(user_id, C.BRAINS_AND_BRAWN, edition_id)
        if len(wins) >= 3:
            yield Earned(user_id, C.CLEAN_SWEEP, edition_id)
        ranked = {r.discipline_id for r in rows if r.ranking}
        on_podium = {r.discipline_id for r in mine if 1 <= r.ranking <= 3}
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
                if len(gods) == len(GODS):
                    yield Earned(user_id, C.OLYMPUS, edition_id)


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


GOLDEN_WHISTLE_TIERS = ((5, 1), (10, 2), (20, 3))


@dataclass(frozen=True)
class GameRow:
    """One game of a sequence edition, as the game badges read it."""

    discipline_name: str
    revealed: bool
    team1_id: int
    score1: int
    team2_id: int
    score2: int
    referees_id: int


@dataclass(frozen=True)
class GameFacts:
    """What one edition's games say about its teams."""

    records: dict  # team id -> {discipline name: (played, won, lost)}, revealed games only
    shutouts: frozenset
    steamrollers: dict  # team id -> discipline names of that team's biggest margin there
    refereed: dict  # team id -> games refereed by a team not playing them, revealed or not


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
        "team1_id", "score1", "team2_id", "score2", "referees_id",
    )
    games = defaultdict(list)
    for edition_id, *game in rows:
        games[index[edition_id]].append(GameRow(*game))
    return games


def _game_facts(games):
    """The GameFacts of one edition's games. A game counts as refereed only when the referee
    team is neither of the two playing: the schedulers leave a playing team in the slot as a
    placeholder (Swiss rounds put team1 there). Steamroller margins are judged discipline by
    discipline, so raw scores never compare across sports: a darts leg's 301-141 does not
    outweigh a rugby 13-0."""
    records = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    shutouts, refereed = set(), Counter()
    margins = defaultdict(list)  # discipline name -> [(margin, team id)], revealed wins only
    for game in games:
        if game.referees_id not in (game.team1_id, game.team2_id):
            refereed[game.referees_id] += 1
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
        refereed=dict(refereed),
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
    """unbeaten, perfect-run, shutout, steamroller, golden-whistle and perfect-pitch."""
    if not h.sequence:
        return
    games = _game_rows(h)
    pitch = _perfect_pitch(h)
    facts = [_game_facts(games.get(i, [])) for i in range(len(h.sequence))]
    for user_id, seats in h.seats.items():
        refereed = 0
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
            before = refereed
            refereed += fact.refereed.get(team_id, 0)
            for threshold, tier in GOLDEN_WHISTLE_TIERS:
                if before < threshold <= refereed:
                    yield Earned(user_id, C.GOLDEN_WHISTLE, edition_id, tier=tier)


RULES = (_places, _streaks, _career, _loyalty, _teammates, _hall_of_fame, _disciplines, _games)


def earned(today=None):
    """Every computed badge on `today` (a Paris date, default today), as a set of Earned."""
    h = history(today)
    found = set()
    for rule in RULES:
        found.update(rule(h))
    return found


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


def profile_badges(user_id):
    """
    The person's active badges of active editions for GET /profile/<id>/ (1 query), grouped
    by (code, discipline, partner) in catalogue order: [{code, tier, years, discipline,
    partner}], `tier` the highest, `years` sorted, names only for the partner.
    """
    groups = {}
    rows = Badge.objects.filter(
        user_id=user_id, is_active=True, edition__is_active=True
    ).select_related("edition", "partner")
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
