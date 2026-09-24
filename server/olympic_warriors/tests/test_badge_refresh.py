"""
Tests for badges.refresh() and what calls it: the refresh stores the difference between
earned() and the stored computed rows, and never touches the manual ones. The
refresh_badges command, the Edition admin action and a real import_edition run it; the
Badge admin gives badges by hand and only revokes computed ones.
"""

import json
import os
import tempfile
from collections import Counter
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from olympic_warriors.badges import RefreshReport, earned, refresh
from olympic_warriors.models import MANUAL_CODES, Badge, BadgeRefresh, Team
from olympic_warriors.tests.test_badges import PLACE_CODES, TODAY, World

C = Badge.Codes

# What identifies a computed row.
KEY = ("user_id", "code", "edition_id", "tier", "discipline", "partner_id")


def stored():
    """The keys of the stored computed rows, with how many rows each."""
    return Counter(Badge.objects.filter(is_manual=False).values_list(*KEY))


def wanted(today=TODAY):
    """The keys of earned(today), once each."""
    return Counter(tuple(getattr(badge, field) for field in KEY) for badge in earned(today))


def rows():
    """Every row, with its id, creation time and state, in id order."""
    return list(
        Badge.objects.order_by("id").values_list("id", "created_at", "is_active", "is_manual", *KEY)
    )


