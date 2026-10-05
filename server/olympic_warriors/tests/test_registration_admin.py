"""The questionnaire in the admin: the locked skills inline, the two Edition actions, the
Player columns and filters, the sports inline."""
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.test import TestCase, override_settings

from olympic_warriors.admin import LockedSkillFormSet
from olympic_warriors.models import (
    Edition,
    Player,
    PlayerRating,
    PlayerSport,
    RegistrationSkill,
    Team,
)

EDITIONS = "/admin/olympic_warriors/edition/"
PLAYERS = "/admin/olympic_warriors/player/"
FIELDS = ("order", "identifier", "name_fr", "name_en", "weight", "is_active")


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


def make_skill(edition, identifier="CARD", weight=4, order=0):
    return RegistrationSkill.objects.create(
        edition=edition,
        name_fr=identifier,
        name_en=identifier,
        identifier=identifier,
        weight=weight,
        order=order,
    )


def skill_row(skill, **changes):
    """The posted values of an existing skill, with changes applied."""
    row = {
        "id": skill.pk,
        "order": skill.order,
        "identifier": skill.identifier,
        "name_fr": skill.name_fr,
        "name_en": skill.name_en,
        "weight": skill.weight,
        "is_active": "on",
    }
    row.update(changes)
    return row


NEW_ROW = {
    "order": 5,
    "identifier": "NEW",
    "name_fr": "Nouvelle",
    "name_en": "New",
    "weight": 2,
    "is_active": "on",
}


def bound_formset(edition, rows):
    """LockedSkillFormSet bound to posted rows; rows with an id come first."""
    factory = inlineformset_factory(
        Edition, RegistrationSkill, formset=LockedSkillFormSet, fields=FIELDS, extra=0
    )
    prefix = factory.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": str(sum("id" in row for row in rows)),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        data[f"{prefix}-{index}-edition"] = str(edition.pk)
        for key, value in row.items():
            data[f"{prefix}-{index}-{key}"] = str(value)
    return factory(data, instance=edition)


