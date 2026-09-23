"""
Assigning teams to players: Player.clean() refuses a team of another edition and a second
active row for the same person and edition, and the Player changelist edits the team with
teams labelled by year.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from django.forms import inlineformset_factory

from olympic_warriors.admin import PlayerInlineForm
from olympic_warriors.models import Edition, Player, Team

CHANGELIST = "/admin/olympic_warriors/player/"


class PlayerSetup:
    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2026 = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.mxm_2024 = Team.objects.create(name="MxM", edition=self.y2024)
        self.mxm_2026 = Team.objects.create(name="MxM", edition=self.y2026)
        self.ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        self.player = Player.objects.create(user=self.ana, edition=self.y2026, rating=5)


class TestPlayerClean(PlayerSetup, TestCase):
    def test_a_team_of_the_same_edition_is_accepted(self):
        self.player.team = self.mxm_2026
        self.player.full_clean()

    def test_a_team_of_another_edition_is_refused_on_team(self):
        self.player.team = self.mxm_2024

        with self.assertRaises(ValidationError) as caught:
            self.player.full_clean()
        self.assertIn("team", caught.exception.message_dict)

    def test_a_second_active_row_for_the_same_person_and_edition_is_refused_on_team(self):
        second = Player(user=self.ana, edition=self.y2026, rating=5)

        with self.assertRaises(ValidationError) as caught:
            second.full_clean()
        self.assertIn("team", caught.exception.message_dict)

    def test_an_inactive_duplicate_and_another_edition_are_accepted(self):
        Player(user=self.ana, edition=self.y2026, rating=5, is_active=False).full_clean()
        Player(user=self.ana, edition=self.y2024, rating=5).full_clean()
        self.player.full_clean()  # the only active row of 2026 for Ana


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestPlayerChangelist(PlayerSetup, TestCase):
    def setUp(self):
        super().setUp()
        root = User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(root)

    def save_team(self, team):
        return self.client.post(
            CHANGELIST,
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(self.player.id),
                "form-0-team": str(team.id),
                "_save": "Save",
            },
        )

    def test_team_is_editable_from_the_changelist(self):
        response = self.save_team(self.mxm_2026)

        self.assertEqual(response.status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.team, self.mxm_2026)

    def test_a_team_of_another_edition_shows_an_error_on_the_row(self):
        response = self.save_team(self.mxm_2024)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "belongs to another edition")
        self.player.refresh_from_db()
        self.assertIsNone(self.player.team)

    def test_team_choices_carry_their_year_newest_first(self):
        content = self.client.get(CHANGELIST).content.decode()

        self.assertIn("MxM (2026)", content)
        self.assertIn("MxM (2024)", content)
        self.assertLess(content.index("MxM (2026)"), content.index("MxM (2024)"))


class TestPlayerInlineForm(PlayerSetup, TestCase):
    """On the team page, `team` is the inline's hidden foreign key: its errors must still show."""

    def test_team_errors_show_among_the_row_errors(self):
        formset_class = inlineformset_factory(
            Team, Player, form=PlayerInlineForm, fields=["user", "edition", "rating", "is_active"]
        )
        formset = formset_class(
            {
                "player_set-TOTAL_FORMS": "1",
                "player_set-INITIAL_FORMS": "0",
                "player_set-MIN_NUM_FORMS": "0",
                "player_set-MAX_NUM_FORMS": "1000",
                "player_set-0-user": str(self.ana.id),
                "player_set-0-edition": str(self.y2026.id),
                "player_set-0-rating": "5",
                "player_set-0-is_active": "on",
            },
            instance=self.mxm_2026,
        )

        self.assertFalse(formset.is_valid())  # Ana already has an active 2026 player
        self.assertIn("already has an active player", str(formset.forms[0].non_field_errors()))