class TestRefresh(World, TestCase):
    """A hand-ranked 4-team edition of 2024 with Ana, Bob, Cat and Dan on teams 1 to 4, plus
    the default teamless spectator."""

    def setUp(self):
        self.e2024, self.teams = self.edition(2024)
        self.people = [self.person(n) for n in ("Ana", "Bob", "Cat", "Dan")]
        self.ana, self.bob, self.cat, self.dan = self.people
        for user, team in zip(self.people, self.teams):
            self.seat(user, self.e2024, team)

    @staticmethod
    def codes(user, *codes):
        """The codes of the user's stored rows among `codes`, sorted."""
        found = Badge.objects.filter(user=user, code__in=codes)
        return sorted(found.values_list("code", flat=True))

    def places(self, user):
        """The codes of the user's stored place rows, sorted."""
        return self.codes(user, *PLACE_CODES)

    def test_the_first_run_stores_what_was_earned(self):
        # The four places, a rookie and an argonaut each (the first finished edition), and
        # the spectator's own rookie and argonaut.
        expected = wanted()

        report = refresh(TODAY)

        self.assertEqual(stored(), expected)
        for user, code in zip(self.people, (C.CHAMPION, C.RUNNER_UP, C.BRONZE, C.WOODEN_SPOON)):
            self.assertEqual(self.places(user), [code])
            self.assertEqual(self.codes(user, C.ROOKIE, C.ARGONAUT), [C.ARGONAUT, C.ROOKIE])
        self.assertFalse(Badge.objects.filter(is_active=False).exists())
        self.assertEqual(
            (report.added, report.removed, report.kept), (sum(expected.values()), 0, 0)
        )
        self.assertIsNotNone(report.refreshed_at)
        self.assertEqual(BadgeRefresh.objects.get(pk=1).refreshed_at, report.refreshed_at)

    def test_a_second_run_writes_nothing(self):
        refresh(TODAY)
        before = rows()

        report = refresh(TODAY)

        self.assertEqual((report.added, report.removed, report.kept), (0, 0, len(before)))
        self.assertEqual(rows(), before)

    def test_a_correction_deletes_what_is_no_longer_earned(self):
        refresh(TODAY)
        old = Badge.objects.get(user=self.ana, code=C.CHAMPION)
        first, second = self.teams[:2]
        Team.objects.filter(pk=first.pk).update(final_rank=2)
        Team.objects.filter(pk=second.pk).update(final_rank=1)

        report = refresh(TODAY)

        self.assertFalse(Badge.objects.filter(pk=old.pk).exists())
        self.assertEqual(self.places(self.ana), [C.RUNNER_UP])
        self.assertEqual(self.places(self.bob), [C.CHAMPION])
        self.assertEqual((report.added, report.removed), (2, 2))  # the two swapped places
        self.assertEqual(stored(), wanted())

    def test_a_revoked_row_stays_revoked(self):
        refresh(TODAY)
        revoked = Badge.objects.get(user=self.ana, code=C.CHAMPION)
        Badge.objects.filter(pk=revoked.pk).update(is_active=False)

        report = refresh(TODAY)

        self.assertEqual((report.added, report.removed), (0, 0))
        self.assertFalse(Badge.objects.get(pk=revoked.pk).is_active)

    def test_a_revoked_row_no_longer_earned_is_deleted(self):
        refresh(TODAY)
        revoked = Badge.objects.get(user=self.ana, code=C.CHAMPION)
        Badge.objects.filter(pk=revoked.pk).update(is_active=False)
        Team.objects.filter(pk=self.teams[0].pk).update(final_rank=2)
        Team.objects.filter(pk=self.teams[1].pk).update(final_rank=1)

        refresh(TODAY)

        self.assertFalse(Badge.objects.filter(pk=revoked.pk).exists())
        self.assertEqual(self.places(self.ana), [C.RUNNER_UP])

    def test_manual_rows_are_untouched(self):
        mvp = Badge.objects.create(
            user=self.ana, code=C.MVP, edition=self.e2024, is_manual=True, note="Try of the day"
        )
        before = Badge.objects.filter(pk=mvp.pk).values().get()

        refresh(TODAY)
        refresh(TODAY)

        self.assertEqual(Badge.objects.filter(pk=mvp.pk).values().get(), before)

    def test_duplicates_collapse(self):
        refresh(TODAY)
        kept = Badge.objects.get(user=self.ana, code=C.CHAMPION)
        # Without a partner, the constraint lets the same key in twice.
        Badge.objects.create(user=self.ana, code=C.CHAMPION, edition=self.e2024)

        report = refresh(TODAY)

        self.assertEqual(
            list(Badge.objects.filter(user=self.ana, code=C.CHAMPION).values_list("id", flat=True)),
            [kept.pk],
        )
        self.assertEqual((report.added, report.removed), (0, 1))
        self.assertEqual(stored(), wanted())

    def test_a_duplicate_keeps_the_revocation(self):
        refresh(TODAY)
        first = Badge.objects.get(user=self.ana, code=C.CHAMPION)
        revoked = Badge.objects.create(
            user=self.ana, code=C.CHAMPION, edition=self.e2024, is_active=False
        )
        self.assertGreater(revoked.pk, first.pk)

        report = refresh(TODAY)

        self.assertEqual(
            list(
                Badge.objects.filter(user=self.ana, code=C.CHAMPION).values_list(
                    "id", "is_active"
                )
            ),
            [(revoked.pk, False)],
        )
        self.assertEqual((report.added, report.removed), (0, 1))

    def deactivate(self, active=False):
        """Deactivate the 2024 edition (or reactivate it) as the admin would."""
        self.e2024.is_active = active
        self.e2024.save()

    def test_an_inactive_edition_keeps_its_rows(self):
        # Out of the sequence, the edition earns nothing: its rows, revoked or not, are
        # left alone rather than deleted.
        refresh(TODAY)
        Badge.objects.filter(user=self.ana, code=C.CHAMPION).update(is_active=False)
        before = rows()
        self.deactivate()

        report = refresh(TODAY)

        self.assertEqual((report.added, report.removed, report.kept), (0, 0, 0))
        self.assertEqual(rows(), before)
        self.assertFalse(Badge.objects.get(user=self.ana, code=C.CHAMPION).is_active)

    def test_a_reactivated_edition_gets_its_rows_back_as_they_were(self):
        refresh(TODAY)
        Badge.objects.filter(user=self.ana, code=C.CHAMPION).update(is_active=False)
        before = rows()
        self.deactivate()
        refresh(TODAY)
        self.deactivate(active=True)

        report = refresh(TODAY)

        self.assertEqual((report.added, report.removed, report.kept), (0, 0, len(before)))
        self.assertEqual(rows(), before)  # created_at and the revocation included
        self.assertFalse(Badge.objects.get(user=self.ana, code=C.CHAMPION).is_active)

    def test_the_lock_row_comes_back(self):
        BadgeRefresh.objects.all().delete()

        report = refresh(TODAY)

        self.assertEqual(list(BadgeRefresh.objects.values_list("pk", flat=True)), [1])
        self.assertEqual(BadgeRefresh.objects.get(pk=1).refreshed_at, report.refreshed_at)
        self.assertEqual(stored(), wanted())

    def test_the_command_refreshes_and_prints_the_counts_and_the_time(self):
        out = StringIO()
        with mock.patch("olympic_warriors.badges.paris_today", return_value=TODAY):
            call_command("refresh_badges", stdout=out)

        refreshed_at = BadgeRefresh.objects.get(pk=1).refreshed_at
        self.assertEqual(
            out.getvalue(),
            f"Badges: {sum(wanted().values())} added, 0 removed, 0 kept. "
            f"Refreshed at {refreshed_at.isoformat()}.\n",
        )
        self.assertEqual(stored(), wanted())


