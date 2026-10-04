"""
Tests for olympic_warriors.badges: every computed badge rule, read through earned() on
small histories, and the progress toward the badges whose rule is a count, read through
compute(). Hand-ranked editions (Team.final_rank) make the place, streak, loyalty,
teammate and hall of fame histories quick to build; discipline and game rules use
revealed disciplines with results and games. Every test built on World also checks, as
it tears down, that the raw progress counters agree with the rules over its data.
"""

from collections import defaultdict
from datetime import date, timedelta
from datetime import time as dt_time
from functools import cache
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors import profiles
from olympic_warriors.badges import (
    ALL_ROUNDER_TIERS,
    EVER_PRESENT_TIERS,
    FAMILIES,
    GODS,
    KINDS,
    NETWORKER_TIERS,
    PROGRESS_TARGETS,
    SPECIALIST_TIERS,
    TIERED_CODES,
    VETERAN_TIERS,
    Progress,
    _counters,
    _badges_and_reigns,
    _progress,
    compute,
    earned,
    history,
)
from olympic_warriors.models import (
    Badge,
    Basketball,
    Blindtest,
    BlindtestGuess,
    BlindtestRound,
    Crossfit,
    Dance,
    Darts,
    Discipline,
    Dodgeball,
    Edition,
    Fair,
    Football,
    Frisbee,
    Game,
    GeneralCultureQuizz,
    Geoguessr,
    Handball,
    HideAndSeek,
    Orienteering,
    Petanque,
    Player,
    Relay,
    Rugby,
    Team,
    TeamResult,
    TeamSportRound,
    Volleyball,
)
from olympic_warriors.models.ResultTypes import ResultTypes
from olympic_warriors.profiles import _sort_key
from olympic_warriors.standings import compute_standings

C = Badge.Codes
TODAY = date(2031, 1, 1)
PLACE_CODES = (C.CHAMPION, C.RUNNER_UP, C.BRONZE, C.CHOCOLATE, C.WOODEN_SPOON)

# The 20 codes with progress, in catalogue order: the five tiered ones, the fourteen of
# PROGRESS_TARGETS, and argonaut, whose only row is out of reach.
PROGRESS_CODES = (
    C.BACK_TO_BACK,
    C.THREEPEAT,
    C.DYNASTY,
    C.LEGEND,
    C.PODIUM_REGULAR,
    C.FULL_SET,
    C.ETERNAL_SECOND,
    C.ON_THE_RISE,
    C.LUCKY_CHARM,
    C.VETERAN,
    C.ARGONAUT,
    C.EVER_PRESENT,
    C.COMRADES,
    C.NETWORKER,
    C.REIGN,
    C.SPECIALIST,
    C.ALL_ROUNDER,
    C.DECATHLETE,
    C.CLEAN_SWEEP,
    C.OLYMPUS,
)
# The codes whose row carries a best run.
STREAK_CODES = (
    C.EVER_PRESENT,
    C.BACK_TO_BACK,
    C.THREEPEAT,
    C.DYNASTY,
    C.PODIUM_REGULAR,
    C.ON_THE_RISE,
    C.REIGN,
)


def tier_of(tiers, count):
    """The highest tier `count` reaches in a tier table ({threshold: tier}, or its pairs), 0
    below the first threshold."""
    return max((tier for threshold, tier in dict(tiers).items() if count >= threshold), default=0)


class World:
    """
    Builds histories: finished editions whose teams are hand-ranked, and people on them.
    Tearing down, it checks that the raw progress counters agree with the rules on whatever
    the test built (assert_counters_agree).
    """

    def tearDown(self):
        try:
            self.assert_counters_agree()
        finally:
            super().tearDown()

    def assert_counters_agree(self):
        """
        The design spec's "The raw counters and the rules agree": replayed the day after each
        active edition's end in turn, every person's raw counters of that History against
        the badges its rules earn (agree), then the rows compute() would keep (rows_hold).
        An edition's standings depend on its data alone, not on the day, so the replay
        computes them once per edition rather than once per day.
        """
        ends = Edition.objects.filter(is_active=True).values_list("end_date", flat=True)
        with mock.patch.object(profiles, "compute_standings", cache(compute_standings)):
            for day in sorted({end + timedelta(days=1) for end in ends}):
                self.agree_on(day)

    def agree_on(self, day):
        """assert_counters_agree() on the History of `day`."""
        h = history(day)
        found, reigns = _badges_and_reigns(h)
        counters = _counters(h, reigns)
        self.assertEqual(set(counters), set(h.users), day)
        badges = defaultdict(list)
        for badge in found:
            badges[badge.user_id].append(badge)
        for user_id, counts in counters.items():
            self.agree(h, counts, badges[user_id], f"user {user_id} on {day}")
        self.rows_hold(h, counters, found, day)

    def agree(self, h, counts, badges, where):
        """One person's counters against their badges `badges`, L being the last edition of
        the sequence."""
        codes = {badge.code for badge in badges}
        last = h.sequence[-1].id if h.sequence else None
        at_last = {badge.code for badge in badges if badge.edition_id == last}

        def tier(code, discipline=""):
            return max(
                (b.tier for b in badges if b.code == code and b.discipline == discipline),
                default=0,
            )

        # Tiered: the counter's tier is the highest earned; ever-present's from its best run,
        # specialist's per discipline name.
        for code, tiers, count in (
            (C.VETERAN, VETERAN_TIERS, counts.played),
            (C.EVER_PRESENT, EVER_PRESENT_TIERS, counts.present_run[1]),
            (C.NETWORKER, NETWORKER_TIERS, counts.mates),
            (C.ALL_ROUNDER, ALL_ROUNDER_TIERS, counts.disciplines_won),
        ):
            self.assertEqual(tier_of(tiers, count), tier(code), f"{code}, {where}")
        names = set(counts.wins) | {b.discipline for b in badges if b.code == C.SPECIALIST}
        for name in names:
            won, _ = counts.wins.get(name, (0, None))
            self.assertEqual(
                tier_of(SPECIALIST_TIERS, won), tier(C.SPECIALIST, name), f"{name}, {where}"
            )

        # Counts that can jump: earned exactly when the counter reaches the target.
        for code, count in (
            (C.LEGEND, counts.titles),
            (C.FULL_SET, counts.places),
            (C.DECATHLETE, counts.podiums),
            (C.OLYMPUS, counts.gods),
        ):
            self.assertEqual(count >= PROGRESS_TARGETS[code], code in codes, f"{code}, {where}")

        # Streaks: the current run is at the target exactly when the badge was earned at L,
        # and the best run reached it exactly when it was ever earned.
        for code, (current, best) in (
            (C.BACK_TO_BACK, counts.title_run),
            (C.THREEPEAT, counts.title_run),
            (C.DYNASTY, counts.title_run),
            (C.PODIUM_REGULAR, counts.podium_run),
            (C.ON_THE_RISE, counts.rise_run),
            (C.REIGN, counts.reign_run),
        ):
            target = PROGRESS_TARGETS[code]
            self.assertEqual(current == target, code in at_last, f"{code}, {where}")
            self.assertEqual(best >= target, code in codes, f"{code}, {where}")
            self.assertLessEqual(current, best, f"{code}, {where}")

        # Per key: comrades with a partner at 3 editions shared, clean-sweep at an edition of
        # 3 discipline wins.
        partners = {b.partner_id for b in badges if b.code == C.COMRADES}
        for partner in set(counts.together) | partners:
            shared, _ = counts.together.get(partner, (0, None))
            self.assertEqual(
                shared >= PROGRESS_TARGETS[C.COMRADES], partner in partners, f"{partner}, {where}"
            )
        swept = {b.edition_id for b in badges if b.code == C.CLEAN_SWEEP}
        for i, edition in enumerate(h.sequence):
            self.assertEqual(
                counts.sweeps.get(i, 0) >= PROGRESS_TARGETS[C.CLEAN_SWEEP],
                edition.id in swept,
                f"{edition.year}, {where}",
            )

        # The two that can close: out of reach means not earned, reachable and not earned
        # means below the target, earned means the counter reached it.
        for code, count, closed in (
            (C.ETERNAL_SECOND, counts.seconds, counts.seconds_closed),
            (C.LUCKY_CHARM, counts.lucky, counts.lucky_closed),
        ):
            if closed:
                self.assertNotIn(code, codes, where)
            elif code in codes:
                self.assertGreaterEqual(count, PROGRESS_TARGETS[code], f"{code}, {where}")
            else:
                self.assertLess(count, PROGRESS_TARGETS[code], f"{code}, {where}")
        # eternal-second closes exactly at an edition won, unless already earned.
        self.assertEqual(
            counts.seconds_closed, counts.titles > 0 and C.ETERNAL_SECOND not in codes, where
        )

        # Argonaut: out of reach exactly when the first edition is over and it is not earned.
        self.assertEqual(
            counts.argonaut_closed,
            h.first_edition_id is not None and C.ARGONAUT not in codes,
            where,
        )

    def rows_hold(self, h, counters, found, where):
        """
        The rows compute() keeps from these counters are exactly the expected ones
        (expected_rows): one per person and code, each with the value, best run, reach,
        discipline, partner and year its counters give; no value exactly when out of reach,
        a best run on streaks only, and a value of 0 naming nothing.
        """
        actual = {}
        for row in _progress(h, counters, found):
            key, name = (row.user_id, row.code), f"user {row.user_id}, {row.code}, {where}"
            self.assertNotIn(key, actual, f"two rows for {name}")
            self.assertEqual(row.value is None, not row.reachable, name)
            self.assertEqual(row.best is None, row.code not in STREAK_CODES, name)
            if not row.value:
                self.assertEqual((row.discipline, row.partner_id, row.year), ("", None, None), name)
            actual[key] = (
                row.value, row.best, row.reachable, row.discipline, row.partner_id, row.year
            )
        expected = self.expected_rows(h, counters, found)
        for key in sorted(set(actual) | set(expected)):
            user_id, code = key
            self.assertEqual(actual.get(key), expected.get(key), f"user {user_id}, {code}, {where}")

    @staticmethod
    def expected_rows(h, counters, found):
        """
        The rows the design spec's "Which rows exist" and its counter bullets ask for, from
        each person's counters: {(user id, code): (value, best, reachable, discipline,
        partner id, year)}. Every tiered code; a non-tiered one while not earned (argonaut
        only once out of reach); comrades unless earned with no partner below the target.
        """
        held = {(badge.user_id, badge.code) for badge in found}
        top, users = max(SPECIALIST_TIERS), h.users
        expected = {}
        for user_id, c in counters.items():
            # Specialist: the most wins below the top tier first, then the latest win, then
            # the name; with every name at the top tier, the most wins first.
            names = sorted(
                (won >= top, -won, -latest, _sort_key(name), name)
                for name, (won, latest) in c.wins.items()
            )
            specialist = (c.wins[names[0][-1]][0], names[0][-1]) if names else (0, "")
            tiered = {
                C.VETERAN: (c.played, None, ""),
                C.EVER_PRESENT: (*c.present_run, ""),
                C.NETWORKER: (c.mates, None, ""),
                C.SPECIALIST: (specialist[0], None, specialist[1]),
                C.ALL_ROUNDER: (c.disciplines_won, None, ""),
            }
            for code, (value, best, discipline) in tiered.items():
                expected[(user_id, code)] = (value, best, True, discipline, None, None)

            until_earned = {
                C.LEGEND: (c.titles, None),
                C.FULL_SET: (c.places, None),
                C.DECATHLETE: (c.podiums, None),
                C.OLYMPUS: (c.gods, None),
                C.BACK_TO_BACK: c.title_run,
                C.THREEPEAT: c.title_run,
                C.DYNASTY: c.title_run,
                C.PODIUM_REGULAR: c.podium_run,
                C.ON_THE_RISE: c.rise_run,
                C.REIGN: c.reign_run,
                C.ETERNAL_SECOND: (None if c.seconds_closed else c.seconds, None),
                C.LUCKY_CHARM: (None if c.lucky_closed else c.lucky, None),
            }
            if c.argonaut_closed:
                until_earned[C.ARGONAUT] = (None, None)
            for code, (value, best) in until_earned.items():
                if (user_id, code) not in held:
                    expected[(user_id, code)] = (value, best, value is not None, "", None, None)
            if (user_id, C.CLEAN_SWEEP) not in held:
                won, i = max(((won, i) for i, won in c.sweeps.items()), default=(0, None))
                year = None if i is None else h.sequence[i].year
                expected[(user_id, C.CLEAN_SWEEP)] = (won, None, True, "", None, year)

            # Comrades: the most editions together below the target, then the latest, then
            # the last name, first name and id.
            below = sorted(
                (-shared, -latest, _sort_key(users[p].last_name), _sort_key(users[p].first_name), p)
                for p, (shared, latest) in c.together.items()
                if shared < PROGRESS_TARGETS[C.COMRADES]
            )
            if below:
                partner = below[0][-1]
                shared, _ = c.together[partner]
                expected[(user_id, C.COMRADES)] = (shared, None, True, "", partner, None)
            elif (user_id, C.COMRADES) not in held:
                expected[(user_id, C.COMRADES)] = (0, None, True, "", None, None)
        return expected

    def edition(
        self, year, size=4, host="Paris", ranks=None, finished=True, ranked=True, spectator=True
    ):
        """
        An edition held on Sept 21-22 of `year` (or ending after TODAY when not `finished`)
        with `size` teams T<year>-1.. ranked 1..size, or `ranks` (None for a team without a
        final_rank). With ranked=False the teams get no final_rank at all.

        With `spectator` (the default) a teamless player sits in the edition, so it has a
        roster and stays in the sequence even when a test's people all miss it: a missed
        edition must break streaks. A teamless player has no place, no teammate and no
        position, so it earns only loyalty badges. Pass spectator=False for an edition
        without any roster, which the sequence skips.
        Returns (edition, [teams]).
        """
        end = date(year, 9, 22) if finished else date(TODAY.year + 1, 1, 1)
        edition = Edition.objects.create(
            year=year, host=host, start_date=date(year, 9, 21), end_date=end
        )
        ranks = ranks if ranks is not None else list(range(1, size + 1))
        teams = [
            Team.objects.create(
                name=f"T{year}-{n}", edition=edition, final_rank=rank if ranked else None
            )
            for n, rank in enumerate(ranks, start=1)
        ]
        if spectator:
            self.seat(self.person(f"Spectator{year}"), edition)
        return edition, teams

    @staticmethod
    def person(name):
        return User.objects.create(username=f"u-{name}", first_name=name, last_name="Test")

    @staticmethod
    def seat(user, edition, team=None):
        return Player.objects.create(user=user, edition=edition, team=team, rating=5)

    def play(self, user, places):
        """
        Seat `user` in consecutive editions from 2021, at the given ranks (None: missed).
        A missing edition is created with 6 teams and the default spectator, so a None is a
        real miss; an edition already built for that year is reused.
        """
        for year, rank in zip(range(2021, 2021 + len(places)), places):
            edition = Edition.objects.filter(year=year).first()
            if edition is None:
                edition, _ = self.edition(year, size=6)
            if rank is not None:
                team = Team.objects.get(edition=edition, final_rank=rank)
                self.seat(user, edition, team)


