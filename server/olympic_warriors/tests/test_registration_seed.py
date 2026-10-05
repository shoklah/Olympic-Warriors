"""The data migration that gives the existing editions their questionnaire."""
import importlib

from django.apps import apps
from django.test import TestCase

from olympic_warriors.models import Edition, RegistrationSkill
from olympic_warriors.registration import FORM_PROFILES

migration = importlib.import_module("olympic_warriors.migrations.0042_seed_registration_skills")


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


class TestSeedLiteralsMatchTheFormProfiles(TestCase):
    """The migration holds literals (a migration must not follow later code changes); this
    keeps them equal to the profiles the CSV import knows today."""

    def literals(self, skills):
        return {(i, fr, en, w) for i, fr, en, w in skills}

    def profile(self, name):
        return {
            (spec["id"], spec["criterion"], skill, spec["coef"])
            for skill, spec in FORM_PROFILES[name].items()
        }

    def test_2025_skills(self):
        self.assertEqual(self.literals(migration.SKILLS_2025), self.profile("2025"))

    def test_2024_skills(self):
        self.assertEqual(self.literals(migration.SKILLS_2024), self.profile("2024"))


class TestSeed(TestCase):
    def test_each_edition_gets_the_skills_of_its_form(self):
        old, y2024, y2025, y2026 = (make_edition(y) for y in (2023, 2024, 2025, 2026))

        migration.seed(apps, None)

        self.assertEqual(old.registrationskill_set.count(), 0)
        self.assertEqual(y2024.registrationskill_set.count(), 10)
        self.assertTrue(y2024.registrationskill_set.filter(identifier="OBS", weight=1).exists())
        for edition in (y2025, y2026):
            self.assertEqual(edition.registrationskill_set.count(), 10)
            self.assertTrue(edition.registrationskill_set.filter(identifier="CARD").exists())
            self.assertFalse(edition.registrationskill_set.filter(identifier="OBS").exists())

    def test_names_orders_and_weights(self):
        edition = make_edition(2026)

        migration.seed(apps, None)

        first = edition.registrationskill_set.first()
        self.assertEqual(
            (first.identifier, first.name_fr, first.name_en, first.weight, first.order),
            ("TEAM", "Cohésion et esprit d'équipe", "Cohesion and Team Spirit", 2, 0),
        )
        self.assertEqual(
            list(edition.registrationskill_set.values_list("order", flat=True)), list(range(10))
        )

    def test_it_is_idempotent_and_leaves_an_existing_questionnaire_alone(self):
        seeded, custom = make_edition(2025), make_edition(2026)
        RegistrationSkill.objects.create(
            edition=custom, name_fr="Mien", name_en="Mine", identifier="MINE", weight=3
        )

        migration.seed(apps, None)
        migration.seed(apps, None)

        self.assertEqual(seeded.registrationskill_set.count(), 10)
        self.assertEqual(list(custom.registrationskill_set.values_list("identifier", flat=True)), ["MINE"])
