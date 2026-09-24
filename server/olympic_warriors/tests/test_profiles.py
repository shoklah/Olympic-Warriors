"""
Tests for olympic_warriors.profiles: a person's editions, places, averages and leaderboard place,
computed from the edition standings, and the two public endpoints serving them, the profile
with its badges (badges.profile_badges) and rarity stats (badges.badge_stats).
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from olympic_warriors import badges as badges_module
from olympic_warriors.badges import badge_stats
from olympic_warriors.models import (
    Badge,
    Darts,
    Discipline,
    Edition,
    HideAndSeek,
    Player,
    Relay,
    Team,
    TeamResult,
)
from olympic_warriors.profiles import (
    DisciplinePlace,
    DisciplinePlaces,
    Participation,
    discipline_table,
    held_disciplines,
    leaderboard,
    paris_today,
    participations,
    profile_record,
    _discipline_places,
    _load,
    _place,
    _record,
)

TODAY = date(2026, 9, 23)
# The editions query, the players query, then three per finished edition with players
# (2024 and 2025 in ProfilesSetup; 2026 is still running).
PROFILES_QUERIES = 2 + 3 * 2
# The discipline's name, the active editions holding it, their players, then three per such
# edition with players (2024 and 2025 for DisciplinesSetup's Relay).
DISCIPLINE_TABLE_QUERIES = 1 + 2 + 3 * 2


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
        self.relay2025 = Relay.objects.create(edition=self.y2025, reveal_score=True)
        for team, points in [(self.loups, 10), (self.ours, 5), (self.pumas, 0)]:
            TeamResult.objects.filter(discipline=self.relay2025, team=team).update(points=points)
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


class TestLoad(ProfilesSetup, TestCase):
    def test_exposes_the_data_participations_reads(self):
        loaded = _load(TODAY)

        self.assertEqual(set(loaded.editions), {self.y2024.id, self.y2025.id, self.y2026.id})
        self.assertEqual(loaded.editions[self.y2024.id].team_count, 4)
        self.assertEqual(loaded.finished, {self.y2024.id, self.y2025.id})
        # Standings only for finished editions with a player, and both of those rank.
        self.assertEqual(set(loaded.standings), {self.y2024.id, self.y2025.id})
        self.assertEqual(loaded.ranked, {self.y2024.id, self.y2025.id})
        self.assertEqual(loaded.chosen[(self.ana.id, self.y2025.id)].team_id, self.loups.id)


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


class DisciplinesSetup(ProfilesSetup):
    """
    On top of ProfilesSetup's revealed 2025 Relay (Loups 1, Ours 2, Pumas 3): a revealed
    2024 Relay (Bisons 1, Aigles 2, Cerfs 3, Daims 4), a revealed 2024 Darts (Aigles 1,
    Bisons 2, Cerfs 3, Daims 4), a hidden 2025 Darts (Loups 1, Ours 2), and a revealed 2026
    Darts in the running edition (Renards 1, Sangliers 2).
    """

    def setUp(self):
        super().setUp()
        self.relay2024 = Relay.objects.create(edition=self.y2024, reveal_score=True)
        for team, points in [(self.bisons, 8), (self.aigles, 5), (self.cerfs, 1), (self.daims, 0)]:
            TeamResult.objects.filter(discipline=self.relay2024, team=team).update(points=points)
        self.darts2024 = Darts.objects.create(edition=self.y2024, reveal_score=True)
        for team, points in [(self.aigles, 9), (self.bisons, 4), (self.cerfs, 2), (self.daims, 1)]:
            TeamResult.objects.filter(discipline=self.darts2024, team=team).update(points=points)
        self.hidden_darts = Darts.objects.create(edition=self.y2025, reveal_score=False)
        for team, points in [(self.loups, 9), (self.ours, 3)]:
            TeamResult.objects.filter(discipline=self.hidden_darts, team=team).update(points=points)
        self.running_darts = Darts.objects.create(edition=self.y2026, reveal_score=True)
        for team, points in [(self.renards, 9), (self.sangliers, 4)]:
            TeamResult.objects.filter(discipline=self.running_darts, team=team).update(points=points)


class TestDisciplinePlaces(DisciplinesSetup, TestCase):
    """A profile's places per discipline (profile_record): every revealed result of the
    person's teams, running editions included, whether or not the participation counts."""

    def record(self, first_name):
        user = User.objects.get(first_name=first_name)
        return profile_record(user.id, TODAY)[1]

    def disciplines(self, first_name):
        return [
            (d.name, d.position, [(p.year, p.rank) for p in d.places])
            for d in self.record(first_name).disciplines
        ]

    def test_places_aggregate_by_name_best_first_and_order_like_a_medal_table(self):
        # Ana: Darts 1st in the running 2026 and in 2024 (the hidden 2025 Darts gives
        # nothing), Relay 1st in 2025 and 2nd in 2024. Two 1st places beat a 1st and a 2nd.
        self.assertEqual(
            self.disciplines("Ana"),
            [("Darts", 1, [(2026, 1), (2024, 1)]), ("Relay", 2, [(2025, 1), (2024, 2)])],
        )

    def test_bob_places(self):
        # Bob: Relay 1st in 2024 and 2nd in 2025; Darts 2nd in 2024. An extra lower place
        # puts Relay first.
        self.assertEqual(
            self.disciplines("Bob"),
            [("Relay", 1, [(2024, 1), (2025, 2)]), ("Darts", 2, [(2024, 2)])],
        )

    def test_identical_places_share_a_position_listed_by_name(self):
        # Dan (Cerfs 2024): Relay 3rd and Darts 3rd: tied, listed by name.
        self.assertEqual(
            self.disciplines("Dan"), [("Darts", 1, [(2024, 3)]), ("Relay", 1, [(2024, 3)])]
        )

    def test_a_running_edition_gives_its_revealed_places(self):
        # Eve (Sangliers) plays the running 2026 only: 2nd in its revealed Darts.
        self.assertEqual(self.disciplines("Eve"), [("Darts", 1, [(2026, 2)])])

    def test_no_team_means_no_disciplines(self):
        self.assertEqual(self.disciplines("Fay"), [])  # no team in 2024

    def test_an_uncontested_discipline_gives_no_place(self):
        # Sangliers not scored yet: Renards' lone score beats nobody. A revealed 2026 Relay
        # with both teams at 0 (as before any game) ties everyone for 1st on nothing.
        TeamResult.objects.filter(discipline=self.running_darts, team=self.sangliers).update(
            points=None
        )
        relay = Relay.objects.create(edition=self.y2026, reveal_score=True)
        TeamResult.objects.filter(discipline=relay).update(points=0)

        self.assertEqual(self.disciplines("Eve"), [])
        self.assertEqual(
            self.disciplines("Ana"),
            [("Relay", 1, [(2025, 1), (2024, 2)]), ("Darts", 2, [(2024, 1)])],
        )

    def test_a_participation_that_does_not_count_still_gives_its_places(self):
        # Without a final_rank, Aigles have no rank in hand-ranked 2024: Ana's 2024 no
        # longer counts for the leaderboard, but its revealed results still show.
        Team.objects.filter(pk=self.aigles.pk).update(final_rank=None)

        ana = self.record("Ana")

        self.assertEqual(ana.counted, 1)
        self.assertEqual(
            [(d.name, [(p.year, p.rank) for p in d.places]) for d in ana.disciplines],
            [("Darts", [(2026, 1), (2024, 1)]), ("Relay", [(2025, 1), (2024, 2)])],
        )

    def test_running_places_leave_the_leaderboard_figures_alone(self):
        records, ana = profile_record(self.ana.id, TODAY)
        on_the_leaderboard = next(r for r in leaderboard(TODAY) if r.user_id == self.ana.id)

        self.assertEqual([r.user_id for r in records], [r.user_id for r in leaderboard(TODAY)])
        self.assertEqual(
            (ana.position, ana.places, ana.counted, ana.average_rank),
            (
                on_the_leaderboard.position,
                on_the_leaderboard.places,
                on_the_leaderboard.counted,
                on_the_leaderboard.average_rank,
            ),
        )

    def test_someone_who_never_played_has_no_record(self):
        root = User.objects.create_superuser("root", "root@mail.example", "pw")

        records, record = profile_record(root.id, TODAY)

        self.assertIsNone(record)
        self.assertEqual(len(records), 6)

    def test_latest_is_the_newest_place_with_its_discipline_row(self):
        # Bob's best Relay place is 2024, but the newest is 2025, whose page the profile
        # links to; Ana's newest Darts place is the running edition's.
        relay, darts = self.record("Bob").disciplines
        ana_darts = self.record("Ana").disciplines[0]

        self.assertEqual(relay.places[0].year, 2024)
        self.assertEqual((relay.latest.year, relay.latest.discipline_id), (2025, self.relay2025.id))
        self.assertEqual((darts.latest.year, darts.latest.discipline_id), (2024, self.darts2024.id))
        self.assertEqual(
            (ana_darts.latest.year, ana_darts.latest.discipline_id), (2026, self.running_darts.id)
        )

    def test_query_budget(self):
        # The leaderboard's, plus three per running edition the person has a team in:
        # Ana plays 2026, Bob does not.
        with self.assertNumQueries(PROFILES_QUERIES):
            leaderboard(TODAY)
        with self.assertNumQueries(PROFILES_QUERIES + 3):
            profile_record(self.ana.id, TODAY)
        with self.assertNumQueries(PROFILES_QUERIES):
            profile_record(self.bob.id, TODAY)


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


