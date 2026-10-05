"""Opening registration from the Edition page and granting late passes."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from olympic_warriors.admin import UserProfileAdmin
from olympic_warriors.models import (
    Edition, LateRegistration, Player, RegistrationSkill, UserProfile,
)

EDITIONS = "/admin/olympic_warriors/edition/"
PLAYERS = "/admin/olympic_warriors/player/"
PROFILES = "/admin/olympic_warriors/userprofile/"
LATE = "/admin/olympic_warriors/lateregistration/"


def make_edition(year, **kw):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19), **kw
    )


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class AdminSetup(TestCase):
    def setUp(self):
        self.orga = User.objects.create_superuser("admin", "a@b.c", "pw")
        self.client.force_login(self.orga)
        self.old = make_edition(2026)
        self.edition = make_edition(2027)
        self.ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        self.bob = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        self.player = Player.objects.create(user=self.ana, edition=self.old, rating=5)

    def act(self, url, action, *ids):
        response = self.client.post(
            url, {"action": action, "_selected_action": list(ids), "index": 0}, follow=True
        )
        return [str(m) for m in response.context["messages"]]


class TestEditionPage(AdminSetup):
    def test_the_window_and_texts_are_edited_and_the_status_is_shown(self):
        response = self.client.get(f"{EDITIONS}{self.edition.pk}/change/")

        self.assertEqual(response.status_code, 200)
        for field in (
            "registration_opens", "registration_closes", "registration_intro_fr",
            "registration_intro_en", "skills_month_fr", "skills_month_en",
        ):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, "Fermée")  # no questionnaire, no opening date yet

    def test_the_status_reads_open_once_configured(self):
        RegistrationSkill.objects.create(
            edition=self.edition, name_fr="C", name_en="C", identifier="CARD", weight=1
        )
        Edition.objects.filter(pk=self.edition.pk).update(
            registration_opens=date(2020, 1, 1), registration_closes=date(2999, 1, 1)
        )

        response = self.client.get(f"{EDITIONS}{self.edition.pk}/change/")

        self.assertContains(response, "Ouverte")

    def test_the_add_page_renders(self):
        self.assertEqual(self.client.get(f"{EDITIONS}add/").status_code, 200)


class TestGrantLatePass(AdminSetup):
    def test_from_the_player_list(self):
        messages = self.act(PLAYERS, "grant_late_pass", self.player.pk)

        pass_ = LateRegistration.objects.get()
        self.assertEqual((pass_.user, pass_.edition, pass_.granted_by), (self.ana, self.edition, self.orga))
        self.assertEqual(messages, ["Inscription tardive accordée pour 2027 à : Ana Lopez (ana)."])

    def test_from_the_profile_list_and_for_a_user_with_no_player(self):
        profile = UserProfile.objects.create(user=self.bob, invited=True)

        self.act(PROFILES, "grant_late_pass", profile.pk)

        self.assertTrue(LateRegistration.objects.filter(user=self.bob, edition=self.edition).exists())

    def test_a_second_grant_is_reported_not_duplicated(self):
        self.act(PLAYERS, "grant_late_pass", self.player.pk)

        messages = self.act(PLAYERS, "grant_late_pass", self.player.pk)

        self.assertEqual(LateRegistration.objects.count(), 1)
        self.assertEqual(messages, ["Inscription tardive déjà accordée à : Ana Lopez (ana)."])

    def test_it_targets_the_latest_edition(self):
        make_edition(2028)

        self.act(PLAYERS, "grant_late_pass", self.player.pk)

        self.assertEqual(LateRegistration.objects.get().edition.year, 2028)


class TestInvitedColumn(AdminSetup):
    def test_the_profile_list_filters_on_invited_and_edits_it_in_place(self):
        UserProfile.objects.create(user=self.bob, invited=True)
        UserProfile.objects.create(user=self.ana)

        response = self.client.get(PROFILES, {"invited__exact": "1"})

        self.assertEqual({str(p) for p in response.context["cl"].result_list}, {"Bob Martin"})
        self.assertIn("invited", UserProfileAdmin.list_editable)
        self.assertIn("invited", UserProfileAdmin.list_display)

    def test_the_change_form_carries_the_flag(self):
        profile = UserProfile.objects.create(user=self.bob, invited=True)

        response = self.client.get(f"{PROFILES}{profile.pk}/change/")

        self.assertContains(response, 'name="invited"')


class TestLateRegistrationAdmin(AdminSetup):
    def test_lists_and_revokes_but_never_adds(self):
        late = LateRegistration.objects.create(user=self.ana, edition=self.edition, granted_by=self.orga)

        self.assertContains(self.client.get(LATE), "ana")
        self.assertEqual(self.client.get(f"{LATE}add/").status_code, 403)
        self.client.post(f"{LATE}{late.pk}/delete/", {"post": "yes"})
        self.assertEqual(LateRegistration.objects.count(), 0)