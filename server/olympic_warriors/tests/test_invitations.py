"""The bulk invite: who is created, who is reused, who is refused."""
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import timezone

from olympic_warriors.invitations import (
    CONFLICT, CREATED, DUPLICATE, MALFORMED, REUSED, STAFF, invite, parse_lines,
)
from olympic_warriors.models import Edition, LateRegistration, Player, UserProfile

PUBLIC = override_settings(PUBLIC_URL="https://ow.example")


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


class TestParseLines(TestCase):
    def test_name_and_email_per_line(self):
        entries, problems = parse_lines(
            "Léa Martin, lea@example.com\n\n  Jean  Dupont ,JEAN@Example.com \nAdrien, a@example.com"
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(e.line, e.first_name, e.last_name, e.email) for e in entries],
            [
                (1, "Léa", "Martin", "lea@example.com"),
                (3, "Jean", "Dupont", "jean@example.com"),
                (4, "Adrien", "", "a@example.com"),
            ],
        )

    def test_an_optional_third_column_sets_the_username(self):
        entries, problems = parse_lines("Marie Martin, marie@example.com, Mariemartin2")

        self.assertEqual(problems, [])
        self.assertEqual(entries[0].username, "mariemartin2")
        self.assertEqual((entries[0].first_name, entries[0].last_name), ("Marie", "Martin"))

    def test_a_bad_identifier_or_too_many_columns_is_a_problem(self):
        entries, problems = parse_lines(
            "A B, a@example.com, has space\nC D, c@example.com, x, y\nE F, e@example.com, "
            + "z" * 151
        )

        self.assertEqual(entries, [])
        self.assertEqual([p.line for p in problems], [1, 2, 3])

    def test_malformed_lines_are_reported_with_their_number(self):
        entries, problems = parse_lines(
            "no comma here\nLéa, not-an-email\n, lea@example.com\nOk Name, ok@example.com\n"
            "Ola, x@olympicwarriors.com"
        )

        self.assertEqual([e.email for e in entries], ["ok@example.com"])
        self.assertEqual([p.line for p in problems], [1, 2, 3, 5])