def badges_of(user, today=TODAY):
    """Sorted (code, year, tier, discipline, partner id) of the user's computed badges."""
    years = dict(Edition.objects.values_list("id", "year"))
    return sorted(
        (e.code, years[e.edition_id], e.tier, e.discipline, e.partner_id)
        for e in earned(today)
        if e.user_id == user.id
    )


def years_of(user, code, today=TODAY):
    """The years at which the user earned `code`, sorted."""
    return sorted(year for c, year, *_ in badges_of(user, today) if c == code)


def places_of(user, today=TODAY):
    """The user's place badges as sorted (code, year), whatever the other rules give."""
    return sorted((c, year) for c, year, *_ in badges_of(user, today) if c in PLACE_CODES)


def progress_of(user, today=TODAY):
    """The user's progress rows on `today`, as {code: Progress}."""
    return {row.code: row for row in compute(today)[1] if row.user_id == user.id}


def counters_of(user, today=TODAY):
    """The user's raw progress counters on `today`."""
    h = history(today)
    return _counters(h, _badges_and_reigns(h)[1])[user.id]


class TestHistory(World, TestCase):
    def test_the_sequence_is_finished_editions_with_players_by_year(self):
        e2023, _ = self.edition(2023, spectator=False)  # finished, no roster: left out
        e2024, t2024 = self.edition(2024)
        e2025, t2025 = self.edition(2025)
        e2026, t2026 = self.edition(2026, finished=False)  # running: left out
        ana = self.person("Ana")
        self.seat(ana, e2025, t2025[0])
        self.seat(ana, e2024, t2024[1])
        self.seat(ana, e2026, t2026[0])

        h = history(TODAY)

        self.assertEqual([e.year for e in h.sequence], [2024, 2025])
        self.assertEqual({i: seat.rank for i, seat in h.seats[ana.id].items()}, {0: 2, 1: 1})
        self.assertEqual(h.first_edition_id, e2023.id)


class TestPlaces(World, TestCase):
    def setUp(self):
        self.e2024, self.teams = self.edition(2024, size=5)
        self.people = [self.person(n) for n in ("Ana", "Bob", "Chloé", "Dan", "Eve")]
        for user, team in zip(self.people, self.teams):
            self.seat(user, self.e2024, team)

    def test_first_second_third_fourth_and_last(self):
        ana, bob, chloe, dan, eve = self.people
        self.assertEqual(years_of(ana, C.CHAMPION), [2024])
        self.assertEqual(years_of(bob, C.RUNNER_UP), [2024])
        self.assertEqual(years_of(chloe, C.BRONZE), [2024])
        self.assertEqual(years_of(dan, C.CHOCOLATE), [2024])
        self.assertEqual(years_of(eve, C.WOODEN_SPOON), [2024])
        self.assertEqual(years_of(dan, C.WOODEN_SPOON), [])

    def test_one_badge_per_edition(self):
        ana = self.people[0]
        e2026, t2026 = self.edition(2026)
        self.seat(ana, e2026, t2026[0])

        self.assertEqual(years_of(ana, C.CHAMPION), [2024, 2026])

    def test_chocolate_needs_five_teams(self):
        # 4 teams, and a rank 4 that is not the last place (5 is): only the size refuses it.
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 4, 5])
        gus = self.person("Gus")
        self.seat(gus, e2025, t2025[2])

        self.assertEqual(places_of(gus), [])

    def test_chocolate_is_never_the_last_place(self):
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 3, 4, 4])
        gus, hugo = self.person("Gus"), self.person("Hugo")
        self.seat(gus, e2025, t2025[3])
        self.seat(hugo, e2025, t2025[4])

        self.assertEqual(places_of(gus), [(C.WOODEN_SPOON, 2025)])
        self.assertEqual(places_of(hugo), [(C.WOODEN_SPOON, 2025)])

    def test_the_spoon_needs_four_teams(self):
        # 3 teams, the worst ranked below the podium: only the size refuses the spoon.
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 4])
        gus = self.person("Gus")
        self.seat(gus, e2025, t2025[2])

        self.assertEqual(places_of(gus), [])

    def test_the_spoon_needs_a_complete_ranking(self):
        # The worst ranked team is below the podium, so only the missing rank refuses the
        # spoon. Without a last place, the 4th of 5 teams is a chocolate medal.
        e2026, t2026 = self.edition(2026, ranks=[1, 2, 3, 4, None])
        hugo = self.person("Hugo")
        self.seat(hugo, e2026, t2026[3])

        self.assertEqual(years_of(hugo, C.WOODEN_SPOON), [])
        self.assertEqual(places_of(hugo), [(C.CHOCOLATE, 2026)])

    def test_no_team_no_place(self):
        gus = self.person("Gus")
        self.seat(gus, self.e2024)

        self.assertEqual(places_of(gus), [])

    def test_unfinished_editions_give_nothing(self):
        e2030, t2030 = self.edition(2030, finished=False)
        gus = self.person("Gus")
        self.seat(gus, e2030, t2030[0])

        self.assertEqual(years_of(gus, C.CHAMPION), [])

    def test_a_tied_last_place_on_the_podium_is_not_last(self):
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 3, 3])
        gus, hugo = self.person("Gus"), self.person("Hugo")
        self.seat(gus, e2025, t2025[2])
        self.seat(hugo, e2025, t2025[3])

        self.assertEqual(places_of(gus), [(C.BRONZE, 2025)])
        self.assertEqual(places_of(hugo), [(C.BRONZE, 2025)])

    def computed(self, year, reveal):
        """
        A 4-team edition without final_rank, ranked from one Relay scored 30/20/10/0 in team
        order (revealed or not), with one person per team. Returns the four people.
        """
        edition, teams = self.edition(year, ranked=False)
        relay = Relay.objects.create(edition=edition, reveal_score=reveal)
        people = []
        for n, (team, points) in enumerate(zip(teams, (30, 20, 10, 0)), start=1):
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)
            person = self.person(f"P{year}-{n}")
            self.seat(person, edition, team)
            people.append(person)
        return people

    def test_a_computed_edition_gives_places(self):
        first, second, third, last = self.computed(2025, reveal=True)

        self.assertEqual(places_of(first), [(C.CHAMPION, 2025)])
        self.assertEqual(places_of(second), [(C.RUNNER_UP, 2025)])
        self.assertEqual(places_of(third), [(C.BRONZE, 2025)])
        self.assertEqual(places_of(last), [(C.WOODEN_SPOON, 2025)])

    def test_a_computed_edition_with_nothing_revealed_gives_no_place(self):
        # Every team would tie 1st on nothing: the edition gives no rank at all.
        people = self.computed(2025, reveal=False)

        self.assertEqual([places_of(person) for person in people], [[], [], [], []])

    def test_a_one_team_edition_gives_no_place(self):
        # A participation counts only in an edition of at least 2 teams.
        e2025, t2025 = self.edition(2025, size=1)
        gus = self.person("Gus")
        self.seat(gus, e2025, t2025[0])

        self.assertEqual(places_of(gus), [])


class TestStreaks(World, TestCase):
    def test_a_title_streak_of_four_earns_each_streak_badge_once(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1, 1, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [2022])
        self.assertEqual(years_of(ana, C.THREEPEAT), [2023])
        self.assertEqual(years_of(ana, C.DYNASTY), [2024])

    def test_later_streaks_earn_again(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 2, 1, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [2022, 2025])

    def test_every_later_streak_earns_each_badge_again(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1, 1, 2, 1, 1, 1, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [2022, 2027])
        self.assertEqual(years_of(ana, C.THREEPEAT), [2023, 2028])
        self.assertEqual(years_of(ana, C.DYNASTY), [2024, 2029])

    def test_a_year_without_an_edition_is_skipped(self):
        ana = self.person("Ana")
        for year in (2021, 2022, 2024):
            edition, teams = self.edition(year)
            self.seat(ana, edition, teams[0])

        self.assertEqual(years_of(ana, C.THREEPEAT), [2024])

    def test_a_missed_edition_breaks_a_streak(self):
        ana = self.person("Ana")
        self.play(ana, [1, None, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [])

    def test_an_unranked_edition_breaks_a_place_streak(self):
        ana = self.person("Ana")
        e2022, t2022 = self.edition(2022, ranks=[1, 2, None])
        self.play(ana, [1, None, 1])
        self.seat(ana, e2022, t2022[2])  # played 2022, for the team without a rank

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [])

    def test_an_edition_without_a_roster_does_not_break_a_streak(self):
        ana = self.person("Ana")
        self.edition(2022, spectator=False)  # nobody played it: left out of the sequence
        self.play(ana, [1, None, 1])

        self.assertEqual(years_of(ana, C.BACK_TO_BACK), [2023])

    def test_podium_regular_is_three_podiums_in_a_row(self):
        ana = self.person("Ana")
        self.play(ana, [3, 2, 1])

        self.assertEqual(years_of(ana, C.PODIUM_REGULAR), [2023])

    def test_podium_regular_once_per_streak(self):
        ana = self.person("Ana")
        self.play(ana, [3, 2, 1, 2])

        self.assertEqual(years_of(ana, C.PODIUM_REGULAR), [2023])

    def test_podium_regular_after_a_broken_run(self):
        ana = self.person("Ana")
        self.play(ana, [3, 2, 4, 1, 1, 2])

        self.assertEqual(years_of(ana, C.PODIUM_REGULAR), [2026])


