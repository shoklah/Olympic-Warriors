"""
Tests for olympic_warriors.profiles: a person's editions, averages and leaderboard place,
computed from the edition standings, and the two public endpoints serving them.
"""

from datetime import date, datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from olympic_warriors.profiles import beaten_share, paris_today


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
