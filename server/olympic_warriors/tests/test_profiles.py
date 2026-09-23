"""
Tests for olympic_warriors.profiles: a person's editions, places, averages and leaderboard place,
computed from the edition standings, and the two public endpoints serving them.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from olympic_warriors.models import Edition, Player, Relay, Team, TeamResult
from olympic_warriors.profiles import (
    Participation,
    leaderboard,
    paris_today,
    participations,
    _place,
    _record,
)

TODAY = date(2026, 9, 23)
# The editions query, the players query, then three per finished edition with players
# (2024 and 2025 in ProfilesSetup; 2026 is still running).
PROFILES_QUERIES = 2 + 3 * 2


class TestParisToday(SimpleTestCase):
    def test_is_the_calendar_day_in_paris_not_utc(self):
        instant = datetime(2026, 9, 20, 22, 30, tzinfo=timezone.utc)  # 00:30 on the 21st in Paris
        with mock.patch("olympic_warriors.profiles.datetime") as fake:
            fake.now.side_effect = lambda tz: instant.astimezone(tz)
            self.assertEqual(paris_today(), date(2026, 9, 21))


class ProfilesSetup:
    """
    Three editions seen on TODAY (2026-09-23):
    - 2024, finished and hand-ranked: Aigles 1, Bisons 2, Cerfs 3, Daims 4;
    - 2025, finished and computed from a revealed Relay: Loups 1, Ours 2, Pumas 3;
    - 2026, running until 2026-09-30: Renards and Sangliers.
    People: Ana (Aigles, Loups, Renards), Bob (Bisons, Ours), Chloé (Loups), Dan (Cerfs),
    Eve (Sangliers only) and Fay (2024 without a team).
    """

    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2025 = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.y2026 = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-22", end_date="2026-09-30"
        )
        self.aigles, self.bisons, self.cerfs, self.daims = [
            Team.objects.create(name=name, edition=self.y2024, final_rank=rank)
            for name, rank in [("Aigles", 1), ("Bisons", 2), ("Cerfs", 3), ("Daims", 4)]
        ]
        self.loups, self.ours, self.pumas = [
            Team.objects.create(name=name, edition=self.y2025) for name in ("Loups", "Ours", "Pumas")
        ]
        relay = Relay.objects.create(edition=self.y2025, reveal_score=True)
        for team, points in [(self.loups, 10), (self.ours, 5), (self.pumas, 0)]:
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)
        self.renards, self.sangliers = [
            Team.objects.create(name=name, edition=self.y2026) for name in ("Renards", "Sangliers")
        ]

        self.ana = self.person("Ana", "Lopez")
        self.bob = self.person("Bob", "Martin")
        self.chloe = self.person("Chloé", "Dupont")
        self.dan = self.person("Dan", "Petit")
        self.eve = self.person("Eve", "Adam")
        self.fay = self.person("Fay", "Brun")
        self.play(self.ana, self.y2024, self.aigles)
        self.play(self.ana, self.y2025, self.loups)
        self.play(self.ana, self.y2026, self.renards)
        self.play(self.bob, self.y2024, self.bisons)
        self.play(self.bob, self.y2025, self.ours)
        self.play(self.chloe, self.y2025, self.loups)
        self.play(self.dan, self.y2024, self.cerfs)
        self.play(self.eve, self.y2026, self.sangliers)
        self.play(self.fay, self.y2024)

    @staticmethod
    def person(first_name, last_name):
        """A user whose login and email must never reach a public payload."""
        return User.objects.create(
            username=f"login-{first_name.lower()}",
            email=f"{first_name.lower()}@mail.example",
            first_name=first_name,
            last_name=last_name,
        )

    @staticmethod
    def play(user, edition, team=None, **kwargs):
        return Player.objects.create(user=user, edition=edition, team=team, rating=5, **kwargs)


def summary_of(parts):
    """(year, team name, rank, teams, finished) per participation, for compact asserts."""
    return [(p.year, p.team_name, p.rank, p.teams, p.finished) for p in parts]


class TestParticipations(ProfilesSetup, TestCase):
    def test_one_participation_per_edition_newest_first(self):
        user, parts = participations(TODAY)[self.ana.id]

        self.assertEqual(user, self.ana)
        self.assertEqual(
            summary_of(parts),
            [
                (2026, "Renards", None, 2, False),
                (2025, "Loups", 1, 3, True),
                (2024, "Aigles", 1, 4, True),
            ],
        )
        self.assertEqual(parts[1].team_id, self.loups.id)

    def test_computed_and_hand_ranked_editions_give_the_team_rank(self):
        _, parts = participations(TODAY)[self.bob.id]

        self.assertEqual(summary_of(parts), [(2025, "Ours", 2, 3, True), (2024, "Bisons", 2, 4, True)])

    def test_hand_ranked_team_without_final_rank_has_no_rank(self):
        elans = Team.objects.create(name="Élans", edition=self.y2024)
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024, elans)

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, "Élans", None, 5, True)])

    def test_a_hand_entered_final_rank_of_zero_has_no_rank(self):
        Team.objects.filter(pk=self.aigles.pk).update(final_rank=0)

        _, parts = participations(TODAY)[self.ana.id]

        self.assertEqual(summary_of(parts)[-1], (2024, "Aigles", None, 4, True))

    def test_an_edition_is_finished_from_the_day_after_its_end_date(self):
        _, on_the_last_day = participations(date(2026, 9, 30))[self.eve.id]
        _, the_day_after = participations(date(2026, 10, 1))[self.eve.id]

        self.assertEqual(summary_of(on_the_last_day), [(2026, "Sangliers", None, 2, False)])
        # 2026 has no discipline: finished, but nothing to rank from.
        self.assertEqual(summary_of(the_day_after), [(2026, "Sangliers", None, 2, True)])

    def test_a_player_without_a_team_has_no_team_and_no_rank(self):
        _, parts = participations(TODAY)[self.fay.id]

        self.assertEqual(summary_of(parts), [(2024, None, None, 4, True)])
        self.assertIsNone(parts[0].team_id)

    def test_inactive_players_and_editions_drop_out_and_an_inactive_team_is_no_team(self):
        Player.objects.filter(user=self.chloe).update(is_active=False)
        Edition.objects.filter(pk=self.y2025.pk).update(is_active=False)
        Team.objects.filter(pk=self.cerfs.pk).update(is_active=False)

        result = participations(TODAY)

        self.assertNotIn(self.chloe.id, result)
        self.assertEqual([p.year for p in result[self.ana.id][1]], [2026, 2024])
        self.assertEqual(summary_of(result[self.dan.id][1]), [(2024, None, None, 3, True)])

    def test_a_team_of_another_edition_counts_as_no_team(self):
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024, self.loups)  # objects.create skips Player.clean()

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, None, None, 4, True)])

    def test_duplicate_rows_collapse_to_the_lowest_id_with_a_team(self):
        gus = self.person("Gus", "Roy")
        self.play(gus, self.y2024)
        self.play(gus, self.y2024, self.daims)
        self.play(gus, self.y2024, self.cerfs)

        _, parts = participations(TODAY)[gus.id]

        self.assertEqual(summary_of(parts), [(2024, "Daims", 4, 4, True)])

    def test_someone_who_never_played_is_absent(self):
        root = User.objects.create_superuser("root", "root@mail.example", "pw")

        self.assertNotIn(root.id, participations(TODAY))

    def test_standings_are_computed_for_finished_editions_with_players_only(self):
        # A finished edition nobody played in costs no standings queries.
        empty = Edition.objects.create(
            year=2023, host="Tours", start_date="2023-09-16", end_date="2023-09-17"
        )
        Team.objects.create(name="Vide", edition=empty)

        with self.assertNumQueries(PROFILES_QUERIES):
            participations(TODAY)


class TestLeaderboard(ProfilesSetup, TestCase):
    def rows(self, today=TODAY):
        return {record.first_name: record for record in leaderboard(today)}

    def test_averages_over_counted_editions_only(self):
        rows = self.rows()

        # Ana: 1st of 4 and 1st of 3; the running 2026 is played but not counted.
        self.assertEqual((rows["Ana"].played, rows["Ana"].counted), (3, 2))
        self.assertEqual(rows["Ana"].average_rank, 1.0)
        self.assertFalse(hasattr(rows["Ana"], "average_beaten"))
        # Bob: 2nd of 4 and 2nd of 3.
        self.assertEqual(rows["Bob"].average_rank, 2.0)
        # Dan: 3rd of 4.
        self.assertEqual(rows["Dan"].average_rank, 3.0)

    def test_ranked_like_a_medal_table(self):
        order = [(record.first_name, record.position) for record in leaderboard(TODAY)]

        # Ana has two 1st places, Chloé one, Bob none but two 2nd places, Dan one 3rd.
        # Then the not-ranked-yet group by last name: Adam (Eve), Brun (Fay).
        self.assertEqual(
            order,
            [("Ana", 1), ("Chloé", 2), ("Bob", 3), ("Dan", 4), ("Eve", None), ("Fay", None)],
        )

    def test_places_are_the_counted_ranks_best_first(self):
        rows = self.rows()

        self.assertEqual([(p.year, p.rank) for p in rows["Ana"].places], [(2025, 1), (2024, 1)])
        self.assertEqual([(p.year, p.rank) for p in rows["Bob"].places], [(2025, 2), (2024, 2)])
        self.assertEqual(rows["Eve"].places, ())  # 2026 is still running
        self.assertEqual(rows["Fay"].places, ())  # no team in 2024

    def test_nothing_counted_means_no_figures_and_no_position(self):
        rows = self.rows()

        for name in ("Eve", "Fay"):
            self.assertEqual(rows[name].counted, 0)
            self.assertIsNone(rows[name].average_rank)
            self.assertIsNone(rows[name].position)
        self.assertEqual(rows["Eve"].played, 1)

    def test_an_edition_with_a_single_team_is_not_counted(self):
        solo_year = Edition.objects.create(
            year=2023, host="Tours", start_date="2023-09-16", end_date="2023-09-17"
        )
        solo = Team.objects.create(name="Solo", edition=solo_year, final_rank=1)
        gus = self.person("Gus", "Roy")
        self.play(gus, solo_year, solo)

        gus_row = self.rows()["Gus"]

        self.assertEqual((gus_row.played, gus_row.counted, gus_row.position), (1, 0, None))

    def test_the_running_edition_counts_once_it_is_over(self):
        relay = Relay.objects.create(edition=self.y2026, reveal_score=True)
        for team, points in [(self.renards, 5), (self.sangliers, 0)]:
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)

        rows = self.rows(date(2026, 10, 1))

        # Eve is Sangliers, 2nd of 2.
        self.assertEqual((rows["Eve"].counted, rows["Eve"].average_rank), (1, 2.0))
        # Ana is Renards, 1st of 2, on top of her two other 1st places.
        self.assertEqual((rows["Ana"].counted, rows["Ana"].average_rank), (3, 1.0))

    def test_a_computed_edition_with_nothing_ranked_does_not_count(self):
        # 2026 has no discipline at all: finished but with nothing to rank from.
        rows = self.rows(date(2026, 10, 1))

        self.assertEqual((rows["Eve"].counted, rows["Eve"].position), (0, None))

    def test_a_computed_edition_with_results_but_none_ranked_does_not_count(self):
        # A discipline exists with scores entered, but nothing was revealed: still
        # nothing to rank from, same as no discipline at all.
        relay = Relay.objects.create(edition=self.y2026, reveal_score=False)
        for team, points in [(self.renards, 5), (self.sangliers, 0)]:
            TeamResult.objects.filter(discipline=relay, team=team).update(points=points)

        result = participations(date(2026, 10, 1))
        self.assertIsNone(result[self.eve.id][1][0].rank)
        self.assertIsNone(result[self.ana.id][1][0].rank)  # 2026 sorts first, newest year

        rows = self.rows(date(2026, 10, 1))
        self.assertEqual((rows["Eve"].counted, rows["Eve"].position), (0, None))
        self.assertEqual(rows["Ana"].counted, 2)

    def test_query_budget_matches_participations(self):
        with self.assertNumQueries(PROFILES_QUERIES):
            leaderboard(TODAY)


class TestRecordAndPlace(SimpleTestCase):
    """`_record` and `_place` work on plain values, no database needed."""

    @staticmethod
    def user(user_id, first_name, last_name):
        return SimpleNamespace(id=user_id, first_name=first_name, last_name=last_name)

    @staticmethod
    def parts(*ranks_by_year):
        """Counted participations from (year, rank) pairs, each in a 10-team edition."""
        return tuple(
            Participation(year, None, None, rank, 10, True) for year, rank in ranks_by_year
        )

    def placed(self, *records):
        return [(record.first_name, record.position) for record in _place(list(records))]

    def test_one_first_place_beats_any_number_of_second_places(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 2), (2023, 2), (2022, 2)))

        self.assertEqual(self.placed(b, a), [("A", 1), ("B", 2)])

    def test_an_extra_lower_place_counts_in_a_persons_favour(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 1), (2023, 5)))

        self.assertEqual(self.placed(a, b), [("B", 1), ("A", 2)])

    def test_more_of_a_lower_place_breaks_a_tie_on_the_better_ones(self):
        a = _record(self.user(1, "A", "Aa"), self.parts((2024, 1), (2023, 3)))
        b = _record(self.user(2, "B", "Bb"), self.parts((2024, 1), (2023, 2)))

        self.assertEqual(self.placed(a, b), [("B", 1), ("A", 2)])

    def test_identical_places_share_a_position_listed_by_name(self):
        zoe = _record(self.user(1, "Zoé", "Zola"), self.parts((2024, 1), (2022, 3)))
        ada = _record(self.user(2, "Ada", "Adam"), self.parts((2023, 3), (2021, 1)))
        max_ = _record(self.user(3, "Max", "Mars"), self.parts((2024, 2)))

        self.assertEqual(self.placed(zoe, max_, ada), [("Ada", 1), ("Zoé", 1), ("Max", 3)])

    def test_places_are_best_first_then_newest_first_and_skip_uncounted(self):
        parts = (
            Participation(2025, None, None, None, 6, False),  # running
            Participation(2024, None, None, 2, 6, True),
            Participation(2023, None, None, 1, 6, True),
            Participation(2022, None, None, 2, 6, True),
        )

        record = _record(self.user(4, "R", "Roy"), parts)

        self.assertEqual(
            [(p.year, p.rank) for p in record.places], [(2023, 1), (2024, 2), (2022, 2)]
        )

    def test_average_rank_can_be_fractional(self):
        user = self.user(3, "R", "Roy")
        parts = (
            Participation(2024, None, None, 1, 4, True),
            Participation(2023, None, None, 2, 4, True),
            Participation(2022, None, None, 2, 4, True),
        )

        record = _record(user, parts)

        self.assertEqual(record.average_rank, 1.7)

    def test_an_accented_last_name_sorts_with_its_base_letter(self):
        # Ébert belongs between Durand and Faure: a key that merely dropped the accented
        # character (rather than decomposing it to "e") would instead sort it first.
        durand = self.user(4, "A", "Durand")
        ebert = self.user(5, "B", "Ébert")
        faure = self.user(6, "C", "Faure")
        # None of them count (no participations): all land in the waiting group, by name.
        placed = _place([_record(faure, ()), _record(durand, ()), _record(ebert, ())])

        self.assertEqual([record.last_name for record in placed], ["Durand", "Ébert", "Faure"])


class TestProfileEndpoints(ProfilesSetup, TestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("olympic_warriors.profiles.paris_today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = APIClient()  # no credentials: both endpoints are public

    def test_leaderboard_is_public_and_ordered(self):
        response = self.client.get("/profiles/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["first_name"] for row in response.data],
            ["Ana", "Chloé", "Bob", "Dan", "Eve", "Fay"],
        )
        self.assertEqual(
            response.data[0],
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "played": 3,
                "counted": 2,
                "average_rank": 1.0,
                "places": [{"year": 2025, "rank": 1}, {"year": 2024, "rank": 1}],
                "position": 1,
            },
        )
        self.assertNotIn("average_beaten", response.data[0])
        self.assertEqual(response.data[1]["position"], 2)  # Chloé: one 1st place
        self.assertEqual(response.data[1]["average_rank"], 1.0)
        self.assertEqual((response.data[4]["places"], response.data[4]["position"]), ([], None))
        self.assertIsNone(response.data[4]["average_rank"])

    def test_profile_lists_every_edition_newest_first(self):
        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {k: v for k, v in response.data.items() if k != "editions"},
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "position": 1,
                "counted": 2,
                "average_rank": 1.0,
            },
        )
        self.assertNotIn("average_beaten", response.data)
        self.assertEqual(
            response.data["editions"],
            [
                {
                    "year": 2026,
                    "team": {"id": self.renards.id, "name": "Renards"},
                    "rank": None,
                    "teams": 2,
                    "finished": False,
                },
                {
                    "year": 2025,
                    "team": {"id": self.loups.id, "name": "Loups"},
                    "rank": 1,
                    "teams": 3,
                    "finished": True,
                },
                {
                    "year": 2024,
                    "team": {"id": self.aigles.id, "name": "Aigles"},
                    "rank": 1,
                    "teams": 4,
                    "finished": True,
                },
            ],
        )

    def test_profile_without_a_team_or_a_counted_edition(self):
        response = self.client.get(f"/profile/{self.fay.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["position"])
        self.assertIsNone(response.data["average_rank"])
        self.assertEqual(
            response.data["editions"],
            [{"year": 2024, "team": None, "rank": None, "teams": 4, "finished": True}],
        )

    def test_404_for_someone_who_never_played_and_for_an_unknown_id(self):
        root = User.objects.create_superuser("root", "root@mail.example", "pw")

        self.assertEqual(self.client.get(f"/profile/{root.id}/").status_code, 404)
        self.assertEqual(self.client.get("/profile/999999/").status_code, 404)

    def test_payloads_carry_no_login_name_or_email(self):
        for url in ("/profiles/", f"/profile/{self.ana.id}/"):
            content = self.client.get(url).content
            self.assertNotIn(b"login-", content)
            self.assertNotIn(b"mail.example", content)
            self.assertNotIn(b"username", content)
            self.assertNotIn(b"email", content)

    def test_both_endpoints_run_in_a_fixed_number_of_queries(self):
        with self.assertNumQueries(PROFILES_QUERIES):
            self.assertEqual(self.client.get("/profiles/").status_code, 200)
        with self.assertNumQueries(PROFILES_QUERIES):
            self.assertEqual(self.client.get(f"/profile/{self.ana.id}/").status_code, 200)
