"""The registration models: the questionnaire's skills, the private answers on a Player."""
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition, Player, PlayerSport, RegistrationSkill
from olympic_warriors.models.Player import SportFrequency
from olympic_warriors.tests.test_showcase import PRIVATE_KEYS, keys_in


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


class TestEditionDatesConfirmed(TestCase):
    def test_existing_and_new_editions_have_confirmed_dates_by_default(self):
        self.assertTrue(make_edition().dates_confirmed)


class TestPlayerRegistrationFields(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")

    def test_defaults(self):
        player = Player.objects.create(user=self.ana, edition=self.edition, rating=5)

        self.assertIsNone(player.global_level)
        self.assertEqual(player.dietary_restrictions, "")
        self.assertEqual(player.sport_frequency, "")
        self.assertEqual(player.team_wishes, "")
        self.assertFalse(player.attendance_confirmed)

    def test_the_frequency_choices_are_the_five_of_the_form(self):
        self.assertEqual(
            SportFrequency.values, ["rare", "monthly", "hour", "two_hours", "four_hours"]
        )

    def test_sports_come_back_in_order_and_die_with_the_player(self):
        player = Player.objects.create(user=self.ana, edition=self.edition, rating=5)
        PlayerSport.objects.create(player=player, order=2, sport="Judo")
        PlayerSport.objects.create(player=player, order=1, sport="Tennis", level="amateur")

        self.assertEqual([s.sport for s in player.playersport_set.all()], ["Tennis", "Judo"])

        player.delete()
        self.assertEqual(PlayerSport.objects.count(), 0)


class TestRegistrationSkill(TestCase):
    def test_an_identifier_is_unique_per_edition_only(self):
        first, second = make_edition(2027), make_edition(2028)
        RegistrationSkill.objects.create(
            edition=first, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )

        RegistrationSkill.objects.create(
            edition=second, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistrationSkill.objects.create(
                edition=first, name_fr="Autre", name_en="Other", identifier="CARD", weight=1
            )

    def test_skills_are_ordered_and_die_with_their_edition(self):
        edition = make_edition()
        RegistrationSkill.objects.create(
            edition=edition, name_fr="B", name_en="B", identifier="BBB", weight=1, order=2
        )
        RegistrationSkill.objects.create(
            edition=edition, name_fr="A", name_en="A", identifier="AAA", weight=1, order=1
        )

        self.assertEqual([s.identifier for s in edition.registrationskill_set.all()], ["AAA", "BBB"])
        self.assertTrue(RegistrationSkill.objects.get(identifier="AAA").is_active)

        edition.delete()
        self.assertEqual(RegistrationSkill.objects.count(), 0)


class TestPrivateAnswersStayPrivate(TestCase):
    def test_no_public_payload_carries_a_registration_answer(self):
        edition = make_edition(2026)
        player = Player.objects.create(
            user=User.objects.create(username="ana", first_name="Ana", last_name="Lopez"),
            edition=edition,
            rating=5,
            global_level=7,
            dietary_restrictions="Sans gluten",
            sport_frequency="hour",
            team_wishes="Avec Bob",
            attendance_confirmed=True,
        )
        PlayerSport.objects.create(player=player, sport="Judo", notes="Ceinture orange")

        for url in ("/edition/year/2026/summary/", "/profiles/", f"/profile/{player.user_id}/"):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(keys_in(response.json()) & PRIVATE_KEYS, set())
                for secret in ("Sans gluten", "Avec Bob", "Ceinture orange"):
                    self.assertNotIn(secret.encode(), response.content)