def place(name, year, rank):
    """A DisciplinePlace for the grouping tests, whose discipline row id plays no part."""
    return DisciplinePlace(name, year, rank, discipline_id=1)


class TestDisciplinePlacesGrouping(SimpleTestCase):
    """`_discipline_places` groups and positions a person's places, no database needed."""

    @staticmethod
    def counted(*discipline_ranks):
        """A counted Participation (finished, ranked, teams >= 2) carrying these
        (name, year, rank) discipline places."""
        disciplines = tuple(
            place(name, year, rank) for name, year, rank in discipline_ranks
        )
        return Participation(2024, None, None, 1, 10, True, disciplines=disciplines)

    def test_shared_positions_can_land_away_from_first(self):
        # Fencing alone in 1st, Archery and Chess tied for 2nd, Darts alone with a 4th:
        # positions 1, 2, 2, 4, not the ordinal 1, 2, 2, 3.
        part = self.counted(
            ("Fencing", 2024, 1),
            ("Archery", 2024, 2),
            ("Chess", 2024, 2),
            ("Darts", 2024, 4),
        )

        self.assertEqual(
            _discipline_places([part]),
            (
                DisciplinePlaces("Fencing", (place("Fencing", 2024, 1),), 1),
                DisciplinePlaces("Archery", (place("Archery", 2024, 2),), 2),
                DisciplinePlaces("Chess", (place("Chess", 2024, 2),), 2),
                DisciplinePlaces("Darts", (place("Darts", 2024, 4),), 4),
            ),
        )

    def test_equal_ranks_in_one_discipline_are_ordered_newest_first(self):
        older = self.counted(("Relay", 2023, 1))
        newer = self.counted(("Relay", 2024, 1))

        result = _discipline_places([older, newer])

        self.assertEqual(
            result,
            (
                DisciplinePlaces(
                    "Relay",
                    (place("Relay", 2024, 1), place("Relay", 2023, 1)),
                    1,
                ),
            ),
        )


