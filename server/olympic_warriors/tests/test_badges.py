"""
Tests for olympic_warriors.badges: every computed badge rule, read through earned() on
small histories. Hand-ranked editions (Team.final_rank) make the place, streak, loyalty,
teammate and hall of fame histories quick to build; discipline and game rules use
revealed disciplines with results and games.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.badges import earned, history
from olympic_warriors.models import Badge, Edition, Player, Relay, Team, TeamResult

C = Badge.Codes
TODAY = date(2031, 1, 1)
PLACE_CODES = (C.CHAMPION, C.RUNNER_UP, C.BRONZE, C.CHOCOLATE, C.WOODEN_SPOON)


class World:
    """Builds histories: finished editions whose teams are hand-ranked, and people on them."""

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

    def test_full_set(self):
        ana = self.person("Ana")
        self.play(ana, [3, 1, 2])

        self.assertEqual(years_of(ana, C.FULL_SET), [2023])

    def test_no_full_set_without_a_third_place(self):
        ana = self.person("Ana")
        self.play(ana, [1, 2])

        self.assertEqual(years_of(ana, C.FULL_SET), [])

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

    def test_comeback_from_last_to_the_podium(self):
        ana = self.person("Ana")
        self.play(ana, [6, 3])

        self.assertEqual(years_of(ana, C.COMEBACK), [2022])

    def test_no_comeback_across_a_missed_edition(self):
        ana = self.person("Ana")
        self.play(ana, [6, None, 1])

        self.assertEqual(years_of(ana, C.COMEBACK), [])

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


LOYALTY_CODES = (
    C.ROOKIE,
    C.VETERAN,
    C.ARGONAUT,
    C.EVER_PRESENT,
    C.HOMECOMING,
    C.GLOBETROTTER,
)


def tiers_of(user, code, today=TODAY):
    """The (year, tier) pairs at which the user earned `code`, sorted."""
    return sorted((year, tier) for c, year, tier, *_ in badges_of(user, today) if c == code)


class TestLoyalty(World, TestCase):
    def tour(self, user, hosts):
        """Seat `user` on a team in consecutive editions from 2021, held at `hosts`."""
        for year, host in zip(range(2021, 2021 + len(hosts)), hosts):
            edition, teams = self.edition(year, host=host)
            self.seat(user, edition, teams[0])

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

    def test_hosts_match_whatever_the_case_and_spaces(self):
        ana = self.person("Ana")
        self.tour(ana, ["Paris", " paris ", "Nantes"])

        self.assertEqual(years_of(ana, C.GLOBETROTTER), [])

    def test_globetrotter_at_the_third_host(self):
        ana = self.person("Ana")
        self.tour(ana, ["Paris", " paris ", "Nantes", "Lyon"])

        self.assertEqual(years_of(ana, C.GLOBETROTTER), [2024])

    def test_a_fourth_host_earns_nothing_more(self):
        ana = self.person("Ana")
        self.tour(ana, ["Paris", " paris ", "Nantes", "Lyon", "Marseille"])

        self.assertEqual(years_of(ana, C.GLOBETROTTER), [2024])

    def test_hosts_match_whatever_the_accents(self):
        ana = self.person("Ana")
        self.tour(ana, ["Orléans", "Orleans", "Paris"])

        self.assertEqual(years_of(ana, C.GLOBETROTTER), [])


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

    def crowd(self, year):
        """Ten new people."""
        return [self.person(f"Mate{year}-{n}") for n in range(10)]

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

    def test_networker_at_twenty_teammates(self):
        self.meet(2021, self.crowd(2021))
        self.meet(2022, self.crowd(2022))

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2022, 1)])

    def test_networker_tiers_at_forty_and_sixty(self):
        for year in range(2021, 2027):
            self.meet(year, self.crowd(year))

        self.assertEqual(tiers_of(self.ana, C.NETWORKER), [(2022, 1), (2024, 2), (2026, 3)])

    def test_meeting_the_same_people_again_adds_nothing(self):
        mates = self.crowd(2021)
        self.meet(2021, mates)
        self.meet(2022, mates)
        self.meet(2023, self.crowd(2023))

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

    def test_the_first_edition_gives_nothing(self):
        # A second edition in the sequence, but nothing counted in it: still no table.
        ana = self.person("Ana")
        self.play(ana, [1, None])

        self.assertEqual([b for b in badges_of(ana) if b[0] in FAME_CODES], [])

    def test_goat_from_the_second_edition(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 2])  # places 1, 2: 1st
        self.play(bob, [None, 1])  # place 1: 2nd

        self.assertEqual(years_of(ana, C.GOAT), [2022])
        self.assertEqual(years_of(bob, C.GOAT), [])

    def test_goat_once_even_when_shared(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 1, 1])
        self.play(bob, [1, 1, 1])  # the same team: the same places

        self.assertEqual(years_of(ana, C.GOAT), [2022])
        self.assertEqual(years_of(bob, C.GOAT), [2022])
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

    def test_kingslayer_takes_the_top_from_someone_else(self):
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 3, 4])  # 2022 table: (1, 3) 1st; 2023: (1, 3, 4) 2nd
        self.play(bob, [2, 2, 1])  # 2022 table: (2, 2) 2nd; 2023: (1, 2, 2) 1st

        self.assertEqual(years_of(bob, C.KINGSLAYER), [2023])
        self.assertEqual(years_of(ana, C.KINGSLAYER), [])

    def test_no_kingslayer_at_the_first_table(self):
        # Ana tops the 2021 ranking, Bob the 2022 table, but 2021 alone is not a table.
        ana, bob = self.person("Ana"), self.person("Bob")
        self.play(ana, [1, 3])
        self.play(bob, [2, 1])

        self.assertEqual(years_of(bob, C.GOAT), [2022])
        self.assertEqual(years_of(bob, C.KINGSLAYER), [])

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