class TestCareer(World, TestCase):
    def test_phoenix_after_an_edition_without_a_title(self):
        ana = self.person("Ana")
        self.play(ana, [1, 2, 1])

        self.assertEqual(years_of(ana, C.PHOENIX), [2023])

    def test_phoenix_after_a_missed_edition(self):
        ana = self.person("Ana")
        self.play(ana, [1, None, 1])

        self.assertEqual(years_of(ana, C.PHOENIX), [2023])

    def test_no_phoenix_for_back_to_back_titles(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1])

        self.assertEqual(years_of(ana, C.PHOENIX), [])

    def test_no_phoenix_without_an_earlier_title(self):
        ana = self.person("Ana")
        self.play(ana, [2, 1])

        self.assertEqual(years_of(ana, C.PHOENIX), [])

    def test_phoenix_at_every_return(self):
        ana = self.person("Ana")
        self.play(ana, [1, 3, 1, 4, 1])

        self.assertEqual(years_of(ana, C.PHOENIX), [2023, 2025])

    def test_legend_at_the_third_title(self):
        ana = self.person("Ana")
        self.play(ana, [1, 3, 1, 1])

        self.assertEqual(years_of(ana, C.LEGEND), [2024])

    def test_no_legend_with_two_titles(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1])

        self.assertEqual(years_of(ana, C.LEGEND), [])

    def test_legend_once(self):
        ana = self.person("Ana")
        self.play(ana, [1, 3, 1, 1, 1])

        self.assertEqual(years_of(ana, C.LEGEND), [2024])

    def test_full_set(self):
        ana = self.person("Ana")
        self.play(ana, [3, 1, 2])

        self.assertEqual(years_of(ana, C.FULL_SET), [2023])

    def test_no_full_set_without_a_third_place(self):
        ana = self.person("Ana")
        self.play(ana, [1, 2])

        self.assertEqual(years_of(ana, C.FULL_SET), [])

    def test_full_set_once(self):
        ana = self.person("Ana")
        self.play(ana, [3, 1, 2, 1])

        self.assertEqual(years_of(ana, C.FULL_SET), [2023])

    def test_eternal_second(self):
        ana = self.person("Ana")
        self.play(ana, [2, 4, 2])

        self.assertEqual(years_of(ana, C.ETERNAL_SECOND), [2023])

    def test_no_eternal_second_after_a_title(self):
        ana = self.person("Ana")
        self.play(ana, [1, 2, 2])

        self.assertEqual(years_of(ana, C.ETERNAL_SECOND), [])

    def test_eternal_second_stays_after_a_later_title(self):
        ana = self.person("Ana")
        self.play(ana, [2, 2, 1])

        self.assertEqual(years_of(ana, C.ETERNAL_SECOND), [2022])

    def test_janus_once(self):
        ana = self.person("Ana")
        self.play(ana, [1, 6, 1, 6])

        self.assertEqual(years_of(ana, C.JANUS), [2022])

    def test_no_janus_without_a_title(self):
        ana = self.person("Ana")
        self.play(ana, [2, 6])

        self.assertEqual(years_of(ana, C.JANUS), [])

    def test_janus_whatever_the_order(self):
        ana = self.person("Ana")
        self.play(ana, [6, 1])

        self.assertEqual(years_of(ana, C.JANUS), [2022])

    def test_no_janus_without_the_last_place(self):
        ana = self.person("Ana")
        self.play(ana, [1, 5])  # 5th of 6 is not last

        self.assertEqual(years_of(ana, C.JANUS), [])

    def test_comeback_from_last_to_the_podium(self):
        ana = self.person("Ana")
        self.play(ana, [6, 3])

        self.assertEqual(years_of(ana, C.COMEBACK), [2022])

    def test_no_comeback_across_a_missed_edition(self):
        ana = self.person("Ana")
        self.play(ana, [6, None, 1])

        self.assertEqual(years_of(ana, C.COMEBACK), [])

    def test_no_comeback_from_above_the_last_place(self):
        ana = self.person("Ana")
        self.play(ana, [5, 3])  # 5th of 6 is not last

        self.assertEqual(years_of(ana, C.COMEBACK), [])

    def test_no_comeback_off_the_podium(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4])

        self.assertEqual(years_of(ana, C.COMEBACK), [])

    def test_comeback_at_every_return(self):
        ana = self.person("Ana")
        self.play(ana, [6, 3, 6, 2])

        self.assertEqual(years_of(ana, C.COMEBACK), [2022, 2024])

    def test_on_the_rise_is_two_climbs(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4, 2])

        self.assertEqual(years_of(ana, C.ON_THE_RISE), [2023])

    def test_no_on_the_rise_with_one_climb(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4])

        self.assertEqual(years_of(ana, C.ON_THE_RISE), [])

    def test_on_the_rise_once_per_streak(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4, 2, 1])

        self.assertEqual(years_of(ana, C.ON_THE_RISE), [2023])

    def test_on_the_rise_restarts_at_a_repeated_rank(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4, 4, 3, 2])

        self.assertEqual(years_of(ana, C.ON_THE_RISE), [2025])

    def test_on_the_rise_compares_relative_ranks(self):
        ana = self.person("Ana")
        # 3rd of 5 (0.5), then 3rd of 9 (0.25), then 1st (0).
        for year, size, rank in ((2021, 5, 3), (2022, 9, 3), (2023, 4, 1)):
            edition, teams = self.edition(year, size=size)
            self.seat(ana, edition, teams[rank - 1])

        self.assertEqual(years_of(ana, C.ON_THE_RISE), [2023])

    def test_icarus_falls_to_the_bottom_half(self):
        ana = self.person("Ana")
        self.play(ana, [1, 4])

        self.assertEqual(years_of(ana, C.ICARUS), [2022])

    def test_no_icarus_in_the_top_half(self):
        ana = self.person("Ana")
        self.play(ana, [1, 3])

        self.assertEqual(years_of(ana, C.ICARUS), [])

    def test_no_icarus_without_a_title(self):
        ana = self.person("Ana")
        self.play(ana, [2, 4])

        self.assertEqual(years_of(ana, C.ICARUS), [])

    def test_no_icarus_across_a_missed_edition(self):
        ana = self.person("Ana")
        self.play(ana, [1, None, 4])

        self.assertEqual(years_of(ana, C.ICARUS), [])

    def test_lucky_charm(self):
        ana = self.person("Ana")
        self.play(ana, [2, 3, 1])

        self.assertEqual(years_of(ana, C.LUCKY_CHARM), [2023])

    def test_no_lucky_charm_off_the_podium(self):
        ana = self.person("Ana")
        self.play(ana, [2, 4, 1])

        self.assertEqual(years_of(ana, C.LUCKY_CHARM), [])

    def test_lucky_charm_stays_after_a_bad_edition(self):
        ana = self.person("Ana")
        self.play(ana, [2, 3, 1, 6])

        self.assertEqual(years_of(ana, C.LUCKY_CHARM), [2023])

    def test_lucky_charm_reads_counted_participations(self):
        ana = self.person("Ana")
        self.play(ana, [2, 3, None, 1])
        self.seat(ana, Edition.objects.get(year=2023))  # played 2023, without a team

        self.assertEqual(years_of(ana, C.LUCKY_CHARM), [2024])


LOYALTY_CODES = (
    C.ROOKIE,
    C.VETERAN,
    C.ARGONAUT,
    C.EVER_PRESENT,
    C.HOMECOMING,
)


def tiers_of(user, code, today=TODAY):
    """The (year, tier) pairs at which the user earned `code`, sorted."""
    return sorted((year, tier) for c, year, tier, *_ in badges_of(user, today) if c == code)


class TestLoyalty(World, TestCase):
    def test_rookie_at_the_first_finished_edition_played(self):
        ana = self.person("Ana")
        self.play(ana, [None, 2, 3])

        self.assertEqual(years_of(ana, C.ROOKIE), [2022])

    def test_a_running_edition_gives_no_loyalty_badge(self):
        ana = self.person("Ana")
        e2030, t2030 = self.edition(2030, finished=False)
        self.seat(ana, e2030, t2030[0])

        self.assertEqual([b for b in badges_of(ana) if b[0] in LOYALTY_CODES], [])

    def test_veteran_tiers(self):
        ana = self.person("Ana")
        self.play(ana, [4] * 10)

        self.assertEqual(tiers_of(ana, C.VETERAN), [(2023, 1), (2025, 2), (2030, 3)])

    def test_veteran_editions_need_not_be_consecutive(self):
        ana = self.person("Ana")
        self.play(ana, [2, None, 2, None, 2])

        self.assertEqual(tiers_of(ana, C.VETERAN), [(2025, 1)])

    def test_argonaut_for_playing_the_first_finished_edition(self):
        ana = self.person("Ana")
        self.play(ana, [3, 3])

        self.assertEqual(years_of(ana, C.ARGONAUT), [2021])

    def test_no_argonaut_when_the_first_edition_has_no_roster(self):
        ana = self.person("Ana")
        self.edition(2020, spectator=False)
        self.play(ana, [3])

        self.assertEqual([e for e in earned(TODAY) if e.code == C.ARGONAUT], [])

    def test_no_argonaut_for_a_start_in_the_second_edition(self):
        ana = self.person("Ana")
        self.play(ana, [None, 3])

        self.assertEqual(years_of(ana, C.ARGONAUT), [])
        spectator = User.objects.get(username="u-Spectator2021")
        self.assertEqual(years_of(spectator, C.ARGONAUT), [2021])

    def test_ever_present_tiers(self):
        ana = self.person("Ana")
        self.play(ana, [5] * 8)

        self.assertEqual(tiers_of(ana, C.EVER_PRESENT), [(2024, 1), (2026, 2), (2028, 3)])

    def test_a_new_run_after_a_break_earns_no_tier_again(self):
        ana = self.person("Ana")
        self.play(ana, [5, 5, 5, 5, None, 5, 5, 5, 5])

        self.assertEqual(tiers_of(ana, C.EVER_PRESENT), [(2024, 1)])

    def test_playing_without_a_team_or_a_rank_keeps_the_run(self):
        ana = self.person("Ana")
        e2022, _ = self.edition(2022)
        e2023, t2023 = self.edition(2023, ranks=[1, 2, 3, None])
        self.play(ana, [2, None, None, 2])
        self.seat(ana, e2022)  # no team
        self.seat(ana, e2023, t2023[3])  # a team without a rank

        self.assertEqual(tiers_of(ana, C.EVER_PRESENT), [(2024, 1)])

    def test_homecoming_after_missing_two_editions(self):
        ana = self.person("Ana")
        self.play(ana, [3, None, None, 3])

        self.assertEqual(years_of(ana, C.HOMECOMING), [2024])

    def test_no_homecoming_after_missing_one_edition(self):
        ana = self.person("Ana")
        self.play(ana, [3, None, 3])

        self.assertEqual(years_of(ana, C.HOMECOMING), [])

    def test_homecoming_at_each_return(self):
        ana = self.person("Ana")
        self.play(ana, [3, None, None, 3, None, None, 3])

        self.assertEqual(years_of(ana, C.HOMECOMING), [2024, 2027])

    def test_a_first_edition_is_not_a_homecoming(self):
        ana = self.person("Ana")
        self.play(ana, [None, None, None, 3])

        self.assertEqual(years_of(ana, C.HOMECOMING), [])


def comrades_of(user, today=TODAY):
    """The (year, partner id) of the user's comrades badges, sorted."""
    return sorted(
        (year, partner) for c, year, _, _, partner in badges_of(user, today) if c == C.COMRADES
    )


class TestTeammates(World, TestCase):
    def setUp(self):
        self.ana, self.bob = self.person("Ana"), self.person("Bob")

    def share(self, years, same=True):
        """Ana and Bob in each of `years`, on the same team or on two different ones."""
        for year in years:
            edition, teams = self.edition(year)
            self.seat(self.ana, edition, teams[0])
            self.seat(self.bob, edition, teams[0] if same else teams[1])

    def meet(self, year, mates):
        """Ana and `mates` on the same team in a new edition of `year`."""
        edition, teams = self.edition(year)
        for user in (self.ana, *mates):
            self.seat(user, edition, teams[0])

    def test_comrades_after_three_editions_together(self):
        self.share([2021])
        self.share([2022], same=False)
        self.share([2023, 2024])

        self.assertEqual(comrades_of(self.ana), [(2024, self.bob.id)])
        self.assertEqual(comrades_of(self.bob), [(2024, self.ana.id)])

    def test_two_editions_together_give_nothing(self):
        self.share([2021, 2022])

        self.assertEqual(comrades_of(self.ana), [])
        self.assertEqual(comrades_of(self.bob), [])

    def test_the_same_editions_on_different_teams_give_nothing(self):
        self.share([2021, 2022, 2023], same=False)

        self.assertEqual(comrades_of(self.ana), [])
        self.assertEqual(comrades_of(self.bob), [])

    def test_a_fourth_edition_together_earns_nothing_more(self):
        self.share([2021, 2022, 2023, 2024])

        self.assertEqual(comrades_of(self.ana), [(2023, self.bob.id)])
        self.assertEqual(comrades_of(self.bob), [(2023, self.ana.id)])

    def test_comrades_with_each_teammate(self):
        chloe = self.person("Chloé")
        for year in (2021, 2022, 2023):
            self.meet(year, [self.bob, chloe])

        ana, bob = self.ana.id, self.bob.id
        self.assertEqual(comrades_of(self.ana), [(2023, bob), (2023, chloe.id)])
        self.assertEqual(comrades_of(self.bob), [(2023, ana), (2023, chloe.id)])
        self.assertEqual(comrades_of(chloe), [(2023, ana), (2023, bob)])

    def test_no_comrades_without_a_team(self):
        uma, vic = self.person("Uma"), self.person("Vic")
        for year in (2021, 2022, 2023):
            edition, _ = self.edition(year)
            self.seat(uma, edition)
            self.seat(vic, edition)

        self.assertEqual(comrades_of(uma), [])
        self.assertEqual(comrades_of(vic), [])

    def test_networker_at_five_teammates(self):
        self.meet(2021, [self.person(f"Mate{n}") for n in range(3)])
        self.meet(2022, [self.person(f"Mate2-{n}") for n in range(2)])  # 5th teammate here

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2022, 1)])

    def test_networker_tiers_at_ten_and_twenty(self):
        self.meet(2021, [self.person(f"Mate21-{n}") for n in range(5)])
        self.meet(2022, [self.person(f"Mate22-{n}") for n in range(5)])  # 10th teammate here
        self.meet(2023, [self.person(f"Mate23-{n}") for n in range(10)])  # 20th teammate here

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2021, 1), (2022, 2), (2023, 3)])

    def test_two_networker_tiers_in_one_edition(self):
        self.meet(2021, [self.person(f"Mate{n}") for n in range(11)])  # 11 teammates

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2021, 1), (2021, 2)])

    def test_networker_when_the_threshold_is_passed_not_reached(self):
        self.meet(2021, [self.person(f"Mate{n}") for n in range(4)])
        self.meet(2022, [self.person(f"Mate2-{n}") for n in range(3)])  # 7 teammates: 5 passed, never reached

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2022, 1)])

    def test_meeting_the_same_people_again_adds_nothing(self):
        mates = [self.person(f"Mate{n}") for n in range(4)]
        self.meet(2021, mates)
        self.meet(2022, mates)
        self.meet(2023, [self.person(f"Mate2-{n}") for n in range(3)])  # 7 teammates: 5 crossed here

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2023, 1)])


