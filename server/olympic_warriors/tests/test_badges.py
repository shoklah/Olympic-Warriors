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
from olympic_warriors.models import Badge, Edition, Player, Team

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
        e2025, t2025 = self.edition(2025, size=4)
        gus = self.person("Gus")
        self.seat(gus, e2025, t2025[3])

        self.assertEqual(places_of(gus), [(C.WOODEN_SPOON, 2025)])

    def test_chocolate_is_never_the_last_place(self):
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 3, 4, 4])
        gus, hugo = self.person("Gus"), self.person("Hugo")
        self.seat(gus, e2025, t2025[3])
        self.seat(hugo, e2025, t2025[4])

        self.assertEqual(places_of(gus), [(C.WOODEN_SPOON, 2025)])
        self.assertEqual(places_of(hugo), [(C.WOODEN_SPOON, 2025)])

    def test_the_spoon_needs_four_teams(self):
        e2025, t2025 = self.edition(2025, size=3)
        gus = self.person("Gus")
        self.seat(gus, e2025, t2025[2])

        self.assertEqual(places_of(gus), [(C.BRONZE, 2025)])

    def test_the_spoon_needs_a_complete_ranking(self):
        e2025, t2025 = self.edition(2025, ranks=[1, 2, 3, None])
        # Below the podium too, so only the missing rank refuses the spoon.
        e2026, t2026 = self.edition(2026, ranks=[1, 2, 3, 4, None])
        gus, hugo = self.person("Gus"), self.person("Hugo")
        self.seat(gus, e2025, t2025[2])
        self.seat(hugo, e2026, t2026[3])

        self.assertEqual(years_of(gus, C.WOODEN_SPOON), [])
        self.assertEqual(years_of(hugo, C.WOODEN_SPOON), [])

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