class TestBadgeStats(ProfilesSetup, TestCase):
    """badges.badge_stats: how many of the given people hold each badge code, once per
    person, and for the six tiered codes, how many hold at least each tier."""

    def badge(self, code, edition, user=None, **kwargs):
        """A stored Badge row, Ana's unless `user` is given."""
        return Badge.objects.create(user=user or self.ana, code=code, edition=edition, **kwargs)

    def test_players_is_the_number_of_ids_passed(self):
        stats = badge_stats([self.ana.id, self.bob.id, self.chloe.id])

        self.assertEqual(stats["players"], 3)

    def test_holders_only_lists_codes_with_at_least_one_holder(self):
        stats = badge_stats([self.ana.id, self.bob.id])

        self.assertEqual(stats, {"players": 2, "holders": {}, "tiers": {}})

    def test_counts_each_person_once_per_code_whatever_tier_discipline_partner_or_year(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024)
        self.badge(Badge.Codes.CHAMPION, self.y2025)  # Ana again, another year: still one
        self.badge(Badge.Codes.SPECIALIST, self.y2024, tier=1, discipline="Darts", user=self.bob)
        self.badge(Badge.Codes.SPECIALIST, self.y2025, tier=2, discipline="Relay", user=self.bob)
        self.badge(Badge.Codes.COMRADES, self.y2025, user=self.chloe, partner=self.dan)
        self.badge(Badge.Codes.COMRADES, self.y2025, user=self.chloe, partner=self.ana)

        stats = badge_stats([self.ana.id, self.bob.id, self.chloe.id, self.dan.id])

        self.assertEqual(
            stats["holders"], {"champion": 1, "specialist": 1, "comrades": 1}
        )

    def test_ignores_revoked_rows(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024, is_active=False)

        stats = badge_stats([self.ana.id])

        self.assertEqual(stats["holders"], {})

    def test_ignores_inactive_editions(self):
        y2023 = Edition.objects.create(
            year=2023, host="Brest", start_date="2023-09-23", end_date="2023-09-24",
            is_active=False,
        )
        self.badge(Badge.Codes.ROOKIE, y2023)

        stats = badge_stats([self.ana.id])

        self.assertEqual(stats["holders"], {})

    def test_ignores_people_outside_ids(self):
        self.badge(Badge.Codes.GOAT, self.y2024, user=self.bob)

        stats = badge_stats([self.ana.id])  # Bob not passed

        self.assertEqual(stats["holders"], {})

    def test_tiers_is_the_at_least_k_count(self):
        self.badge(Badge.Codes.VETERAN, self.y2024, tier=3)
        self.badge(Badge.Codes.VETERAN, self.y2025, tier=2, user=self.bob)
        self.badge(Badge.Codes.VETERAN, self.y2024, tier=1, user=self.chloe)

        stats = badge_stats([self.ana.id, self.bob.id, self.chloe.id])

        self.assertEqual(stats["holders"]["veteran"], 3)
        self.assertEqual(stats["tiers"]["veteran"], [3, 2, 1])

    def test_tiers_reads_the_highest_tier_per_person(self):
        self.badge(Badge.Codes.VETERAN, self.y2024, tier=1)
        self.badge(Badge.Codes.VETERAN, self.y2025, tier=3)  # Ana again, a higher tier

        stats = badge_stats([self.ana.id])

        self.assertEqual(stats["holders"]["veteran"], 1)
        self.assertEqual(stats["tiers"]["veteran"], [1, 1, 1])

    def test_tiers_only_lists_the_tiered_codes_with_a_holder(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024)  # untiered: no tiers entry

        stats = badge_stats([self.ana.id])

        self.assertEqual(stats["tiers"], {})

    def test_one_query(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024)

        with self.assertNumQueries(1):
            badge_stats([self.ana.id])

    def test_a_manually_awarded_badge_counts_towards_holders(self):
        """MVP and the other awards are entered by hand in the admin, never through
        badges.earned(): badge_stats reads the Badge table directly, so it must count a
        manual row exactly like a computed one."""
        self.badge(Badge.Codes.MVP, self.y2024, is_manual=True)

        stats = badge_stats([self.ana.id])

        self.assertEqual(stats["holders"], {"mvp": 1})

    def test_tiered_codes_matches_every_tier_table(self):
        """TIERED_CODES is maintained by hand next to the six *_TIERS tables it names.
        Derive the codes mechanically from every *_TIERS name in the module instead of
        hand-listing them again here, so a seventh tiered badge with a new *_TIERS table
        can't be added without TIERED_CODES failing this test."""
        derived = {
            name[: -len("_TIERS")].lower().replace("_", "-")
            for name in vars(badges_module)
            if name.endswith("_TIERS")
        }

        self.assertEqual(derived, set(badges_module.TIERED_CODES))


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
        self.assertNotIn("disciplines", response.data[0])  # /profiles/ rows carry no disciplines
        self.assertEqual(response.data[1]["position"], 2)  # Chloé: one 1st place
        self.assertEqual(response.data[1]["average_rank"], 1.0)
        self.assertEqual((response.data[4]["places"], response.data[4]["position"]), ([], None))
        self.assertIsNone(response.data[4]["average_rank"])

    def test_profile_lists_every_edition_newest_first(self):
        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {k: v for k, v in response.data.items() if k not in ("editions", "disciplines")},
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "position": 1,
                "counted": 2,
                "average_rank": 1.0,
                "badges": [],
                "badge_stats": {"players": 6, "holders": {}, "tiers": {}},
            },
        )
        self.assertNotIn("average_beaten", response.data)
        self.assertEqual(
            response.data["disciplines"],
            [
                {
                    "name": "Relay",
                    "position": 1,
                    "places": [{"year": 2025, "rank": 1}],
                    "latest": {"year": 2025, "discipline": self.relay2025.id},
                }
            ],
        )
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
        self.assertEqual(response.data["disciplines"], [])
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
        # Badges over two editions, one with a partner: the profile reads them in one query,
        # plus one more for the rarity stats.
        self.badge(Badge.Codes.CHAMPION, self.y2024)
        self.badge(Badge.Codes.CHAMPION, self.y2025)
        self.badge(Badge.Codes.COMRADES, self.y2025, partner=self.chloe)

        with self.assertNumQueries(PROFILES_QUERIES):
            self.assertEqual(self.client.get("/profiles/").status_code, 200)
        # Plus three for the standings of the running 2026, where Ana has a team.
        with self.assertNumQueries(PROFILES_QUERIES + 2 + 3):
            self.assertEqual(self.client.get(f"/profile/{self.ana.id}/").status_code, 200)
        # Bob plays no running edition.
        with self.assertNumQueries(PROFILES_QUERIES + 2):
            self.assertEqual(self.client.get(f"/profile/{self.bob.id}/").status_code, 200)

    def test_profile_carries_badge_stats(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024)
        self.badge(Badge.Codes.VETERAN, self.y2025, tier=2, user=self.bob)

        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["badge_stats"],
            {
                "players": 6,
                "holders": {"champion": 1, "veteran": 1},
                "tiers": {"veteran": [1, 1, 0]},
            },
        )

    def test_profiles_endpoint_carries_no_badge_stats(self):
        response = self.client.get("/profiles/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("badge_stats", response.data[0])

    # Badges

    def badge(self, code, edition, user=None, **kwargs):
        """A stored Badge row, Ana's unless `user` is given."""
        return Badge.objects.create(user=user or self.ana, code=code, edition=edition, **kwargs)

    def badges(self, user=None):
        """The `badges` of the user's profile, Ana's by default."""
        response = self.client.get(f"/profile/{(user or self.ana).id}/")
        self.assertEqual(response.status_code, 200)
        return response.data["badges"]

    @staticmethod
    def entry(code, years, tier=0, discipline=None, partner=None):
        return {
            "code": code, "tier": tier, "years": years, "discipline": discipline,
            "partner": partner,
        }

    def test_a_profile_without_badges_has_an_empty_list(self):
        self.badge(Badge.Codes.CHAMPION, self.y2024)  # Ana's, not Fay's

        self.assertEqual(self.badges(self.fay), [])

    def test_the_rows_of_one_badge_are_grouped_with_their_years_oldest_first(self):
        self.badge(Badge.Codes.CHAMPION, self.y2025)
        self.badge(Badge.Codes.CHAMPION, self.y2024)

        self.assertEqual(self.badges(), [self.entry("champion", [2024, 2025])])

    def test_a_tiered_badge_carries_its_highest_tier(self):
        self.badge(Badge.Codes.VETERAN, self.y2025, tier=2)
        self.badge(Badge.Codes.VETERAN, self.y2024, tier=1)

        self.assertEqual(self.badges(), [self.entry("veteran", [2024, 2025], tier=2)])

    def test_a_discipline_badge_is_one_entry_per_discipline_by_name(self):
        self.badge(Badge.Codes.SPECIALIST, self.y2025, tier=1, discipline="Relay")
        self.badge(Badge.Codes.SPECIALIST, self.y2024, tier=1, discipline="Darts")

        self.assertEqual(
            self.badges(),
            [
                self.entry("specialist", [2024], tier=1, discipline="Darts"),
                self.entry("specialist", [2025], tier=1, discipline="Relay"),
            ],
        )

    def test_a_comrades_badge_names_the_partner_and_nothing_else(self):
        self.badge(Badge.Codes.COMRADES, self.y2025, partner=self.chloe)

        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(
            response.data["badges"],
            [
                self.entry(
                    "comrades",
                    [2025],
                    partner={"id": self.chloe.id, "first_name": "Chloé", "last_name": "Dupont"},
                )
            ],
        )
        content = response.content
        self.assertNotIn(b"username", content)
        self.assertNotIn(b"email", content)
        self.assertNotIn(b"login-", content)  # neither Ana's login nor Chloé's
        self.assertNotIn(b"mail.example", content)

    def test_badges_come_in_catalogue_order_and_keep_private_fields_out(self):
        self.badge(Badge.Codes.MVP, self.y2025, is_manual=True, note="Try of the day")
        self.badge(Badge.Codes.GOAT, self.y2025)
        self.badge(Badge.Codes.WOODEN_SPOON, self.y2024)

        response = self.client.get(f"/profile/{self.ana.id}/")

        self.assertEqual(
            [badge["code"] for badge in response.data["badges"]],
            ["wooden-spoon", "goat", "mvp"],
        )
        self.assertEqual(response.data["badges"][2], self.entry("mvp", [2025]))
        self.assertNotIn(b"Try of the day", response.content)
        self.assertNotIn(b"is_manual", response.content)
        self.assertNotIn(b"created_at", response.content)

    def test_inactive_rows_and_rows_of_an_inactive_edition_are_left_out(self):
        y2023 = Edition.objects.create(
            year=2023, host="Brest", start_date="2023-09-23", end_date="2023-09-24",
            is_active=False,
        )
        self.badge(Badge.Codes.CHAMPION, self.y2024)
        self.badge(Badge.Codes.CHAMPION, self.y2025, is_active=False)
        self.badge(Badge.Codes.ROOKIE, y2023)

        self.assertEqual(self.badges(), [self.entry("champion", [2024])])


class TestDisciplineTable(DisciplinesSetup, TestCase):
    """profiles.discipline_table and GET /discipline/<id>/all-time/: every revealed result
    of a discipline, across editions by name, running ones included, credited to the
    team's roster and in medal-table order."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()  # no credentials: the endpoint is public

    @staticmethod
    def rows(table):
        """(first name, position, [(year, rank), ...]) per row, for compact asserts."""
        return [
            (row.first_name, row.position, [(p.year, p.rank) for p in row.places])
            for row in table.rows
        ]

    def test_places_aggregate_by_name_across_editions_in_medal_table_order(self):
        # Ana (2nd in 2024, 1st in 2025) and Bob (1st in 2024, 2nd in 2025) have identical
        # places: tied, listed by name. Chloé's single 1st loses to their extra 2nd.
        table = discipline_table("Relay")

        self.assertEqual(table.name, "Relay")
        self.assertEqual(table.years, (2024, 2025))
        self.assertEqual(
            self.rows(table),
            [
                ("Ana", 1, [(2025, 1), (2024, 2)]),
                ("Bob", 1, [(2024, 1), (2025, 2)]),
                ("Chloé", 3, [(2025, 1)]),
                ("Dan", 4, [(2024, 3)]),
            ],
        )

    def test_the_running_edition_counts_once_revealed_and_a_hidden_result_never(self):
        # The running 2026 Darts is revealed: Renards (Ana) 1st, Sangliers (Eve) 2nd. Eve
        # and Bob tie on a single 2nd place, listed by name. The hidden 2025 Darts gives
        # Chloé nothing, and Fay had no team in 2024.
        table = discipline_table("Darts")

        self.assertEqual(table.years, (2024, 2026))
        self.assertEqual(
            self.rows(table),
            [
                ("Ana", 1, [(2026, 1), (2024, 1)]),
                ("Eve", 2, [(2026, 2)]),
                ("Bob", 2, [(2024, 2)]),
                ("Dan", 4, [(2024, 3)]),
            ],
        )

    def test_an_uncontested_discipline_gives_no_place(self):
        # A lone scored result beats nobody, nor does a tie of every team on 0.
        TeamResult.objects.filter(discipline=self.running_darts, team=self.sangliers).update(
            points=None
        )
        relay = Relay.objects.create(edition=self.y2026, reveal_score=True)
        TeamResult.objects.filter(discipline=relay).update(points=0)

        self.assertEqual(discipline_table("Darts").years, (2024,))
        self.assertEqual(discipline_table("Relay").years, (2024, 2025))

    def test_revealing_a_result_adds_it_and_hiding_it_takes_it_back(self):
        Darts.objects.filter(pk=self.hidden_darts.pk).update(reveal_score=True)
        Darts.objects.filter(pk=self.running_darts.pk).update(reveal_score=False)

        # Ana (Aigles, then Loups) now has two 1st places, Chloé (Loups) one, and Bob
        # (Bisons, then Ours) two 2nd places.
        self.assertEqual(
            self.rows(discipline_table("Darts")),
            [
                ("Ana", 1, [(2025, 1), (2024, 1)]),
                ("Chloé", 2, [(2025, 1)]),
                ("Bob", 3, [(2025, 2), (2024, 2)]),
                ("Dan", 4, [(2024, 3)]),
            ],
        )

    def test_a_place_counts_whether_or_not_the_participation_does(self):
        # Without a final_rank, Aigles have no rank in hand-ranked 2024, so Ana's 2024 counts
        # neither on her profile nor for the leaderboard: its revealed Relay place still does.
        Team.objects.filter(pk=self.aigles.pk).update(final_rank=None)

        rows = self.rows(discipline_table("Relay"))

        self.assertEqual(rows[0], ("Ana", 1, [(2025, 1), (2024, 2)]))

    def test_an_inactive_discipline_or_team_drops_out(self):
        # Without the 2024 Relay, Chloé (Dupont) and Ana (Lopez) tie on a single 1st place,
        # listed by name; with Cerfs inactive, Dan has no team and no place.
        Relay.objects.filter(pk=self.relay2024.pk).update(is_active=False)
        Team.objects.filter(pk=self.cerfs.pk).update(is_active=False)

        table = discipline_table("Relay")

        self.assertEqual(table.years, (2025,))
        self.assertEqual(
            self.rows(table),
            [("Chloé", 1, [(2025, 1)]), ("Ana", 1, [(2025, 1)]), ("Bob", 3, [(2025, 2)])],
        )

    def test_a_discipline_without_a_place_gives_an_empty_table(self):
        table = discipline_table("Rugby")

        self.assertEqual((table.name, table.years, table.rows), ("Rugby", (), ()))

    def test_query_budget_follows_the_editions_holding_the_discipline(self):
        # Relay: 2024 and 2025. Darts: 2024, 2025 and 2026. A discipline held nowhere: the
        # editions query alone.
        with self.assertNumQueries(2 + 3 * 2):
            discipline_table("Relay")
        with self.assertNumQueries(2 + 3 * 3):
            discipline_table("Darts")
        with self.assertNumQueries(1):
            discipline_table("Rugby")

    def test_endpoint_is_public_and_serves_the_table(self):
        response = self.client.get(f"/discipline/{self.relay2024.id}/all-time/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Relay")
        self.assertEqual(response.data["years"], [2024, 2025])
        self.assertEqual(
            response.data["players"][0],
            {
                "id": self.ana.id,
                "first_name": "Ana",
                "last_name": "Lopez",
                "position": 1,
                "places": [{"year": 2025, "rank": 1}, {"year": 2024, "rank": 2}],
            },
        )
        self.assertEqual(
            [(row["first_name"], row["position"]) for row in response.data["players"]],
            [("Ana", 1), ("Bob", 1), ("Chloé", 3), ("Dan", 4)],
        )

    def test_every_edition_of_a_discipline_serves_the_same_table(self):
        # Including the running edition's Darts and the hidden 2025 one: the table does not
        # depend on the page it is shown on.
        relay = self.client.get(f"/discipline/{self.relay2024.id}/all-time/").data
        darts = self.client.get(f"/discipline/{self.darts2024.id}/all-time/").data

        self.assertEqual(self.client.get(f"/discipline/{self.relay2025.id}/all-time/").data, relay)
        for discipline in (self.hidden_darts, self.running_darts):
            self.assertEqual(self.client.get(f"/discipline/{discipline.id}/all-time/").data, darts)

    def test_empty_table(self):
        unplayed = Darts.objects.create(edition=self.y2026, reveal_score=False)
        Darts.objects.exclude(pk=unplayed.pk).update(is_active=False)

        response = self.client.get(f"/discipline/{unplayed.id}/all-time/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"name": "Darts", "years": [], "players": []})

    def test_404_for_an_unknown_or_inactive_discipline_and_an_inactive_edition(self):
        Relay.objects.filter(pk=self.relay2024.pk).update(is_active=False)
        Edition.objects.filter(pk=self.y2025.pk).update(is_active=False)

        for discipline_id in (999999, self.relay2024.id, self.relay2025.id):
            response = self.client.get(f"/discipline/{discipline_id}/all-time/")
            self.assertEqual(response.status_code, 404)

    def test_payload_carries_no_login_name_or_email(self):
        content = self.client.get(f"/discipline/{self.relay2024.id}/all-time/").content

        self.assertNotIn(b"login-", content)
        self.assertNotIn(b"mail.example", content)
        self.assertNotIn(b"username", content)
        self.assertNotIn(b"email", content)

    def test_endpoint_runs_in_a_fixed_number_of_queries(self):
        with self.assertNumQueries(DISCIPLINE_TABLE_QUERIES):
            self.assertEqual(
                self.client.get(f"/discipline/{self.relay2024.id}/all-time/").status_code, 200
            )


class TestHeldDisciplines(DisciplinesSetup, TestCase):
    """profiles.held_disciplines and GET /disciplines/all-time/: every discipline name an
    active edition held, with those editions, the index of the all-time tables."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()  # no credentials: the endpoint is public

    @staticmethod
    def held():
        """(name, [(year, discipline id), ...]) per held discipline, for compact asserts."""
        return [
            (d.name, [(e.year, e.discipline_id) for e in d.editions]) for d in held_disciplines()
        ]

    def test_every_name_held_by_an_active_edition_in_name_order_editions_oldest_first(self):
        # The hidden 2025 Darts and the running 2026 Darts are held all the same.
        self.assertEqual(
            self.held(),
            [
                (
                    "Darts",
                    [
                        (2024, self.darts2024.id),
                        (2025, self.hidden_darts.id),
                        (2026, self.running_darts.id),
                    ],
                ),
                ("Relay", [(2024, self.relay2024.id), (2025, self.relay2025.id)]),
            ],
        )

    def test_a_discipline_without_any_result_is_held(self):
        seek = HideAndSeek.objects.create(edition=self.y2026)

        self.assertIn(("Hide and Seek", [(2026, seek.id)]), self.held())

    def test_an_edition_holding_a_name_twice_gives_its_lowest_id(self):
        Darts.objects.create(edition=self.y2024)

        self.assertEqual(self.held()[0][1][0], (2024, self.darts2024.id))

    def test_inactive_disciplines_and_editions_are_left_out(self):
        Darts.objects.filter(pk=self.running_darts.pk).update(is_active=False)
        Edition.objects.filter(pk=self.y2024.pk).update(is_active=False)

        self.assertEqual(
            self.held(),
            [
                ("Darts", [(2025, self.hidden_darts.id)]),
                ("Relay", [(2025, self.relay2025.id)]),
            ],
        )

    def test_a_row_without_a_name_is_left_out(self):
        Discipline.objects.create(edition=self.y2026, name="")

        self.assertEqual([name for name, _ in self.held()], ["Darts", "Relay"])

    def test_endpoint_is_public_and_serves_the_index_in_one_query(self):
        with self.assertNumQueries(1):
            response = self.client.get("/disciplines/all-time/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "name": "Darts",
                    "editions": [
                        {"year": 2024, "discipline": self.darts2024.id},
                        {"year": 2025, "discipline": self.hidden_darts.id},
                        {"year": 2026, "discipline": self.running_darts.id},
                    ],
                },
                {
                    "name": "Relay",
                    "editions": [
                        {"year": 2024, "discipline": self.relay2024.id},
                        {"year": 2025, "discipline": self.relay2025.id},
                    ],
                },
            ],
        )