FAME_CODES = (
    C.GOAT,
    C.ALONE_AT_THE_TOP,
    C.HALL_OF_FAME_PODIUM,
    C.HALL_OF_FAMER,
    C.REIGN,
    C.KINGSLAYER,
    C.ROCKET,
)


class TestHallOfFame(World, TestCase):
    """
    The all-time tables follow the /players rules: people rank like a medal table on their
    places, identical places share a position, and the teamless spectators have none.
    """

    def test_the_first_edition_gives_goat_alone(self):
        # The table after one counted edition is only that edition's ranking: goat for its
        # leader, none of the other hall of fame badges.
        ana = self.person("Ana")
        self.play(ana, [1, None])

        self.assertEqual([b[:2] for b in badges_of(ana) if b[0] in FAME_CODES], [(C.GOAT, 2021)])

    def test_goat_from_the_first_edition_and_the_next_leader(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 2])  # places 1, 2: 1st
        self.play(bob, [2, 1])  # places 2, 1: 1st too, shared

        self.assertEqual(years_of(ana, C.GOAT), [2021])
        self.assertEqual(years_of(bob, C.GOAT), [2022])

    def test_goat_for_a_later_leader(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 2])
        self.play(bob, [2, 1])
        self.play(bob, [2, 1, 1])

        self.assertEqual(years_of(bob, C.GOAT), [2022])

    def test_goat_once_even_when_shared(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1])
        self.play(bob, [1, 1, 1])  # the same team: the same places

        self.assertEqual(years_of(ana, C.GOAT), [2021])
        self.assertEqual(years_of(bob, C.GOAT), [2021])
        self.assertEqual(years_of(ana, C.ALONE_AT_THE_TOP), [])
        self.assertEqual(years_of(bob, C.ALONE_AT_THE_TOP), [])

    def test_alone_at_the_top_needs_the_first_place_alone(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1])
        self.play(bob, [1, 1, 2])  # teammates in 2021 and 2022, then Ana has one more title

        self.assertEqual(years_of(ana, C.ALONE_AT_THE_TOP), [2023])
        self.assertEqual(years_of(bob, C.ALONE_AT_THE_TOP), [])

    def test_hall_of_fame_podium_and_hall_of_famer(self):
        # 2021: eleven people on eleven teams, ranked 1 to 11. The 2022 table adds a title
        # to the first: positions 1 to 11. The 2023 table adds one to the fourth, 2nd then.
        people = [self.person(f"P{n}") for n in range(1, 12)]
        e2021, t2021 = self.edition(2021, size=11)
        for user, team in zip(people, t2021):
            self.seat(user, e2021, team)
        e2022, t2022 = self.edition(2022, size=2)
        self.seat(people[0], e2022, t2022[0])
        e2023, t2023 = self.edition(2023, size=2)
        self.seat(people[3], e2023, t2023[0])
        third, fourth, tenth, eleventh = people[2], people[3], people[9], people[10]

        self.assertEqual(years_of(third, C.HALL_OF_FAME_PODIUM), [2022])
        self.assertEqual(years_of(third, C.HALL_OF_FAMER), [2022])
        self.assertEqual(years_of(fourth, C.HALL_OF_FAME_PODIUM), [2023])
        self.assertEqual(years_of(fourth, C.HALL_OF_FAMER), [2022])
        self.assertEqual(years_of(tenth, C.HALL_OF_FAME_PODIUM), [])
        self.assertEqual(years_of(tenth, C.HALL_OF_FAMER), [2022])
        self.assertEqual(years_of(eleventh, C.HALL_OF_FAMER), [])

    def test_a_shared_position_on_the_cut_off_is_in(self):
        # Cat and Dan share a team, so the same places: position 3 twice, then Eve 5th.
        ana, bob, cat, dan, eve = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan", "Eve"))
        for user, rank in zip((ana, bob, cat, dan, eve), (1, 2, 3, 3, 4)):
            self.play(user, [rank, rank])

        self.assertEqual(
            [years_of(user, C.HALL_OF_FAME_PODIUM) for user in (ana, bob, cat, dan, eve)],
            [[2022], [2022], [2022], [2022], []],
        )

    def test_reign_after_three_tables_at_the_top(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1, 1, 1])  # tables 2022 to 2025

        self.assertEqual(years_of(ana, C.REIGN), [2024])

    def test_no_reign_after_two_tables(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1])  # tables 2022 and 2023

        self.assertEqual(years_of(ana, C.REIGN), [])

    def test_reign_again_after_losing_the_top(self):
        # Teammates until 2024. Bob's extra 2nd place puts him alone at the top of the 2025
        # table, Ana's fifth title puts her back there from 2026.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1, 1, None, 1, 1, 1])
        self.play(bob, [1, 1, 1, 1, 2])

        self.assertEqual(years_of(ana, C.REIGN), [2024, 2028])
        self.assertEqual(years_of(bob, C.REIGN), [2024])

    def test_the_reign_needs_the_edition_to_count_not_the_person(self):
        # Ana wins 2021, 2022 and 2024 and misses 2023, where Bob is 2nd. Tables: 2022 Ana
        # (1, 1) 1st; 2023 Ana (1, 1) 1st, Bob (2) 2nd, since two titles beat a 2nd place;
        # 2024 Ana (1, 1, 1) 1st. Bob's place makes 2023 an edition that counts, so Ana's
        # absence does not break her reign.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, None, 1])
        self.play(bob, [None, None, 2])

        self.assertEqual(years_of(ana, C.REIGN), [2024])

    def unranked(self, user, year):
        """Seat `user` on a team of a new finished edition of `year` where nothing ranks:
        no final_rank and no discipline, so no participation counts."""
        edition, teams = self.edition(year, ranked=False)
        self.seat(user, edition, teams[0])

    def test_an_edition_without_counted_places_breaks_the_reign(self):
        # Ana tops the 2022, 2023 and 2024 tables, but 2023 and 2024 counted nothing.
        ana = self.person("Ana")
        self.play(ana, [1, 1])
        self.unranked(ana, 2023)
        self.unranked(ana, 2024)

        self.assertEqual(years_of(ana, C.REIGN), [])

    def test_the_reign_restarts_after_an_edition_without_counted_places(self):
        # Tables 2022 (1), 2023 (broken), then 2024, 2025 and 2026 at the top again.
        ana = self.person("Ana")
        self.unranked(ana, 2023)
        self.play(ana, [1, 1, None, 1, 1, 1])

        self.assertEqual(years_of(ana, C.REIGN), [2026])

    def test_kingslayer_takes_the_top_from_someone_else(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 3, 4])  # 2022 table: (1, 3) 1st; 2023: (1, 3, 4) 2nd
        self.play(bob, [2, 2, 1])  # 2022 table: (2, 2) 2nd; 2023: (1, 2, 2) 1st

        self.assertEqual(years_of(bob, C.KINGSLAYER), [2023])
        self.assertEqual(years_of(ana, C.KINGSLAYER), [])

    def test_kingslayer_and_rocket_at_every_table_earned(self):
        # Tables: 2022 Ana (1, 3) 1st, Bob (2, 2) 2nd; 2023 Bob (1, 2, 2) takes the top;
        # 2024 Ana (1, 1, 3, 4) takes it back and keeps it in 2025; 2027 Bob
        # (1, 1, 1, 2, 2, 4, 4) takes it again; 2028 Ana (1, 1, 1, 1, 3, 4) again.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 3, 4, 1, 1, None, None, 1])
        self.play(bob, [2, 2, 1, 4, 4, 1, 1])

        for code in (C.KINGSLAYER, C.ROCKET):
            self.assertEqual(years_of(bob, code), [2023, 2027])
            self.assertEqual(years_of(ana, code), [2024, 2028])

    def test_no_kingslayer_at_the_first_table(self):
        # Ana tops the 2021 ranking, Bob the 2022 table, but 2021 alone is not a table.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 3])
        self.play(bob, [2, 1])

        self.assertEqual(years_of(bob, C.GOAT), [2022])
        self.assertEqual(years_of(bob, C.KINGSLAYER), [])
        self.assertEqual(years_of(bob, C.ROCKET), [])

    def test_no_kingslayer_for_the_standing_leader(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1])
        self.play(bob, [2, 2, 2])

        self.assertEqual(years_of(ana, C.KINGSLAYER), [])

    def test_rocket_for_the_biggest_climb_shared(self):
        # 2022 table: Ana 1, Bob 2, Cat 3, Dan 4, Eve 5. In 2023 Dan and Eve win on two
        # teams tied 1st: Ana (1, 1, 3) 1, Dan (1, 4, 4) 2, Eve (1, 5, 5) 3,
        # Bob (2, 2, 4) 4, Cat (3, 3, 5) 5. Dan and Eve both climb 2 places.
        ana, bob, cat, dan, eve = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan", "Eve"))
        e2023, t2023 = self.edition(2023, ranks=[1, 1, 3, 4, 5, 6])
        for user, rank in zip((ana, bob, cat, dan, eve), (1, 2, 3, 4, 5)):
            self.play(user, [rank, rank])
        for user, team in zip((dan, eve, ana, bob, cat), t2023):
            self.seat(user, e2023, team)

        self.assertEqual(years_of(dan, C.ROCKET), [2023])
        self.assertEqual(years_of(eve, C.ROCKET), [2023])
        self.assertEqual([years_of(user, C.ROCKET) for user in (ana, bob, cat)], [[], [], []])

    def test_no_climb_no_rocket(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1])
        self.play(bob, [2, 2, 2])

        self.assertEqual(years_of(ana, C.ROCKET), [])
        self.assertEqual(years_of(bob, C.ROCKET), [])

    def test_a_newcomer_has_no_climb(self):
        # 2022 table: Ana 1, Bob 2, Cat 3; Uma sits teamless, without a position. In 2023
        # Cat, Zed (new) and Uma win: Ana (1, 1, 3) 1, Cat (1, 3, 3) 2, Zed and Uma (1) 3,
        # Bob (2, 2, 4) 5. Only Cat climbs from a known position.
        ana, bob, cat = self.person("Ana"), self.person("Bob"), self.person("Cat")
        uma, zed = self.person("Uma"), self.person("Zed")
        e2023, t2023 = self.edition(2023, ranks=[1, 1, 3, 4])
        for user, rank in zip((ana, bob, cat), (1, 2, 3)):
            self.play(user, [rank, rank])
        for edition in Edition.objects.filter(year__in=(2021, 2022)):
            self.seat(uma, edition)
        self.seat(cat, e2023, t2023[0])
        self.seat(zed, e2023, t2023[1])
        self.seat(uma, e2023, t2023[1])
        self.seat(ana, e2023, t2023[2])
        self.seat(bob, e2023, t2023[3])

        self.assertEqual(years_of(cat, C.ROCKET), [2023])
        self.assertEqual(years_of(zed, C.ROCKET), [])
        self.assertEqual(years_of(uma, C.ROCKET), [])


GOD_CODES = (
    C.ATHENA,
    C.APOLLO,
    C.ARTEMIS,
    C.HERMES,
    C.HERACLES,
    C.THESEUS,
    C.ARES,
    C.HADES,
    C.DIONYSUS,
    C.OLYMPUS,
)
DISCIPLINE_CODES = (
    C.SPECIALIST,
    C.MASTER,
    C.ALL_ROUNDER,
    C.DECATHLETE,
    C.BRAINS_AND_BRAWN,
    C.CLEAN_SWEEP,
    C.METRONOME,
    C.UNCROWNED,
    C.PHOTO_FINISH,
    *GOD_CODES,
)


def disciplines_of(user, today=TODAY):
    """The user's discipline badges and gods, whatever the other rules give."""
    return [badge for badge in badges_of(user, today) if badge[0] in DISCIPLINE_CODES]


def specialist_of(user, today=TODAY):
    """The (year, tier, discipline) of the user's specialist badges, sorted."""
    return sorted(
        (year, tier, discipline)
        for c, year, tier, discipline, _ in badges_of(user, today)
        if c == C.SPECIALIST
    )


def master_of(user, today=TODAY):
    """The (year, discipline) of the user's master badges, sorted."""
    return sorted(
        (year, discipline)
        for c, year, _, discipline, _ in badges_of(user, today)
        if c == C.MASTER
    )


