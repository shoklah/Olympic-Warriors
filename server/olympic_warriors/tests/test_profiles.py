"""
Tests for olympic_warriors.profiles: a person's editions, averages and leaderboard place,
computed from the edition standings, and the two public endpoints serving them.
"""

from datetime import date, datetime, timezone
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from olympic_warriors.models import Edition, Player, Relay, Team, TeamResult
from olympic_warriors.profiles import beaten_share, paris_today, participations

TODAY = date(2026, 9, 23)
# The editions query, the players query, then three per finished edition with players
# (2024 and 2025 in ProfilesSetup; 2026 is still running).
PROFILES_QUERIES = 2 + 3 * 2


class TestBeatenShare(SimpleTestCase):
    def test_first_beats_every_other_team_and_last_none(self):
        self.assertEqual(beaten_share(1, 6), 1.0)
        self.assertEqual(beaten_share(6, 6), 0.0)
        self.assertAlmostEqual(beaten_share(2, 8), 6 / 7)

    def test_no_share_without_a_rank_or_with_a_single_team(self):
        self.assertIsNone(beaten_share(None, 6))
        self.assertIsNone(beaten_share(1, 1))
        self.assertIsNone(beaten_share(1, 0))

    def test_clamped_when_a_hand_entered_rank_is_out_of_range(self):
        self.assertEqual(beaten_share(9, 6), 0.0)
        self.assertEqual(beaten_share(0, 6), 1.0)


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
        self.chloe = self.person("Chloé", "Nguyen")
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

    def test_an_edition_is_finished_from_the_day_after_its_end_date(self):
        _, on_the_last_day = participations(date(2026, 9, 30))[self.eve.id]
        _, the_day_after = participations(date(2026, 10, 1))[self.eve.id]

        self.assertEqual(summary_of(on_the_last_day), [(2026, "Sangliers", None, 2, False)])
        # Nothing revealed in 2026: both teams tie on 0 points, so both are 1st.
        self.assertEqual(summary_of(the_day_after), [(2026, "Sangliers", 1, 2, True)])

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
