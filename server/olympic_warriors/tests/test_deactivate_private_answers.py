"""Deleting an account clears the private registration answers (spec: Privacy)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors import accounts
from olympic_warriors.models import Edition, Player, PlayerSport


def make_player(edition, username, **answers):
    user = User.objects.create(username=username)
    return Player.objects.create(user=user, edition=edition, rating=6, **answers)


class TestDeactivateClearsAnswers(TestCase):
    def setUp(self):
        self.old = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.new = Edition.objects.create(
            year=2027, host="Paris", start_date=date(2027, 9, 18), end_date=date(2027, 9, 19)
        )
        self.answers = dict(
            global_level=8, dietary_restrictions="Végane", sport_frequency="two_hours",
            team_wishes="Avec Bob", attendance_confirmed=True,
        )

    def test_every_player_row_of_the_person_is_cleared_but_keeps_its_rating(self):
        first = make_player(self.old, "ana", **self.answers)
        second = Player.objects.create(user=first.user, edition=self.new, rating=7, **self.answers)
        PlayerSport.objects.create(player=first, sport="Judo")
        PlayerSport.objects.create(player=second, sport="Tennis")

        accounts.deactivate(first.user)

        for player in (first, second):
            player.refresh_from_db()
            self.assertIsNone(player.global_level)
            self.assertEqual(player.dietary_restrictions, "")
            self.assertEqual(player.sport_frequency, "")
            self.assertEqual(player.team_wishes, "")
            self.assertFalse(player.attendance_confirmed)
        self.assertEqual((first.rating, second.rating), (6, 7))  # places and history stay
        self.assertEqual(PlayerSport.objects.count(), 0)

    def test_another_person_is_untouched(self):
        ana = make_player(self.old, "ana", **self.answers)
        bob = make_player(self.old, "bob", **self.answers)
        PlayerSport.objects.create(player=bob, sport="Judo")

        accounts.deactivate(ana.user)

        bob.refresh_from_db()
        self.assertEqual(bob.dietary_restrictions, "Végane")
        self.assertEqual(bob.global_level, 8)
        self.assertEqual(PlayerSport.objects.count(), 1)
