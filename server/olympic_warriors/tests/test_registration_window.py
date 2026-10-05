"""The registration window fields, the invited flag and the late pass."""
from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition, LateRegistration, Player, UserProfile


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


class TestEditionWindowFields(TestCase):
    def test_defaults_close_the_registration(self):
        edition = make_edition()

        self.assertIsNone(edition.registration_opens)
        self.assertIsNone(edition.registration_closes)
        self.assertEqual(edition.registration_intro_fr, "")
        self.assertEqual(edition.registration_intro_en, "")
        self.assertEqual(edition.skills_month_fr, "")
        self.assertEqual(edition.skills_month_en, "")


class TestInvited(TestCase):
    def test_a_profile_is_not_invited_by_default(self):
        profile = UserProfile.objects.create(user=User.objects.create(username="ana"))

        self.assertFalse(profile.invited)


class TestPlayerWithdrawnAt(TestCase):
    def test_a_player_has_not_withdrawn_by_default(self):
        player = Player.objects.create(
            user=User.objects.create(username="ana"), edition=make_edition(), rating=5
        )

        self.assertIsNone(player.withdrawn_at)


class TestLateRegistration(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")
        self.orga = User.objects.create(username="orga", is_staff=True)

    def test_one_pass_per_user_and_edition(self):
        LateRegistration.objects.create(user=self.ana, edition=self.edition, granted_by=self.orga)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LateRegistration.objects.create(user=self.ana, edition=self.edition)
        LateRegistration.objects.create(user=self.ana, edition=make_edition(2028))

    def test_it_records_who_and_when_and_survives_its_granter(self):
        late = LateRegistration.objects.create(
            user=self.ana, edition=self.edition, granted_by=self.orga
        )
        self.assertIsNotNone(late.granted_at)

        self.orga.delete()
        late.refresh_from_db()
        self.assertIsNone(late.granted_by)

    def test_it_dies_with_its_user_or_edition(self):
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        self.ana.delete()
        self.assertEqual(LateRegistration.objects.count(), 0)
