"""
The badge showcase (see the player profile customization design spec under
docs/superpowers/specs/, "Showcase"): badges.showcase() turns a person's badges, their
stored pins and the rarity counts into the three badges their profile shows, with no query;
badges.badges_by_user() reads many people's badges in the shape profile_badges() gives one
person; profiles.person_ids() is the leaderboard's people without computing the leaderboard,
the denominator of the rarity counts the automatic showcase reads.
"""

from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from olympic_warriors.badges import badges_by_user, profile_badges, showcase
from olympic_warriors.models import Badge, Edition
from olympic_warriors.profiles import is_person, leaderboard, person_ids
from olympic_warriors.tests.test_profiles import TODAY, ProfilesSetup

C = Badge.Codes


def entry(code, tier=0, years=(2024,), discipline=None, partner=None):
    """A profile_badges entry."""
    return {
        "code": code, "tier": tier, "years": list(years), "discipline": discipline,
        "partner": partner,
    }


def shown(code, tier=0, discipline=None):
    """A showcase badge."""
    return {"code": code, "tier": tier, "discipline": discipline}


def comrade(pk, first_name):
    return {"id": pk, "first_name": first_name, "last_name": "Martin"}


class TestShowcase(SimpleTestCase):
    """showcase(entries, pins, holders): pure, so a SimpleTestCase (no database) runs it.
    The entries come in catalogue order, as profile_badges() returns them."""

    ENTRIES = [
        entry(C.CHAMPION, years=(2024, 2025)),
        entry(C.ROOKIE),
        entry(C.VETERAN, tier=2, years=(2024, 2025)),
        entry(C.GOAT),
        entry(C.SPECIALIST, tier=1, discipline="Darts"),
        entry(C.MVP),
    ]
    HOLDERS = {C.CHAMPION: 5, C.ROOKIE: 40, C.VETERAN: 12, C.GOAT: 1, C.SPECIALIST: 3, C.MVP: 2}

    def test_the_pins_come_in_the_persons_order(self):
        self.assertEqual(
            showcase(self.ENTRIES, [C.ROOKIE, C.CHAMPION, C.VETERAN], self.HOLDERS),
            {
                "auto": False,
                "badges": [shown(C.ROOKIE), shown(C.CHAMPION), shown(C.VETERAN, tier=2)],
            },
        )

    def test_one_or_two_pins_are_a_pinned_showcase_of_one_or_two(self):
        self.assertEqual(
            showcase(self.ENTRIES, [C.ROOKIE], self.HOLDERS),
            {"auto": False, "badges": [shown(C.ROOKIE)]},
        )

    def test_a_pin_no_longer_earned_falls_out_and_the_others_keep_their_order(self):
        self.assertEqual(
            showcase(self.ENTRIES, [C.ROOKIE, C.LEGEND, C.CHAMPION], self.HOLDERS),
            {"auto": False, "badges": [shown(C.ROOKIE), shown(C.CHAMPION)]},
        )

    def test_a_pin_outside_the_catalogue_falls_out(self):
        self.assertEqual(
            showcase(self.ENTRIES, ["golden-whistle", C.GOAT], self.HOLDERS),
            {"auto": False, "badges": [shown(C.GOAT)]},
        )

    def test_pins_none_of_which_is_earned_give_the_automatic_showcase(self):
        self.assertEqual(
            showcase(self.ENTRIES, [C.LEGEND, C.DYNASTY], self.HOLDERS),
            showcase(self.ENTRIES, [], self.HOLDERS),
        )
        self.assertTrue(showcase(self.ENTRIES, [C.LEGEND], self.HOLDERS)["auto"])

    def test_automatic_is_the_three_rarest_earned_codes(self):
        self.assertEqual(
            showcase(self.ENTRIES, [], self.HOLDERS),
            {
                "auto": True,
                "badges": [shown(C.GOAT), shown(C.MVP), shown(C.SPECIALIST, 1, "Darts")],
            },
        )

    def test_equally_rare_codes_go_to_the_higher_tier_held(self):
        holders = {C.CHAMPION: 4, C.ROOKIE: 4, C.VETERAN: 4, C.SPECIALIST: 4}
        entries = [
            entry(C.CHAMPION),
            entry(C.ROOKIE),
            entry(C.VETERAN, tier=1),
            entry(C.SPECIALIST, tier=1, discipline="Darts"),
            entry(C.SPECIALIST, tier=3, discipline="Relay"),
        ]

        self.assertEqual(
            showcase(entries, [], holders)["badges"],
            [shown(C.SPECIALIST, 3, "Relay"), shown(C.VETERAN, 1), shown(C.CHAMPION)],
        )

    def test_equally_rare_codes_of_the_same_tier_go_by_catalogue_order(self):
        holders = {C.MVP: 2, C.GOAT: 2, C.ROOKIE: 2, C.CHAMPION: 2}
        entries = [entry(C.CHAMPION), entry(C.ROOKIE), entry(C.GOAT), entry(C.MVP)]

        self.assertEqual(
            [badge["code"] for badge in showcase(entries, [], holders)["badges"]],
            [C.CHAMPION, C.ROOKIE, C.GOAT],
        )

    def test_a_code_without_a_holder_count_is_the_rarest(self):
        entries = [entry(C.CHAMPION), entry(C.ROOKIE), entry(C.GOAT), entry(C.MVP)]

        badges = showcase(entries, [], {C.CHAMPION: 1, C.GOAT: 2})["badges"]

        self.assertEqual([badge["code"] for badge in badges], [C.ROOKIE, C.MVP, C.CHAMPION])

    def test_fewer_than_three_earned_codes_show_them_all(self):
        self.assertEqual(
            showcase([entry(C.ROOKIE)], [], {C.ROOKIE: 9}),
            {"auto": True, "badges": [shown(C.ROOKIE)]},
        )

    def test_nothing_earned_is_an_empty_automatic_showcase(self):
        self.assertEqual(showcase([], [], {}), {"auto": True, "badges": []})
        self.assertEqual(showcase([], [C.GOAT], {}), {"auto": True, "badges": []})

    def test_a_code_is_drawn_from_its_entry_with_the_highest_tier(self):
        entries = [
            entry(C.SPECIALIST, tier=1, discipline="Darts"),
            entry(C.SPECIALIST, tier=2, discipline="Relay"),
            entry(C.SPECIALIST, tier=1, discipline="Rugby"),
        ]

        self.assertEqual(
            showcase(entries, [C.SPECIALIST], {})["badges"],
            [shown(C.SPECIALIST, 2, "Relay")],
        )

    def test_equal_tiers_draw_the_first_entry(self):
        entries = [
            entry(C.SPECIALIST, tier=2, discipline="Darts"),
            entry(C.SPECIALIST, tier=2, discipline="Relay"),
        ]

        self.assertEqual(
            showcase(entries, [C.SPECIALIST], {})["badges"],
            [shown(C.SPECIALIST, 2, "Darts")],
        )

    def test_an_untiered_code_draws_its_first_entry_and_carries_no_partner(self):
        entries = [
            entry(C.COMRADES, partner=comrade(7, "Bob")),
            entry(C.COMRADES, partner=comrade(3, "Ana")),
        ]

        self.assertEqual(showcase(entries, [], {C.COMRADES: 2})["badges"], [shown(C.COMRADES)])

    def test_a_code_is_shown_once_however_many_entries_or_pins_it_has(self):
        entries = [
            entry(C.SPECIALIST, tier=1, discipline="Darts"),
            entry(C.SPECIALIST, tier=1, discipline="Relay"),
            entry(C.GOAT),
        ]

        self.assertEqual(
            [b["code"] for b in showcase(entries, [], {})["badges"]], [C.SPECIALIST, C.GOAT]
        )
        self.assertEqual(
            [b["code"] for b in showcase(entries, [C.GOAT, C.GOAT], {})["badges"]], [C.GOAT]
        )

    def test_at_most_three_badges_whatever_is_stored(self):
        pins = [C.CHAMPION, C.ROOKIE, C.VETERAN, C.GOAT]

        self.assertEqual(len(showcase(self.ENTRIES, pins, self.HOLDERS)["badges"]), 3)

    def test_the_arguments_are_left_as_they_were(self):
        entries = [dict(e) for e in self.ENTRIES]
        pins, holders = [C.LEGEND, C.GOAT], dict(self.HOLDERS)

        showcase(entries, pins, holders)
        showcase(entries, [], holders)

        self.assertEqual(
            (entries, pins, holders), (self.ENTRIES, [C.LEGEND, C.GOAT], self.HOLDERS)
        )