class DisciplineWorld(World):
    """
    Builds computed editions (teams without final_rank): a discipline's first save creates a
    result per active team, and a person seated on a team gets that team's results.
    """

    def results(self, discipline_model, edition, values, reveal=True):
        """
        A discipline of `edition` whose teams score `values` (a list, in team order): points
        for a points discipline (higher is better), seconds for a time discipline such as
        Crossfit or Orienteering (lower is better, stored as a `time`).
        """
        discipline = discipline_model.objects.create(edition=edition, reveal_score=reveal)
        timed = discipline.result_type == ResultTypes.TIME
        for team, value in zip(Team.objects.filter(edition=edition).order_by("id"), values):
            field = {"time": dt_time(0, value // 60, value % 60)} if timed else {"points": value}
            TeamResult.objects.filter(discipline=discipline, team=team).update(**field)
        return discipline

    def computed(self, year, user, size=2):
        """A computed edition of `size` teams with `user` on the first. Returns (edition,
        [teams])."""
        edition, teams = self.edition(year, size=size, ranked=False)
        self.seat(user, edition, teams[0])
        return edition, teams

    def win(self, user, year, *models):
        """A computed 2-team edition where `user`'s team wins each of the points disciplines
        `models`, 10 to 0."""
        edition, _ = self.computed(year, user)
        for model in models:
            self.results(model, edition, [10, 0])
        return edition

    def four(self, year, people, scores):
        """
        A computed 4-team edition with one person per team, in team order, and a discipline
        per (model, points in team order) of `scores`. With 4 teams, global points are 6, 4,
        3 and 1 for ranks 1 to 4.
        """
        edition, teams = self.edition(year, ranked=False)
        for user, team in zip(people, teams):
            self.seat(user, edition, team)
        for model, values in scores:
            self.results(model, edition, values)
        return edition


class TestDisciplines(DisciplineWorld, TestCase):
    def test_every_discipline_has_a_god_and_a_kind(self):
        edition, _ = self.edition(2021, ranked=False)
        models = Discipline.__subclasses__()
        names = {model.objects.create(edition=edition).name for model in models}

        self.assertEqual(len(names), len(models))
        self.assertEqual(sorted(names - set(FAMILIES)), [])
        self.assertEqual(sorted(names - {"Fair"} - set(KINDS)), [])
        self.assertNotIn("Fair", KINDS)

    def test_specialist_tiers_in_one_discipline(self):
        ana = self.person("Ana")
        for year in range(2021, 2026):
            self.win(ana, year, Relay)

        self.assertEqual(
            specialist_of(ana), [(2022, 1, "Relay"), (2023, 2, "Relay"), (2024, 3, "Relay")]
        )

    def test_no_specialist_for_two_different_disciplines(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        self.win(ana, 2022, Darts)

        self.assertEqual(specialist_of(ana), [])

    def test_a_discipline_won_twice_in_one_edition_counts_once(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Relay)

        self.assertEqual(specialist_of(ana), [])

    def test_master_for_winning_every_edition_of_a_discipline(self):
        ana = self.person("Ana")
        for year in (2021, 2022, 2023):
            self.win(ana, year, Relay)

        self.assertEqual(master_of(ana), [(2022, "Relay")])

    def test_one_edition_of_a_discipline_is_no_master(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        self.win(ana, 2022, Darts)

        self.assertEqual(master_of(ana), [])

    def test_master_is_lost_at_the_next_edition_not_won(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        self.win(ana, 2022, Relay)
        e2023, _ = self.computed(2023, ana)
        self.results(Relay, e2023, [0, 10])

        self.assertEqual(master_of(ana, today=date(2023, 1, 1)), [(2022, "Relay")])
        self.assertEqual(master_of(ana), [])

    def test_missing_an_edition_of_the_discipline_loses_master(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.win(ana, 2021, Relay)
        self.win(ana, 2022, Relay)
        self.win(bob, 2023, Relay)

        self.assertEqual(master_of(ana), [])

    def test_master_needs_the_editions_before_the_first_played(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.win(bob, 2021, Relay)
        self.win(ana, 2022, Relay)
        self.win(ana, 2023, Relay)

        self.assertEqual(master_of(ana), [])
        self.assertEqual(master_of(bob), [])

    def test_editions_without_the_discipline_do_not_count(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.win(ana, 2021, Relay)
        self.win(bob, 2022, Darts)  # Ana missed it, but it held no relay
        self.win(ana, 2023, Relay)

        self.assertEqual(master_of(ana), [(2023, "Relay")])

    def test_a_hidden_edition_of_the_discipline_neither_breaks_nor_extends_master(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        e2022, _ = self.computed(2022, ana)
        self.results(Relay, e2022, [0, 10], reveal=False)
        self.win(ana, 2023, Relay)

        self.assertEqual(master_of(ana), [(2023, "Relay")])

    def test_a_shared_first_place_is_a_win(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        e2021, teams = self.computed(2021, ana, size=3)
        self.seat(bob, e2021, teams[1])
        self.results(Relay, e2021, [10, 10, 0])  # contested: a third team beaten
        self.win(ana, 2022, Relay)

        self.assertEqual(master_of(ana), [(2022, "Relay")])
        self.assertEqual(master_of(bob), [])

    def test_an_uncontested_edition_of_the_discipline_neither_breaks_nor_extends_master(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        e2022, _ = self.computed(2022, ana)
        self.results(Relay, e2022, [0, 0])  # every team tied: Ana's shared 1st beats nobody
        e2023, _ = self.computed(2023, ana)
        self.results(Relay, e2023, [None, 10])  # a lone scored result: the other team's
        self.win(ana, 2024, Relay)

        self.assertEqual(master_of(ana), [(2024, "Relay")])

    def test_two_disciplines_of_one_name_in_an_edition_are_two_events(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay)
        e2022 = self.win(ana, 2022, Relay)
        self.results(Relay, e2022, [0, 10])

        self.assertEqual(master_of(ana), [])

    def test_master_of_each_discipline(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Relay, Darts)

        self.assertEqual(master_of(ana), [(2022, "Darts"), (2022, "Relay")])

    def test_all_rounder_at_the_third_discipline_won(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Relay)  # the same discipline again: still 2
        self.win(ana, 2023, GeneralCultureQuizz)

        self.assertEqual(tiers_of(ana, C.ALL_ROUNDER), [(2023, 1)])

    def test_all_rounder_tiers_at_five_and_eight(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts, Petanque, Frisbee)  # 4
        self.win(ana, 2022, Relay, Dance)  # 5
        self.win(ana, 2023, Football, Handball, Basketball)  # 8

        self.assertEqual(tiers_of(ana, C.ALL_ROUNDER), [(2021, 1), (2022, 2), (2023, 3)])

    def test_two_all_rounder_tiers_in_one_edition(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts, Petanque, Frisbee, Dance)

        self.assertEqual(tiers_of(ana, C.ALL_ROUNDER), [(2021, 1), (2021, 2)])

    def test_decathlete_at_the_tenth_discipline_on_the_podium(self):
        ana = self.person("Ana")
        second = [5, 10, 1, 0]  # Ana's team, the first, 2nd of 4
        for year, models in (
            (2021, (Relay, Darts, Petanque, Frisbee, Dance)),  # 5
            (2022, (Relay, Football, Handball, Basketball, Volleyball)),  # 9
            (2023, (Dodgeball,)),  # 10
            (2024, (Geoguessr,)),
        ):
            edition, _ = self.computed(year, ana, size=4)
            for model in models:
                self.results(model, edition, second)

        self.assertEqual(years_of(ana, C.DECATHLETE), [2023])

    def test_no_decathlete_podium_in_an_edition_of_three_teams(self):
        # Ana is last of 3 in Dodgeball in 2022: every result of a 3-team edition is on the
        # podium, so that one does not count and the tenth only comes in 2023.
        ana = self.person("Ana")
        for year, values, models in (
            (2021, [5, 10, 1, 0], (Relay, Darts, Petanque, Frisbee, Dance, Football)),  # 6
            (2022, [0, 10, 5], (Dodgeball,)),  # still 6
            (2023, [5, 10, 1, 0], (Handball, Basketball, Volleyball)),  # 9
            (2024, [5, 10, 1, 0], (Geoguessr,)),  # 10
        ):
            edition, _ = self.computed(year, ana, size=len(values))
            for model in models:
                self.results(model, edition, values)

        self.assertEqual(years_of(ana, C.DECATHLETE), [2024])

    def test_brains_and_brawn(self):
        ana = self.person("Ana")
        self.win(ana, 2021, GeneralCultureQuizz, Relay)

        self.assertEqual(years_of(ana, C.BRAINS_AND_BRAWN), [2021])

    def test_blindtest_is_a_mind_discipline(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Blindtest, Relay)

        self.assertEqual(years_of(ana, C.BRAINS_AND_BRAWN), [2021])

    def test_two_physical_wins_are_not_brains_and_brawn(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)

        self.assertEqual(years_of(ana, C.BRAINS_AND_BRAWN), [])

    def test_fair_is_neither_mind_nor_physical(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Fair, GeneralCultureQuizz)

        self.assertEqual(years_of(ana, C.BRAINS_AND_BRAWN), [])

    def test_brains_and_brawn_needs_one_edition(self):
        ana = self.person("Ana")
        self.win(ana, 2021, GeneralCultureQuizz)
        self.win(ana, 2022, Relay)

        self.assertEqual(years_of(ana, C.BRAINS_AND_BRAWN), [])

    def test_clean_sweep_at_three_wins_in_one_edition(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts, Petanque)

        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [2021])

    def test_two_wins_are_no_clean_sweep(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Petanque)

        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [])

    def test_a_lone_scored_result_wins_nothing(self):
        # Only Ana's team has a score in each discipline, the other one none yet: a lone
        # result beats nobody, as on the profiles.
        ana = self.person("Ana")
        for year in (2021, 2022):
            edition, _ = self.computed(year, ana)
            for model in (Relay, Darts, Petanque):
                self.results(model, edition, [10])

        self.assertEqual(specialist_of(ana), [])
        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [])
        self.assertEqual(disciplines_of(ana), [])

    def test_every_team_tied_on_nothing_wins_nothing(self):
        # Both teams on 0, as in a revealed discipline with a pairing system before any game
        # is played: everyone ties for 1st on nothing.
        ana = self.person("Ana")
        for year in (2021, 2022):
            edition, _ = self.computed(year, ana)
            for model in (Relay, Darts, Petanque):
                self.results(model, edition, [0, 0])

        self.assertEqual(specialist_of(ana), [])
        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [])
        self.assertEqual(disciplines_of(ana), [])

    def test_only_contested_disciplines_are_won(self):
        # Beside three disciplines won 10 to 0, a lone Frisbee score and a Dance tied on 0.
        ana = self.person("Ana")
        for year in (2021, 2022):
            edition = self.win(ana, year, Relay, Darts, Petanque)
            self.results(Frisbee, edition, [10])
            self.results(Dance, edition, [0, 0])

        self.assertEqual(
            specialist_of(ana),
            [(2022, 1, "Darts"), (2022, 1, "Petanque"), (2022, 1, "Relay")],
        )
        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [2021, 2022])
        self.assertEqual(tiers_of(ana, C.ALL_ROUNDER), [(2021, 1)])

    def podiums(self, user, *extra, reveal=True):
        """A computed 4-team edition of 2021 where `user`'s team is 1st, 2nd, 3rd and 2nd in
        four disciplines, plus one discipline per model of `extra` where it is 4th."""
        edition, _ = self.computed(2021, user, size=4)
        for model, values in (
            (Relay, [40, 30, 20, 10]),
            (Darts, [30, 40, 20, 10]),
            (Petanque, [20, 40, 30, 10]),
            (Frisbee, [30, 40, 20, 10]),
        ):
            self.results(model, edition, values)
        for model in extra:
            self.results(model, edition, [10, 40, 30, 20], reveal=reveal)
        return edition

    def test_metronome_on_the_podium_of_every_ranked_discipline(self):
        ana = self.person("Ana")
        self.podiums(ana)

        self.assertEqual(years_of(ana, C.METRONOME), [2021])

    def test_metronome_needs_every_ranked_discipline(self):
        ana = self.person("Ana")
        self.podiums(ana, Dance)

        self.assertEqual(years_of(ana, C.METRONOME), [])

    def test_metronome_needs_four_ranked_disciplines(self):
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=4)
        for model in (Relay, Darts, Petanque):
            self.results(model, edition, [40, 30, 20, 10])

        self.assertEqual(years_of(ana, C.METRONOME), [])

    def test_metronome_needs_an_edition_of_four_teams(self):
        # Ana's team is last in every discipline of a 2- and a 3-team edition, which is still
        # a podium there, and 3rd of 4 in every discipline of 2023.
        ana = self.person("Ana")
        for year, values in ((2021, [0, 10]), (2022, [0, 10, 5]), (2023, [5, 10, 20, 0])):
            edition, _ = self.computed(year, ana, size=len(values))
            for model in (Relay, Darts, Petanque, Frisbee):
                self.results(model, edition, values)

        self.assertEqual(years_of(ana, C.METRONOME), [2023])

    def test_no_metronome_for_winning_every_discipline_of_three_teams(self):
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        for model in (Relay, Darts, Petanque, Frisbee):
            self.results(model, edition, [30, 20, 10])

        self.assertEqual(years_of(ana, C.METRONOME), [])
        self.assertEqual(years_of(ana, C.CLEAN_SWEEP), [2021])

    def test_a_hidden_discipline_is_not_ranked(self):
        ana = self.person("Ana")
        self.podiums(ana, Dance, reveal=False)

        self.assertEqual(years_of(ana, C.METRONOME), [2021])

    def test_an_uncontested_discipline_is_not_ranked(self):
        # Another team's lone Dance score and a Football tied on 0 rank nobody.
        ana = self.person("Ana")
        edition = self.podiums(ana)
        self.results(Dance, edition, [None, 40])
        self.results(Football, edition, [0, 0, 0, 0])

        self.assertEqual(years_of(ana, C.METRONOME), [2021])

    def test_a_tie_on_nothing_is_no_fourth_ranked_discipline(self):
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=4)
        for model in (Relay, Darts, Petanque):
            self.results(model, edition, [40, 30, 20, 10])
        self.results(Football, edition, [0, 0, 0, 0])

        self.assertEqual(years_of(ana, C.METRONOME), [])

    def test_uncrowned_with_the_most_wins_without_the_title(self):
        # Wins: A 2, B 1, C 1, D 1. Totals: A 15, B 22, C 19, D 14: B is champion.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021,
            [ana, bob, cat, dan],
            [
                (Relay, [40, 30, 20, 10]),
                (Darts, [40, 30, 20, 10]),
                (Petanque, [10, 40, 30, 20]),
                (Frisbee, [10, 30, 40, 20]),
                (Dance, [10, 30, 20, 40]),
            ],
        )

        self.assertEqual(years_of(ana, C.UNCROWNED), [2021])
        self.assertEqual([years_of(u, C.UNCROWNED) for u in (bob, cat, dan)], [[], [], []])

    def test_the_champion_is_never_uncrowned(self):
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        for model in (Relay, Darts):
            self.results(model, edition, [30, 20, 10])

        self.assertEqual(years_of(ana, C.UNCROWNED), [])

    def test_uncrowned_when_tied_on_wins(self):
        # Wins: A 2, B 1, C 2. Totals: A 15, B 22, C 22, D 11: B and C share the title.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021,
            [ana, bob, cat, dan],
            [
                (Relay, [40, 30, 20, 10]),
                (Darts, [40, 30, 20, 10]),
                (Petanque, [10, 40, 30, 20]),
                (Frisbee, [10, 30, 40, 20]),
                (Dance, [10, 30, 40, 20]),
            ],
        )

        self.assertEqual(years_of(ana, C.UNCROWNED), [2021])
        self.assertEqual(years_of(cat, C.UNCROWNED), [])

    def test_no_uncrowned_when_another_team_won_more(self):
        # Wins: A 2, B 3. Totals: A 15, B 26, C 18, D 11: Ana is 3rd, Bob champion.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021,
            [ana, bob, cat, dan],
            [
                (Relay, [40, 30, 20, 10]),
                (Darts, [40, 30, 20, 10]),
                (Petanque, [10, 40, 30, 20]),
                (Frisbee, [10, 40, 30, 20]),
                (Dance, [10, 40, 30, 20]),
            ],
        )

        self.assertEqual(years_of(ana, C.BRONZE), [2021])
        self.assertEqual(years_of(ana, C.UNCROWNED), [])
        self.assertEqual(years_of(bob, C.UNCROWNED), [])

    def test_a_lone_scored_result_is_no_win_for_uncrowned(self):
        # Wins: A 1 (plus a lone Dance score), B 1, C 1, D 1. Totals: A 15, B 18, C 16, D 13.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021,
            [ana, bob, cat, dan],
            [
                (Relay, [40, 30, 20, 10]),
                (Darts, [10, 40, 30, 20]),
                (Petanque, [10, 30, 40, 20]),
                (Frisbee, [10, 30, 20, 40]),
                (Dance, [10]),
            ],
        )

        self.assertEqual(years_of(ana, C.BRONZE), [2021])
        self.assertEqual(years_of(ana, C.UNCROWNED), [])

    def test_one_win_is_not_uncrowned(self):
        # One win each; totals A 10, B 11, C 9: B is champion, A 2nd.
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        for model, values in (
            (Relay, [30, 20, 10]),
            (Darts, [10, 20, 30]),
            (Petanque, [20, 30, 10]),
        ):
            self.results(model, edition, values)

        self.assertEqual(years_of(ana, C.UNCROWNED), [])

    def test_photo_finish_on_the_points_difference(self):
        # A 20-0 C, B 5-0 C, A 0-0 B: A and B have 4 league points, A the better difference.
        ana, bob = self.person("Ana"), self.person("Bob")
        edition, (a, b, c) = self.edition(2021, size=3, ranked=False)
        self.seat(ana, edition, a)
        self.seat(bob, edition, b)
        rugby = Rugby.objects.create(edition=edition, reveal_score=True)
        round_ = TeamSportRound.objects.create(discipline=rugby, order=1)
        for team1, score1, team2, score2, referees in (
            (a, 20, c, 0, b),
            (b, 5, c, 0, a),
            (a, 0, b, 0, c),
        ):
            Game.objects.create(
                discipline=rugby,
                round=round_,
                team1=team1,
                score1=score1,
                team2=team2,
                score2=score2,
                referees=referees,
                edition=edition,
                is_played=True,
            )

        points = TeamResult.objects.filter(discipline=rugby).order_by("team_id")
        self.assertEqual(list(points.values_list("points", flat=True)), [4, 4, 0])
        self.assertEqual(years_of(ana, C.PHOTO_FINISH), [2021])
        self.assertEqual(years_of(bob, C.PHOTO_FINISH), [])

    def test_photo_finish_by_one_total_point(self):
        # Totals: A 6 + 3 = 9, B 4 + 6 = 10, C 3 + 4 = 7, D 1 + 1 = 2.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021,
            [ana, bob, cat, dan],
            [(Relay, [40, 30, 20, 10]), (Darts, [20, 40, 30, 10])],
        )

        self.assertEqual(years_of(bob, C.PHOTO_FINISH), [2021])
        self.assertEqual(years_of(ana, C.PHOTO_FINISH), [])

    def test_no_photo_finish_by_two_points(self):
        # Totals: A 5, B 3, C 2.
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        self.results(Relay, edition, [30, 20, 10])

        self.assertEqual(years_of(ana, C.PHOTO_FINISH), [])

    def test_no_photo_finish_on_a_time_discipline(self):
        # A time result has no points: its rank-2 result never ties it on points. Totals:
        # A 5, B 3, C 2, so the totals give nothing either.
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        self.results(Crossfit, edition, [60, 120, 180])

        self.assertEqual(years_of(ana, C.PHOTO_FINISH), [])

    def test_no_photo_finish_for_a_shared_first_place(self):
        # Darts 10, 10, 5: A and B tie 1st without a tie-breaker, and on totals (5, 5, 2).
        ana = self.person("Ana")
        edition, _ = self.computed(2021, ana, size=3)
        self.results(Darts, edition, [10, 10, 5])

        self.assertEqual(years_of(ana, C.CHAMPION), [2021])
        self.assertEqual(years_of(ana, C.PHOTO_FINISH), [])

    def test_hidden_disciplines_give_nothing(self):
        ana = self.person("Ana")
        for year in (2021, 2022):
            edition, _ = self.computed(year, ana)
            for model in (Relay, GeneralCultureQuizz, Darts):
                self.results(model, edition, [10, 0], reveal=False)
            self.results(Petanque, edition, [0, 10])  # revealed, Ana 2nd: the edition ranks

        self.assertEqual(disciplines_of(ana), [])

    def test_a_god_once_at_the_first_win_of_its_family(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Darts)
        self.win(ana, 2022, Darts)
        self.win(ana, 2023, Petanque)

        self.assertEqual(years_of(ana, C.ARTEMIS), [2021])

    def test_olympus_at_the_ninth_god(self):
        ana = self.person("Ana")
        e2021 = self.win(ana, 2021, Relay, Darts, GeneralCultureQuizz, Blindtest)
        self.results(Crossfit, e2021, [60, 120])  # 1:00 against 2:00
        e2022 = self.win(ana, 2022, Rugby, HideAndSeek)
        self.results(Orienteering, e2022, [90, 95])
        self.win(ana, 2023, Fair)

        gods = sorted((c, year) for c, year, *_ in badges_of(ana) if c in GOD_CODES)
        self.assertEqual(
            gods,
            sorted(
                [
                    (C.HERMES, 2021),
                    (C.ARTEMIS, 2021),
                    (C.ATHENA, 2021),
                    (C.APOLLO, 2021),
                    (C.HERACLES, 2021),
                    (C.THESEUS, 2022),
                    (C.ARES, 2022),
                    (C.HADES, 2022),
                    (C.DIONYSUS, 2023),
                    (C.OLYMPUS, 2023),
                ]
            ),
        )

    def test_a_hand_ranked_edition_gives_no_discipline_badge(self):
        ana = self.person("Ana")
        for year in (2021, 2022):
            edition, teams = self.edition(year)  # final_rank 1 to 4
            self.seat(ana, edition, teams[0])
            Relay.objects.create(edition=edition, reveal_score=True)  # nothing entered

        self.assertEqual(years_of(ana, C.CHAMPION), [2021, 2022])
        self.assertEqual(disciplines_of(ana), [])