class TestLockedSkillFormSet(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        self.skill = make_skill(self.edition)

    def lock(self):
        player = Player.objects.create(
            user=User.objects.create(username="ana"), edition=self.edition, rating=5
        )
        PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=6)

    def test_free_while_nobody_has_answered(self):
        formset = bound_formset(self.edition, [skill_row(self.skill, identifier="CRD"), NEW_ROW])
        self.assertTrue(formset.is_valid(), formset.errors)

        deletion = bound_formset(self.edition, [skill_row(self.skill, DELETE="on")])
        self.assertTrue(deletion.is_valid(), deletion.errors)

    def test_locked_allows_weights_labels_order_and_activation(self):
        self.lock()
        row = skill_row(self.skill, weight=9, name_fr="Cardio !", order=3)
        row.pop("is_active")  # switched off

        formset = bound_formset(self.edition, [row])

        self.assertTrue(formset.is_valid(), formset.errors)

    def test_locked_refuses_a_new_skill(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill), NEW_ROW])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_locked_refuses_a_deletion(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill, DELETE="on")])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_locked_refuses_an_identifier_change(self):
        self.lock()

        formset = bound_formset(self.edition, [skill_row(self.skill, identifier="CRD")])

        self.assertFalse(formset.is_valid())
        self.assertIn("verrouillé", " ".join(formset.non_form_errors()))

    def test_an_unsaved_edition_is_never_locked(self):
        factory = inlineformset_factory(
            Edition, RegistrationSkill, formset=LockedSkillFormSet, fields=FIELDS, extra=1
        )
        formset = factory(instance=Edition())

        self.assertEqual(len(formset.forms), 1)


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestEditionAdmin(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.previous = make_edition(2026)
        make_skill(self.previous, "CARD", 4)
        make_skill(self.previous, "STR", 3, order=1)
        self.current = make_edition(2027)

    def run_action(self, action, *editions):
        response = self.client.post(
            EDITIONS,
            {"action": action, "_selected_action": [e.pk for e in editions], "index": 0},
            follow=True,
        )
        return response, [str(m) for m in response.context["messages"]]

    def test_the_change_page_renders_with_dates_confirmed_and_the_skills(self):
        response = self.client.get(f"{EDITIONS}{self.previous.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dates_confirmed")
        self.assertContains(response, "registrationskill_set-TOTAL_FORMS")

    def test_copy_action(self):
        _, messages = self.run_action("copy_questionnaire", self.current)

        self.assertEqual(messages, ["2027 : 2 compétence(s) copiée(s) depuis 2026."])
        self.assertEqual(self.current.registrationskill_set.count(), 2)

    def test_copy_action_reports_an_edition_that_already_has_skills(self):
        _, messages = self.run_action("copy_questionnaire", self.previous)

        self.assertEqual(messages, ["2026 : cette édition a déjà un questionnaire."])

    def test_recompute_action_reports_each_edition(self):
        player = Player.objects.create(
            user=User.objects.create(username="ana"), edition=self.previous,
            rating=5, global_level=5,
        )
        PlayerRating.objects.create(player=player, name="C", identifier="CARD", rating=10)
        PlayerRating.objects.create(player=player, name="S", identifier="STR", rating=2)
        old = Player.objects.create(
            user=User.objects.create(username="old"), edition=self.previous, rating=7
        )
        PlayerRating.objects.create(player=old, name="C", identifier="CARD", rating=10)

        _, messages = self.run_action("recompute_player_ratings", self.previous, self.current)

        # CARD 10 (4), STR 2 (3): weighted 6.57, blend (6.57 + 20) / 5 = 5.31, stored 5: unchanged.
        self.assertEqual(
            messages,
            [
                "2026 : 0 note(s) mise(s) à jour, 1 inchangée(s), "
                "1 joueur(s) ignoré(s) : réponse globale inconnue.",
                "2027 : Aucun questionnaire pour cette édition.",
            ],
        )


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestPlayerAdminRegistration(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        edition = make_edition(2027)
        self.vegan = Player.objects.create(
            user=User.objects.create(username="ana", first_name="Ana"), edition=edition,
            rating=5, dietary_restrictions="Végane", attendance_confirmed=True,
            sport_frequency="hour",
        )
        self.plain = Player.objects.create(
            user=User.objects.create(username="bob", first_name="Bob"), edition=edition, rating=5,
        )

    def names(self, response):
        return {str(p) for p in response.context["cl"].result_list}

    def test_dietary_filter(self):
        yes = self.client.get(PLAYERS, {"dietary": "yes", "is_active__exact": "1"})
        no = self.client.get(PLAYERS, {"dietary": "no", "is_active__exact": "1"})

        self.assertEqual(self.names(yes), {"Ana "})
        self.assertEqual(self.names(no), {"Bob "})

    def test_confirmation_and_frequency_filters(self):
        confirmed = self.client.get(PLAYERS, {"attendance_confirmed__exact": "1", "is_active__exact": "1"})
        weekly = self.client.get(PLAYERS, {"sport_frequency__exact": "hour", "is_active__exact": "1"})

        self.assertEqual(self.names(confirmed), {"Ana "})
        self.assertEqual(self.names(weekly), {"Ana "})

    def test_the_change_page_has_the_sports_inline(self):
        PlayerSport.objects.create(player=self.vegan, sport="Judo")

        response = self.client.get(f"{PLAYERS}{self.vegan.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "playersport_set-TOTAL_FORMS")
        self.assertContains(response, "Judo")


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestTeamPageRoster(TestCase):
    def test_the_roster_rows_do_not_carry_the_private_registration_answers(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        edition = make_edition(2027)
        team = Team.objects.create(name="MxM", edition=edition)
        Player.objects.create(
            user=User.objects.create(username="ana"), edition=edition, rating=5, team=team,
            dietary_restrictions="Végane", team_wishes="Avec Bob", team_with="Avec Bob",
            team_avoid="Pas Carl",
        )

        response = self.client.get(f"/admin/olympic_warriors/team/{team.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "player_set-0-rating")
        for private in (
            "global_level", "dietary_restrictions", "sport_frequency", "team_wishes",
            "team_with", "team_avoid", "attendance_confirmed",
        ):
            self.assertNotContains(response, f"player_set-0-{private}")
        self.assertNotContains(response, "Végane")
        self.assertNotContains(response, "Pas Carl")