class TestBadgesByUser(TestCase):
    """badges_by_user(user_ids): profile_badges() for many people in one query."""

    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2025 = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.hidden = Edition.objects.create(
            year=2023, host="Brest", start_date="2023-09-23", end_date="2023-09-24",
            is_active=False,
        )
        self.ana, self.bob, self.chloe, self.dan = [
            User.objects.create(username=name.lower(), first_name=name, last_name="Martin")
            for name in ("Ana", "Bob", "Chloé", "Dan")
        ]
        badge = Badge.objects.create
        badge(user=self.ana, code=C.CHAMPION, edition=self.y2025)
        badge(user=self.ana, code=C.CHAMPION, edition=self.y2024)
        badge(user=self.ana, code=C.VETERAN, edition=self.y2025, tier=2)
        badge(user=self.ana, code=C.SPECIALIST, edition=self.y2024, tier=1, discipline="Relay")
        badge(user=self.ana, code=C.COMRADES, edition=self.y2025, partner=self.bob)
        badge(user=self.ana, code=C.MVP, edition=self.y2025, is_manual=True, note="memo")
        badge(user=self.ana, code=C.GOAT, edition=self.y2025, is_active=False)
        badge(user=self.ana, code=C.ROOKIE, edition=self.hidden)
        badge(user=self.bob, code=C.COMRADES, edition=self.y2025, partner=self.ana)
        badge(user=self.bob, code=C.ROOKIE, edition=self.y2024)
        badge(user=self.dan, code=C.ROOKIE, edition=self.y2024)  # not asked for below

    def test_each_person_gets_exactly_their_profile_badges(self):
        people = [self.ana, self.bob, self.chloe]
        by_user = badges_by_user([user.id for user in people])

        self.assertEqual(set(by_user), {user.id for user in people})
        for user in people:
            with self.subTest(user=user.first_name):
                self.assertEqual(by_user[user.id], profile_badges(user.id))
        self.assertEqual(
            [badge["code"] for badge in by_user[self.ana.id]],
            [C.CHAMPION, C.VETERAN, C.COMRADES, C.SPECIALIST, C.MVP],
        )
        self.assertEqual(
            by_user[self.ana.id][0],
            {"code": C.CHAMPION, "tier": 0, "years": [2024, 2025], "discipline": None,
             "partner": None},
        )
        self.assertEqual(by_user[self.chloe.id], [])

    def test_one_query_for_any_number_of_people(self):
        ids = [self.ana.id, self.bob.id, self.chloe.id, self.dan.id]

        with self.assertNumQueries(1):  # the partner's names included
            partner = badges_by_user(ids)[self.ana.id][2]["partner"]

        self.assertEqual(partner, {"id": self.bob.id, "first_name": "Bob", "last_name": "Martin"})
        with self.assertNumQueries(1):
            profile_badges(self.ana.id)

    def test_no_one_asked_for_is_no_one_answered(self):
        self.assertEqual(badges_by_user([]), {})