GAME_CODES = (
    C.UNBEATEN,
    C.PERFECT_RUN,
    C.SHUTOUT,
    C.STEAMROLLER,
    C.PERFECT_PITCH,
)


def games_of(user, *codes, today=TODAY):
    """The user's game badges, or only those of `codes`, whatever the other rules give."""
    codes = codes or GAME_CODES
    return [badge for badge in badges_of(user, today) if badge[0] in codes]


class TestGames(World, TestCase):
    """
    Computed 4-team editions (teams without final_rank) with Ana, Bob, Cat and Dan on teams
    1 to 4. A team sport keeps its pairing system at None, so nothing is scheduled: each
    test enters its own games, played unless it says otherwise.
    """

    def setUp(self):
        self.people = [self.person(n) for n in ("Ana", "Bob", "Cat", "Dan")]
        self.ana, self.bob, self.cat, self.dan = self.people

    def four(self, year=2021):
        """A computed 4-team edition of `year`, one person per team. Returns (edition,
        teams)."""
        edition, teams = self.edition(year, ranked=False)
        for user, team in zip(self.people, teams):
            self.seat(user, edition, team)
        return edition, teams

    @staticmethod
    def sport(edition, model=Rugby, reveal=True):
        """A team sport of `edition`, revealed or not. Returns its first round."""
        discipline = model.objects.create(edition=edition, reveal_score=reveal)
        return TeamSportRound.objects.create(discipline=discipline, order=1)

    @staticmethod
    def game(round_, team1, score1, team2, score2, referees, **fields):
        """A played game of `round_`; `fields` such as is_played=False override."""
        discipline = round_.discipline
        return Game.objects.create(
            discipline=discipline,
            round=round_,
            team1=team1,
            score1=score1,
            team2=team2,
            score2=score2,
            referees=referees,
            edition_id=discipline.edition_id,
            **{"is_played": True, **fields},
        )

    def test_perfect_run_for_three_games_won(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 3, c)
        self.game(rugby, a, 12, c, 3, d)
        self.game(rugby, d, 3, a, 12, b)  # won as the second team

        self.assertEqual(
            games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN),
            [(C.PERFECT_RUN, 2021, 0, "Rugby", None)],
        )

    def test_unbeaten_for_three_games_without_a_loss(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 3, c)
        self.game(rugby, c, 5, a, 5, d)
        self.game(rugby, a, 12, d, 3, b)

        self.assertEqual(
            games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN),
            [(C.UNBEATEN, 2021, 0, "Rugby", None)],
        )

    def test_two_games_won_are_not_enough(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 3, c)
        self.game(rugby, a, 12, c, 3, d)

        self.assertEqual(games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN), [])

    def test_one_loss_gives_nothing(self):
        # Three games won and one lost: only the loss refuses both.
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 3, c)
        self.game(rugby, a, 12, c, 3, d)
        self.game(rugby, a, 12, d, 3, b)
        self.game(rugby, b, 10, a, 9, c)

        self.assertEqual(games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN), [])

    def test_each_discipline_is_judged_apart(self):
        # Rugby: three wins. Football: two wins and a draw. Counted together (five wins
        # and a draw), they would make a single unbeaten.
        edition, (a, b, c, d) = self.four()
        rugby, football = self.sport(edition), self.sport(edition, Football)
        for round_ in (rugby, football):
            self.game(round_, a, 12, b, 3, c)
            self.game(round_, a, 12, c, 3, d)
        self.game(rugby, a, 12, d, 3, b)
        self.game(football, a, 4, d, 4, b)

        self.assertEqual(
            games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN),
            [(C.PERFECT_RUN, 2021, 0, "Rugby", None), (C.UNBEATEN, 2021, 0, "Football", None)],
        )

    def test_unplayed_games_and_inactive_rounds_games_and_disciplines_count_for_nothing(self):
        # Two wins count for Ana's team: any one excluded Rugby game would make a third win
        # (a perfect run, a shutout), and so would the win of the deactivated Football.
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, c, 3, b)
        self.game(rugby, a, 12, d, 3, b)
        self.game(rugby, c, 1, d, 1, b)
        self.game(rugby, c, 2, d, 1, b)
        inactive = TeamSportRound.objects.create(
            discipline=rugby.discipline, order=2, is_active=False
        )
        self.game(rugby, a, 12, c, 0, b, is_played=False)
        self.game(inactive, a, 12, d, 0, b)
        self.game(rugby, a, 12, c, 0, b, is_active=False)
        football = self.sport(edition, Football)
        self.game(football, a, 12, c, 0, b)
        Discipline.objects.filter(pk=football.discipline_id).update(is_active=False)

        self.assertEqual(games_of(self.ana, C.UNBEATEN, C.PERFECT_RUN, C.SHUTOUT), [])

    def test_shutout_once_per_edition(self):
        for year in (2021, 2022):
            edition, (a, b, c, d) = self.four(year)
            rugby = self.sport(edition)
            self.game(rugby, a, 12, b, 0, c)
            self.game(rugby, d, 0, a, 12, b)

        self.assertEqual(
            games_of(self.ana, C.SHUTOUT),
            [(C.SHUTOUT, 2021, 0, "", None), (C.SHUTOUT, 2022, 0, "", None)],
        )
        self.assertEqual(games_of(self.bob, C.SHUTOUT), [])  # losing to nil is no shutout

    def test_no_shutout_after_conceding(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 3, c)
        self.game(rugby, a, 0, c, 0, d)  # a goalless draw is no win

        self.assertEqual(games_of(self.ana, C.SHUTOUT), [])
        self.assertEqual(games_of(self.cat, C.SHUTOUT), [])

    def test_steamroller_is_judged_per_discipline(self):
        # Raw margins aren't comparable across sports: Darts' 301-141 (margin 160) dwarfs any
        # Rugby score, but each discipline judges only its own games. Rugby: Ana's team wins
        # by 13, Cat's by 2, so Ana's the biggest Rugby margin. Darts: Bob's team wins by 160,
        # Ana's second Darts game only by 10, so Bob's still the biggest Darts margin. Both
        # earn steamroller, each with their own discipline.
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 13, b, 0, c)
        self.game(rugby, c, 5, d, 3, a)
        darts = self.sport(edition, Darts)
        self.game(darts, b, 301, c, 141, d)
        self.game(darts, a, 100, d, 90, b)

        self.assertEqual(
            games_of(self.ana, C.STEAMROLLER), [(C.STEAMROLLER, 2021, 0, "Rugby", None)]
        )
        self.assertEqual(
            games_of(self.bob, C.STEAMROLLER), [(C.STEAMROLLER, 2021, 0, "Darts", None)]
        )
        self.assertEqual(
            [games_of(user, C.STEAMROLLER) for user in (self.cat, self.dan)], [[], []]
        )

    def test_a_tied_biggest_margin_gives_it_to_both_winners_of_that_discipline(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 12, b, 0, c)
        self.game(rugby, d, 3, c, 15, a)
        self.game(rugby, a, 5, d, 4, b)

        self.assertEqual(
            [games_of(user, C.STEAMROLLER) for user in self.people],
            [
                [(C.STEAMROLLER, 2021, 0, "Rugby", None)],
                [],
                [(C.STEAMROLLER, 2021, 0, "Rugby", None)],
                [],
            ],
        )

    def test_a_draw_is_never_a_steamroller(self):
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 5, b, 5, c)
        self.game(rugby, c, 0, d, 0, a)

        self.assertEqual([years_of(user, C.STEAMROLLER) for user in self.people], [[]] * 4)

    def test_a_hidden_disciplines_games_give_no_steamroller(self):
        # Dan's 30-0 win is the only game of the edition, but its Football is hidden: no one
        # earns the badge.
        edition, (a, b, c, d) = self.four()
        football = self.sport(edition, Football, reveal=False)
        self.game(football, d, 30, b, 0, a)

        self.assertEqual([years_of(user, C.STEAMROLLER) for user in self.people], [[]] * 4)

    def test_one_team_earns_steamroller_in_two_disciplines(self):
        # Ana's team has the biggest margin in both Rugby and Darts, so it earns steamroller
        # twice: one badge per discipline, not one for the edition.
        edition, (a, b, c, d) = self.four()
        rugby = self.sport(edition)
        self.game(rugby, a, 13, b, 0, c)
        darts = self.sport(edition, Darts)
        self.game(darts, a, 301, b, 100, c)

        self.assertEqual(
            games_of(self.ana, C.STEAMROLLER),
            [
                (C.STEAMROLLER, 2021, 0, "Darts", None),
                (C.STEAMROLLER, 2021, 0, "Rugby", None),
            ],
        )

    def blindtest(self, reveal=True):
        """
        A Blindtest of a new 2021 edition (its save makes 10 rounds with a guess per team)
        where Ana's team finds artist and song in every round. A queryset update skips
        BlindtestGuess.save() and its points bookkeeping. Returns (blindtest, Ana's team).
        """
        edition, teams = self.four()
        blindtest = Blindtest.objects.create(edition=edition, reveal_score=reveal)
        BlindtestGuess.objects.filter(team=teams[0]).update(
            is_artist_correct=True, is_song_correct=True
        )
        return blindtest, teams[0]

    def test_perfect_pitch_for_artist_and_song_in_every_round(self):
        self.blindtest()

        self.assertEqual(
            games_of(self.ana, C.PERFECT_PITCH), [(C.PERFECT_PITCH, 2021, 0, "", None)]
        )
        self.assertEqual(games_of(self.bob, C.PERFECT_PITCH), [])

    def test_no_perfect_pitch_with_only_the_artist_in_one_round(self):
        _, team = self.blindtest()
        BlindtestGuess.objects.filter(team=team, blindtest_round__order=4).update(
            is_song_correct=False
        )

        self.assertEqual(games_of(self.ana, C.PERFECT_PITCH), [])

    def test_a_deactivated_round_is_ignored(self):
        blindtest, team = self.blindtest()
        BlindtestGuess.objects.filter(team=team, blindtest_round__order=4).update(
            is_artist_correct=False, is_song_correct=False
        )
        BlindtestRound.objects.filter(blindtest=blindtest, order=4).update(is_active=False)

        self.assertEqual(years_of(self.ana, C.PERFECT_PITCH), [2021])

    def test_a_hidden_blindtest_gives_nothing(self):
        self.blindtest(reveal=False)

        self.assertEqual(games_of(self.ana, C.PERFECT_PITCH), [])

    def test_a_round_without_the_teams_guess_is_not_found(self):
        # The other teams still guessed round 4, so it is a round to find.
        _, team = self.blindtest()
        BlindtestGuess.objects.filter(team=team, blindtest_round__order=4).delete()

        self.assertEqual(games_of(self.ana, C.PERFECT_PITCH), [])

    def test_a_deactivated_guess_is_not_found(self):
        # Right on artist and song, but deactivated: round 4 is not found.
        _, team = self.blindtest()
        BlindtestGuess.objects.filter(team=team, blindtest_round__order=4).update(
            is_active=False
        )

        self.assertEqual(games_of(self.ana, C.PERFECT_PITCH), [])

    def test_a_deactivated_blindtest_gives_nothing(self):
        blindtest, _ = self.blindtest()
        Discipline.objects.filter(pk=blindtest.pk).update(is_active=False)

        self.assertEqual(games_of(self.ana, C.PERFECT_PITCH), [])