@PUBLIC
class TestInvite(TestCase):
    def run_invite(self, text, **kw):
        entries, problems = parse_lines(text)
        return invite(entries, problems, **kw)

    def test_a_newcomer_is_created_invited_with_a_claim_link(self):
        [result] = self.run_invite("Léa Martin, lea@example.com")

        user = User.objects.get(username="léamartin")
        self.assertEqual(result.status, CREATED)
        self.assertEqual((user.first_name, user.last_name, user.email), ("Léa", "Martin", "lea@example.com"))
        self.assertTrue(user.has_usable_password())  # a random one nobody receives
        self.assertTrue(UserProfile.objects.get(user=user).invited)
        self.assertTrue(result.link.startswith("https://ow.example/claim/"))
        self.assertEqual(result.warning, "")

    def test_a_returning_player_is_matched_by_a_real_email(self):
        user = User.objects.create(username="whatever", email="lea@example.com")
        Player.objects.create(user=user, edition=make_edition(2026), rating=5)

        [result] = self.run_invite("Léa Martin, LEA@example.com")

        self.assertEqual((result.status, result.user_id), (REUSED, user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(UserProfile.objects.filter(user=user, invited=True).exists())  # a person already

    def test_a_placeholder_account_is_matched_by_username_and_gets_the_real_email(self):
        user = User.objects.create(username="léamartin", email="léamartin@olympicwarriors.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        user.refresh_from_db()
        self.assertEqual((result.status, user.email), (REUSED, "lea@example.com"))
        self.assertTrue(UserProfile.objects.get(user=user).invited)  # not a person: needs the flag

    def test_a_username_taken_by_another_real_email_is_a_conflict(self):
        User.objects.create(username="léamartin", email="other@example.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, CONFLICT)
        self.assertEqual(result.link, "")
        self.assertEqual(User.objects.count(), 1)

    def test_two_accounts_with_the_same_email_are_a_conflict(self):
        User.objects.create(username="a", email="lea@example.com")
        User.objects.create(username="b", email="LEA@example.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, CONFLICT)

    def test_a_deactivated_account_is_a_conflict(self):
        User.objects.create(username="gone", email="gone@example.com", is_active=False)

        [result] = self.run_invite("Gone Away, gone@example.com")

        self.assertEqual((result.status, result.link), (CONFLICT, ""))

    def test_a_staff_account_is_flagged_invited_with_no_link_ever(self):
        boss = User.objects.create(username="boss", email="boss@example.com", is_staff=True)

        [result] = self.run_invite("Big Boss, boss@example.com")

        self.assertEqual((result.status, result.link), (STAFF, ""))
        self.assertIn("/register", result.detail)
        self.assertTrue(UserProfile.objects.get(user=boss).invited)

    def test_the_late_pass_checkbox_reaches_a_staff_account_too(self):
        make_edition()
        boss = User.objects.create(username="boss", email="boss@example.com", is_staff=True)

        [result] = self.run_invite("Big Boss, boss@example.com", grant_late_pass=True)

        self.assertTrue(result.late_pass)
        self.assertTrue(LateRegistration.objects.filter(user=boss).exists())

    def test_the_identifier_column_lets_a_namesake_be_invited(self):
        User.objects.create(username="mariemartin", email="first@example.com")

        [conflict] = self.run_invite("Marie Martin, second@example.com")
        [created] = self.run_invite("Marie Martin, second@example.com, mariemartin2")

        self.assertEqual(conflict.status, CONFLICT)
        self.assertIn("identifiant", conflict.detail)
        self.assertEqual(created.status, CREATED)
        self.assertTrue(User.objects.filter(username="mariemartin2", last_name="Martin").exists())

    def test_an_already_activated_account_gets_a_link_with_a_warning(self):
        user = User.objects.create(username="lea", email="lea@example.com")
        Player.objects.create(user=user, edition=make_edition(2026), rating=5)
        UserProfile.objects.create(user=user, claimed_at=timezone.now())

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, REUSED)
        self.assertTrue(result.link.startswith("https://ow.example/claim/"))
        self.assertIn("réinitialise", result.warning)

    def test_duplicates_inside_the_paste_are_skipped(self):
        results = self.run_invite("Léa Martin, lea@example.com\nLea Other, lea@example.com\nLéa Martin, b@example.com")

        self.assertEqual([r.status for r in results], [CREATED, DUPLICATE, DUPLICATE])
        self.assertEqual(User.objects.count(), 1)

    def test_malformed_lines_are_reported_and_the_rest_is_processed(self):
        results = self.run_invite("garbage\nLéa Martin, lea@example.com")

        self.assertEqual([(r.line, r.status) for r in results], [(1, MALFORMED), (2, CREATED)])

    def test_the_late_pass_checkbox_grants_a_pass_to_everyone_invited(self):
        edition = make_edition()
        existing = User.objects.create(username="bob", email="bob@example.com")
        Player.objects.create(user=existing, edition=make_edition(2026), rating=5)
        orga = User.objects.create(username="orga", is_staff=True)

        results = self.run_invite(
            "Léa Martin, lea@example.com\nBob X, bob@example.com\nBad Line",
            grant_late_pass=True, granted_by=orga,
        )

        self.assertEqual(LateRegistration.objects.filter(edition=edition).count(), 2)
        self.assertEqual(LateRegistration.objects.first().granted_by, orga)
        self.assertEqual([r.late_pass for r in results], [True, True, False])

    def test_without_a_public_url_nothing_is_created(self):
        with override_settings(PUBLIC_URL=""), self.assertRaises(ImproperlyConfigured):
            self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(User.objects.count(), 0)

    def test_the_late_pass_needs_an_edition(self):
        with self.assertRaises(LookupError):
            self.run_invite("Léa Martin, lea@example.com", grant_late_pass=True)

        self.assertEqual(User.objects.count(), 0)