class TestPersonIds(ProfilesSetup, TestCase):
    """person_ids(): the leaderboard's people (a user with an active Player in an active
    edition, see profiles._load), in one query and without computing the leaderboard."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("olympic_warriors.profiles.paris_today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        hidden = Edition.objects.create(
            year=2023, host="Brest", start_date="2023-09-23", end_date="2023-09-24",
            is_active=False,
        )
        # Only a player of an inactive edition, only an inactive player, never a player.
        self.retired = self.person("Rémi", "Petit")
        self.play(self.retired, hidden)
        self.benched = self.person("Bea", "Roux")
        self.play(self.benched, self.y2025, self.loups, is_active=False)
        self.stranger = self.person("Sam", "Blanc")
        User.objects.create_user("orga", is_staff=True)
        # Two rows in one edition, one inactive, and one row of an inactive edition: once.
        self.play(self.bob, self.y2025, is_active=False)
        self.play(self.bob, hidden)

    def test_the_leaderboards_people_exactly(self):
        ids = person_ids()

        self.assertEqual(ids, sorted(record.user_id for record in leaderboard()))
        people = (self.ana, self.bob, self.chloe, self.dan, self.eve, self.fay)
        self.assertEqual(ids, sorted(user.id for user in people))

    def test_one_query(self):
        with self.assertNumQueries(1):
            person_ids()

    def test_is_person_agrees(self):
        ids = set(person_ids())
        for user in User.objects.all():
            with self.subTest(user=user.username):
                self.assertEqual(is_person(user), user.id in ids)

    def test_a_later_edition_joins_its_people(self):
        y2027 = Edition.objects.create(
            year=2027, host="Lille", start_date="2027-09-18", end_date="2027-09-19"
        )
        self.play(self.stranger, y2027)

        self.assertIn(self.stranger.id, person_ids())
        self.assertEqual(person_ids(), sorted(r.user_id for r in leaderboard(date(2027, 1, 1))))