class TestProgressTargets(TestCase):
    def test_the_targets_of_the_non_tiered_badges(self):
        # full-set's rule compares the places won with {1, 2, 3}, not with its target of 3.
        self.assertEqual(
            PROGRESS_TARGETS,
            {
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
            },
        )
        self.assertEqual(len(GODS), 9)

    def test_the_codes_with_progress(self):
        self.assertEqual(
            set(PROGRESS_TARGETS) | TIERED_CODES | {C.ARGONAUT}, set(PROGRESS_CODES)
        )
        self.assertEqual(len(PROGRESS_CODES), 20)
        self.assertEqual(
            [code for code in Badge.Codes.values if code in PROGRESS_CODES], list(PROGRESS_CODES)
        )


class TestProgress(World, TestCase):
    """The rows compute() returns beside the badges, on hand-ranked histories."""

    def test_a_person_without_a_finished_edition_reads_zero(self):
        # Ana only plays the running 2030 edition, and 2021 is over without her: a row for
        # every code with progress, all at 0, and argonaut out of reach.
        self.edition(2021)
        e2030, t2030 = self.edition(2030, finished=False)
        ana = self.person("Ana")
        self.seat(ana, e2030, t2030[0])

        expected = {
            code: Progress(ana.id, code, 0, best=0 if code in STREAK_CODES else None)
            for code in PROGRESS_CODES
        }
        expected[C.ARGONAUT] = Progress(ana.id, C.ARGONAUT, None, reachable=False)
        self.assertEqual(progress_of(ana), expected)

    def test_no_argonaut_row_before_the_first_edition_is_over(self):
        e2030, t2030 = self.edition(2030, finished=False)
        ana = self.person("Ana")
        self.seat(ana, e2030, t2030[0])

        rows = progress_of(ana)
        self.assertNotIn(C.ARGONAUT, rows)
        self.assertEqual(set(rows), set(PROGRESS_CODES) - {C.ARGONAUT})

    def test_argonaut_has_a_row_only_once_out_of_reach(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [3, 3])
        self.play(bob, [None, 3])
        spectator = User.objects.get(username="u-Spectator2021")

        self.assertNotIn(C.ARGONAUT, progress_of(ana))
        self.assertNotIn(C.ARGONAUT, progress_of(spectator))
        self.assertEqual(
            progress_of(bob)[C.ARGONAUT], Progress(bob.id, C.ARGONAUT, None, reachable=False)
        )
        self.assertNotIn(C.ARGONAUT, progress_of(bob, today=date(2021, 9, 22)))

    def test_a_streak_reads_its_current_run_and_its_best(self):
        ana = self.person("Ana")
        self.play(ana, [2, 3, 4, 3])  # podiums in a row: 1, 2, 0, 1

        self.assertEqual(
            progress_of(ana)[C.PODIUM_REGULAR], Progress(ana.id, C.PODIUM_REGULAR, 1, best=2)
        )

    def test_a_missed_edition_breaks_the_current_run(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, None])  # titles in a row: 1, 2, 0

        rows = progress_of(ana)
        self.assertNotIn(C.BACK_TO_BACK, rows)  # earned in 2022
        self.assertEqual(rows[C.THREEPEAT], Progress(ana.id, C.THREEPEAT, 0, best=2))
        self.assertEqual(rows[C.DYNASTY], Progress(ana.id, C.DYNASTY, 0, best=2))
        self.assertEqual(rows[C.PODIUM_REGULAR], Progress(ana.id, C.PODIUM_REGULAR, 0, best=2))

    def test_the_title_run_feeds_the_title_streaks_not_yet_earned(self):
        ana = self.person("Ana")
        self.play(ana, [1, 1, 1, 4, 1])  # titles in a row: 1, 2, 3, 0, 1

        rows = progress_of(ana)
        self.assertEqual(
            [code for code in (C.BACK_TO_BACK, C.THREEPEAT, C.DYNASTY) if code in rows],
            [C.DYNASTY],
        )
        self.assertEqual(rows[C.DYNASTY], Progress(ana.id, C.DYNASTY, 1, best=3))

    def test_on_the_rise_counts_the_rises_in_a_row(self):
        ana = self.person("Ana")
        self.play(ana, [6, 4])

        self.assertEqual(
            progress_of(ana)[C.ON_THE_RISE], Progress(ana.id, C.ON_THE_RISE, 1, best=1)
        )

    def test_on_the_rise_reads_zero_after_an_unranked_edition(self):
        # One rise, then a team without a rank: the rule's run falls to 0, below the 1 of a
        # first ranked edition, and the counter to 0, not -1.
        ana = self.person("Ana")
        e2023, t2023 = self.edition(2023, ranks=[1, 2, 3, None])
        self.play(ana, [6, 4])
        self.seat(ana, e2023, t2023[3])

        self.assertEqual(
            progress_of(ana)[C.ON_THE_RISE], Progress(ana.id, C.ON_THE_RISE, 0, best=1)
        )

    def test_ever_present_reads_the_current_run_and_the_best(self):
        # Tier 2 held from a run of 6: the current run of 5 aims at the 8 above the best.
        later = date(2033, 1, 1)  # after the twelfth edition, 2032
        ana = self.person("Ana")
        self.play(ana, [5] * 6 + [None] + [5] * 5)

        self.assertEqual(tiers_of(ana, C.EVER_PRESENT, later), [(2024, 1), (2026, 2)])
        self.assertEqual(
            progress_of(ana, later)[C.EVER_PRESENT], Progress(ana.id, C.EVER_PRESENT, 5, best=6)
        )

    def test_ever_present_at_its_top_tier_with_a_short_run(self):
        ana = self.person("Ana")
        self.play(ana, [5] * 8 + [None, 5])

        self.assertEqual(tiers_of(ana, C.EVER_PRESENT), [(2024, 1), (2026, 2), (2028, 3)])
        self.assertEqual(
            progress_of(ana)[C.EVER_PRESENT], Progress(ana.id, C.EVER_PRESENT, 1, best=8)
        )

    def test_a_tiered_row_stays_at_the_top_tier(self):
        ana = self.person("Ana")
        self.play(ana, [4] * 10)

        self.assertEqual(tiers_of(ana, C.VETERAN), [(2023, 1), (2025, 2), (2030, 3)])
        self.assertEqual(progress_of(ana)[C.VETERAN], Progress(ana.id, C.VETERAN, 10))

    def test_a_count_row_goes_once_earned(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 4, 1, 4])
        self.play(bob, [3, 1, 2, 3])

        rows = progress_of(ana)
        self.assertEqual(rows[C.LEGEND], Progress(ana.id, C.LEGEND, 2))
        self.assertEqual(rows[C.FULL_SET], Progress(ana.id, C.FULL_SET, 1))
        rows = progress_of(bob)
        self.assertEqual(rows[C.LEGEND], Progress(bob.id, C.LEGEND, 1))
        self.assertNotIn(C.FULL_SET, rows)  # 3rd, 1st then 2nd: earned in 2023

    def test_reign_reads_zero_after_losing_the_top(self):
        # Tables: 2022 Ana (1, 1) 1st; 2023 Ana still 1st over Bob (1, 2, 2); 2024 Bob
        # (1, 1, 2, 2) takes the top, his extra places counting in his favour.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1])
        self.play(bob, [2, 2, 1, 1])

        self.assertEqual(progress_of(ana)[C.REIGN], Progress(ana.id, C.REIGN, 0, best=2))
        self.assertEqual(progress_of(bob)[C.REIGN], Progress(bob.id, C.REIGN, 1, best=1))

    def test_eternal_second_is_out_of_reach_once_an_edition_is_won(self):
        ana, bob, cat = self.person("Ana"), self.person("Bob"), self.person("Cat")
        self.play(ana, [2, 1])  # a title before a second 2nd place
        self.play(bob, [3, 2])
        self.play(cat, [2, 2])

        self.assertEqual(
            progress_of(ana)[C.ETERNAL_SECOND],
            Progress(ana.id, C.ETERNAL_SECOND, None, reachable=False),
        )
        self.assertEqual(progress_of(bob)[C.ETERNAL_SECOND], Progress(bob.id, C.ETERNAL_SECOND, 1))
        self.assertNotIn(C.ETERNAL_SECOND, progress_of(cat))

    def test_eternal_second_earned_before_a_title_has_no_row(self):
        ana = self.person("Ana")
        self.play(ana, [2, 2, 1])

        self.assertNotIn(C.ETERNAL_SECOND, progress_of(ana))

    def test_lucky_charm_is_out_of_reach_once_an_early_edition_is_off_the_podium(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [2, 4, 1])
        self.play(bob, [3, 1])

        self.assertEqual(
            progress_of(ana)[C.LUCKY_CHARM], Progress(ana.id, C.LUCKY_CHARM, None, reachable=False)
        )
        self.assertEqual(progress_of(bob)[C.LUCKY_CHARM], Progress(bob.id, C.LUCKY_CHARM, 2))

    def test_lucky_charm_counts_the_counted_editions_only(self):
        # 2022 played without a team counts for nothing: the first three counted are 2021,
        # 2023 and 2024, and the last one is off the podium.
        ana = self.person("Ana")
        self.play(ana, [2, None, 3, 5])
        self.seat(ana, Edition.objects.get(year=2022))

        self.assertEqual(
            progress_of(ana)[C.LUCKY_CHARM], Progress(ana.id, C.LUCKY_CHARM, None, reachable=False)
        )
        self.assertEqual(
            progress_of(ana, today=date(2024, 1, 1))[C.LUCKY_CHARM],
            Progress(ana.id, C.LUCKY_CHARM, 2),
        )

    def test_rows_only_for_the_codes_with_progress(self):
        ana = self.person("Ana")
        self.play(ana, [1, 6, 1, 1])

        self.assertLessEqual(set(progress_of(ana)), set(PROGRESS_CODES))
        self.assertIn(C.CHAMPION, {badge[0] for badge in badges_of(ana)})