def a_report():
    """What a patched refresh returns."""
    return RefreshReport(added=3, removed=1, kept=2, refreshed_at=timezone.now())


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestBadgeAdmin(World, TestCase):
    """The Badge admin and the Edition changelist action, as a superuser."""

    BADGES = "/admin/olympic_warriors/badge/"

    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.e2024, _ = self.edition(2024, spectator=False)
        self.ana = self.person("Ana")

    def test_the_edition_action_refreshes_every_badge(self):
        with mock.patch("olympic_warriors.admin.refresh", return_value=a_report()) as patched:
            response = self.client.post(
                "/admin/olympic_warriors/edition/",
                {"action": "refresh_badges", "_selected_action": [self.e2024.id], "index": 0},
                follow=True,
            )

        patched.assert_called_once_with()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [str(message) for message in response.context["messages"]],
            ["Badges recalculés : 3 ajoutés, 1 retirés, 2 inchangés."],
        )

    def test_the_changelist_lists_active_rows_unless_asked(self):
        shown = Badge.objects.create(user=self.ana, code=Badge.Codes.CHAMPION, edition=self.e2024)
        revoked = Badge.objects.create(
            user=self.ana, code=Badge.Codes.ROOKIE, edition=self.e2024, is_active=False
        )

        response = self.client.get(self.BADGES)
        inactive = self.client.get(self.BADGES, {"is_active__exact": "0"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].result_list), [shown])
        self.assertEqual(list(inactive.context["cl"].result_list), [revoked])

    def test_the_add_page_offers_only_the_manual_codes(self):
        response = self.client.get(f"{self.BADGES}add/")

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertEqual(list(form.fields), ["user", "code", "edition", "note", "is_active"])
        self.assertEqual(
            [value for value, _ in form.fields["code"].choices],
            [value for value in Badge.Codes.values if value in MANUAL_CODES],
        )
        self.assertEqual(len(MANUAL_CODES), 6)
        self.assertNotContains(response, 'value="champion"')
        for field in ("tier", "discipline", "partner"):
            self.assertNotContains(response, f'name="{field}"')

    def test_adding_through_the_admin_gives_a_manual_badge(self):
        response = self.client.post(
            f"{self.BADGES}add/",
            {
                "user": self.ana.id,
                "code": Badge.Codes.MVP,
                "edition": self.e2024.id,
                "note": "Try of the day",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        badge = Badge.objects.get()
        self.assertEqual(
            (badge.user, badge.code, badge.edition, badge.note, badge.is_manual, badge.is_active),
            (self.ana, Badge.Codes.MVP, self.e2024, "Try of the day", True, True),
        )

    def test_a_computed_code_cannot_be_added_by_hand(self):
        response = self.client.post(
            f"{self.BADGES}add/",
            {"user": self.ana.id, "code": Badge.Codes.CHAMPION, "edition": self.e2024.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.context["adminform"].form.errors)
        self.assertFalse(Badge.objects.exists())

    def test_a_computed_row_only_edits_is_active(self):
        bob = self.person("Bob")
        badge = Badge.objects.create(
            user=self.ana, code=Badge.Codes.COMRADES, edition=self.e2024, partner=bob
        )
        url = f"{self.BADGES}{badge.id}/change/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        adminform = response.context["adminform"]
        self.assertEqual(list(adminform.form.fields), ["is_active"])
        self.assertEqual(
            tuple(adminform.readonly_fields),
            ("user", "code", "edition", "tier", "discipline", "partner"),
        )

        # The checkbox left off; a posted code is not a field of the form, so it is ignored.
        response = self.client.post(url, {"code": Badge.Codes.MVP})

        self.assertEqual(response.status_code, 302)
        badge.refresh_from_db()
        self.assertEqual(
            (badge.code, badge.partner, badge.is_manual, badge.is_active),
            (Badge.Codes.COMRADES, bob, False, False),
        )

    def test_a_manual_row_stays_editable(self):
        badge = Badge.objects.create(
            user=self.ana, code=Badge.Codes.MVP, edition=self.e2024, is_manual=True
        )

        response = self.client.get(f"{self.BADGES}{badge.id}/change/")

        self.assertEqual(response.status_code, 200)
        adminform = response.context["adminform"]
        self.assertEqual(
            list(adminform.form.fields), ["user", "code", "edition", "note", "is_active"]
        )
        self.assertEqual(tuple(adminform.readonly_fields), ())


class TestImportRefresh(TestCase):
    """import_edition refreshes the badges after a real import, never after a dry run."""

    COMMAND = "olympic_warriors.management.commands.import_edition"
    REPORT = {
        "year": 2024,
        "edition_id": 1,
        "users_reused": 0,
        "users_created": 0,
        "created_users": [],
        "counts": {},
        "missing_files": [],
    }

    def run_import(self, *args):
        """Run the command on a document holding {}, the import and the refresh patched."""
        folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "edition.json")
        with open(path, "w", encoding="utf-8") as dst:
            json.dump({}, dst)
        out = StringIO()
        with mock.patch(f"{self.COMMAND}.import_edition", return_value=self.REPORT), mock.patch(
            f"{self.COMMAND}.refresh", return_value=a_report()
        ) as patched:
            call_command("import_edition", path, *args, stdout=out)
        return patched, out.getvalue()

    def test_a_real_import_refreshes_the_badges(self):
        patched, out = self.run_import()

        patched.assert_called_once_with()
        self.assertIn("Imported edition 2024.", out)
        self.assertTrue(out.endswith("Badges: 3 added, 1 removed, 2 kept.\n"))

    def test_a_dry_run_does_not(self):
        patched, out = self.run_import("--dry-run")

        patched.assert_not_called()
        self.assertIn("Dry run: rolled back, nothing persisted.", out)
        self.assertNotIn("Badges:", out)