class TestComradesProgress(World, TestCase):
    """Ana's comrades row: the partner closest to 3 editions together among those below."""

    def setUp(self):
        self.ana, self.bob, self.chloe = (self.person(n) for n in ("Ana", "Bob", "Chloé"))

    def meet(self, year, *mates):
        """Ana and `mates` on the same team in a new edition of `year`."""
        edition, teams = self.edition(year)
        for user in (self.ana, *mates):
            self.seat(user, edition, teams[0])

    def comrades(self, user=None):
        return progress_of(user or self.ana).get(C.COMRADES)

    def test_the_partner_with_the_most_editions_together(self):
        self.meet(2021, self.bob)
        self.meet(2022, self.bob, self.chloe)

        self.assertEqual(
            counters_of(self.ana).together, {self.bob.id: (2, 1), self.chloe.id: (1, 1)}
        )
        self.assertEqual(
            self.comrades(), Progress(self.ana.id, C.COMRADES, 2, partner_id=self.bob.id)
        )

    def test_a_tie_goes_to_the_latest_edition_together(self):
        self.meet(2021, self.bob)
        self.meet(2022, self.chloe)

        self.assertEqual(
            self.comrades(), Progress(self.ana.id, C.COMRADES, 1, partner_id=self.chloe.id)
        )

    def test_then_to_the_last_name(self):
        zoe = User.objects.create(username="u-Zoe", first_name="Zoé", last_name="Aubert")
        self.meet(2021, self.bob, zoe)

        self.assertEqual(self.comrades(), Progress(self.ana.id, C.COMRADES, 1, partner_id=zoe.id))

    def test_then_to_the_first_name_accents_aside(self):
        elodie, fanny = self.person("Élodie"), self.person("Fanny")
        self.meet(2021, fanny, elodie)

        self.assertEqual(
            self.comrades(), Progress(self.ana.id, C.COMRADES, 1, partner_id=elodie.id)
        )

    def test_networker_counts_the_distinct_teammates(self):
        self.meet(2021, self.bob, self.chloe)
        self.meet(2022, self.bob)

        self.assertEqual(progress_of(self.ana)[C.NETWORKER], Progress(self.ana.id, C.NETWORKER, 2))
        self.assertEqual(progress_of(self.bob)[C.NETWORKER], Progress(self.bob.id, C.NETWORKER, 2))

    def test_after_a_first_partner_the_next_one(self):
        for year in (2021, 2022, 2023):
            self.meet(year, self.bob)
        self.meet(2024, self.bob, self.chloe)

        self.assertEqual(comrades_of(self.ana), [(2023, self.bob.id)])
        self.assertEqual(
            self.comrades(), Progress(self.ana.id, C.COMRADES, 1, partner_id=self.chloe.id)
        )

    def test_no_row_once_every_partner_is_at_three(self):
        for year in (2021, 2022, 2023, 2024):
            self.meet(year, self.bob)

        self.assertIsNone(self.comrades())
        self.assertIsNone(self.comrades(self.bob))

    def test_without_a_teammate_it_reads_zero(self):
        edition, teams = self.edition(2021)
        self.seat(self.ana, edition, teams[0])  # alone on the team
        self.seat(self.bob, edition)  # no team

        self.assertEqual(self.comrades(), Progress(self.ana.id, C.COMRADES, 0))
        self.assertEqual(self.comrades(self.bob), Progress(self.bob.id, C.COMRADES, 0))


class TestDisciplineProgress(DisciplineWorld, TestCase):
    def test_the_discipline_counts(self):
        # Ana's team is 1st in Relay and 2nd in Darts of a 4-team edition, 1st in Dance of a
        # 2-team one: three podiums, but the 2-team edition's does not count for decathlete.
        ana, bob, cat, dan = (self.person(n) for n in ("Ana", "Bob", "Cat", "Dan"))
        self.four(
            2021, [ana, bob, cat, dan], [(Relay, [40, 30, 20, 10]), (Darts, [30, 40, 20, 10])]
        )
        self.win(ana, 2022, Dance)

        rows = progress_of(ana)
        self.assertEqual(rows[C.ALL_ROUNDER], Progress(ana.id, C.ALL_ROUNDER, 2))
        self.assertEqual(rows[C.DECATHLETE], Progress(ana.id, C.DECATHLETE, 2))
        self.assertEqual(rows[C.OLYMPUS], Progress(ana.id, C.OLYMPUS, 2))  # Hermes, Apollo

    def test_olympus_counts_the_gods_not_the_disciplines(self):
        # Darts and Petanque are both Artemis's: three disciplines won, two gods.
        ana = self.person("Ana")
        self.win(ana, 2021, Darts, Petanque)
        self.win(ana, 2022, Relay)

        rows = progress_of(ana)
        self.assertEqual(rows[C.ALL_ROUNDER], Progress(ana.id, C.ALL_ROUNDER, 3))
        self.assertEqual(rows[C.OLYMPUS], Progress(ana.id, C.OLYMPUS, 2))

    def test_specialist_shows_the_most_wins_below_the_top_tier(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Relay, Darts)
        self.win(ana, 2023, Relay)
        self.win(ana, 2024, Relay, Petanque)

        self.assertEqual(
            counters_of(ana).wins, {"Relay": (4, 3), "Darts": (2, 1), "Petanque": (1, 3)}
        )
        self.assertEqual(
            progress_of(ana)[C.SPECIALIST], Progress(ana.id, C.SPECIALIST, 2, discipline="Darts")
        )

    def test_specialist_ties_go_to_the_latest_win(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Darts)
        self.win(ana, 2023, Relay)

        self.assertEqual(
            progress_of(ana)[C.SPECIALIST], Progress(ana.id, C.SPECIALIST, 2, discipline="Relay")
        )

    def test_then_to_the_name(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Relay, Darts)

        self.assertEqual(
            progress_of(ana)[C.SPECIALIST], Progress(ana.id, C.SPECIALIST, 2, discipline="Darts")
        )

    def test_every_discipline_at_the_top_tier_shows_the_best(self):
        ana = self.person("Ana")
        for year in (2021, 2022, 2023, 2024):
            self.win(ana, year, Relay, Darts)
        self.win(ana, 2025, Relay)

        self.assertEqual(
            progress_of(ana)[C.SPECIALIST], Progress(ana.id, C.SPECIALIST, 5, discipline="Relay")
        )

    def test_a_discipline_won_twice_in_one_edition_counts_once(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Relay)

        self.assertEqual(
            progress_of(ana)[C.SPECIALIST], Progress(ana.id, C.SPECIALIST, 1, discipline="Relay")
        )

    def test_clean_sweep_shows_the_best_edition_the_latest_among_equals(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts)
        self.win(ana, 2022, Petanque)
        self.win(ana, 2023, Relay, Relay)  # two disciplines of one name: two wins
        self.computed(2024, ana)  # nothing won

        self.assertEqual(counters_of(ana).sweeps, {0: 2, 1: 1, 2: 2})
        self.assertEqual(
            progress_of(ana)[C.CLEAN_SWEEP], Progress(ana.id, C.CLEAN_SWEEP, 2, year=2023)
        )

    def test_clean_sweep_earned_has_no_row(self):
        ana = self.person("Ana")
        self.win(ana, 2021, Relay, Darts, Petanque)
        self.win(ana, 2022, Relay)

        self.assertNotIn(C.CLEAN_SWEEP, progress_of(ana))


# profiles._load (2 + 3 per sequence edition), then games and blindtest guesses; the
# discipline rules read the results compute_standings already loaded (disciplines_of).
BADGES_QUERIES = lambda editions: 4 + 3 * editions  # noqa: E731


class TestQueries(World, TestCase):
    def test_earned_runs_a_fixed_number_of_queries(self):
        # 2021 holds rows for each of the three queries, so a foreign key read per result,
        # game or guess would add queries: a revealed Relay with results, a revealed Rugby
        # round of two played games, and a revealed Blindtest (its save makes the rounds
        # and a guess per team).
        editions = {}
        for year in (2021, 2022, 2023):
            edition, teams = self.edition(year)
            self.seat(self.person(f"P{year}"), edition, teams[0])
            editions[year] = (edition, teams)
        edition, (a, b, c, d) = editions[2021]
        relay = Relay.objects.create(edition=edition, reveal_score=True)
        for team, points in zip((a, b, c, d), (40, 30, 20, 10)):
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)
        rugby = Rugby.objects.create(edition=edition, reveal_score=True)
        round_ = TeamSportRound.objects.create(discipline=rugby, order=1)
        for team1, team2, referees in ((a, b, c), (c, d, a)):
            Game.objects.create(
                discipline=rugby, round=round_, team1=team1, score1=12, team2=team2,
                score2=3, referees=referees, edition=edition, is_played=True,
            )
        Blindtest.objects.create(edition=edition, reveal_score=True)
        BlindtestGuess.objects.filter(team=a).update(is_artist_correct=True, is_song_correct=True)
        self.assertEqual(BlindtestGuess.objects.count(), 40)

        with self.assertNumQueries(BADGES_QUERIES(3)):
            found = earned(TODAY)

        self.assertIn(C.PERFECT_PITCH, {badge.code for badge in found})

    def test_the_progress_adds_no_query(self):
        # Ana, Bob and Chloé share a team in 2021 and 2022, so the comrades tie-break reads
        # the partners' names, and 2021 ranks a revealed Relay, which Ana's team wins.
        ana, bob, chloe = (self.person(n) for n in ("Ana", "Bob", "Chloé"))
        for year in (2021, 2022, 2023):
            edition, teams = self.edition(year)
            for user in (ana, bob, chloe) if year < 2023 else (ana,):
                self.seat(user, edition, teams[0])
            if year == 2021:
                relay = Relay.objects.create(edition=edition, reveal_score=True)
                for team, points in zip(teams, (40, 30, 20, 10)):
                    TeamResult.objects.filter(discipline=relay, team=team).update(points=points)

        with self.assertNumQueries(BADGES_QUERIES(3)):
            found, progress = compute(TODAY)

        self.assertEqual(found, earned(TODAY))
        self.assertIn(Progress(ana.id, C.COMRADES, 2, partner_id=bob.id), progress)
        self.assertIn(Progress(ana.id, C.SPECIALIST, 1, discipline="Relay"), progress)

    def test_an_empty_sequence_costs_only_the_load(self):
        # An unfinished edition with a roster is not in the sequence yet: _load's 2 queries,
        # and no results, games or guesses to read.
        self.edition(2030, finished=False)

        with self.assertNumQueries(2):
            found = earned(TODAY)

        self.assertEqual(found, set())
