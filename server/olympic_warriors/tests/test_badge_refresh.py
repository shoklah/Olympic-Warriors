"""
Tests for badges.refresh() and what calls it: the refresh stores the difference between
compute() and the stored computed badge rows, never touching the manual ones, and between
it and the stored progress rows. The refresh_badges command (with --if-due, only when
refresh_due() says so), the Edition admin action and a real import_edition run it; the
Badge admin gives badges by hand and only revokes computed ones.
"""

import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest import mock

from django.contrib.admin import site
from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings

from olympic_warriors.badges import (
    Progress,
    RefreshReport,
    compute,
    earned,
    refresh,
    refresh_due,
)
from olympic_warriors.models import (
    MANUAL_CODES,
    Badge,
    BadgeProgress,
    BadgeRefresh,
    Edition,
    Relay,
    Team,
)
from olympic_warriors.tests.test_badges import (
    BADGES_QUERIES,
    PLACE_CODES,
    TODAY,
    DisciplineWorld,
    World,
)

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


# A progress row's fields, in Progress's order.
PROGRESS = ("user_id", "code", "value", "best", "reachable", "discipline", "partner_id", "year")


def stored_progress():
    """The stored progress rows, as a set of Progress."""
    return {Progress(*row) for row in BadgeProgress.objects.values_list(*PROGRESS)}


def wanted_progress(today=TODAY):
    """The progress rows of compute(today)."""
    return compute(today)[1]


def progress_rows():
    """Every progress row with its id, in id order."""
    return list(BadgeProgress.objects.order_by("id").values_list("id", *PROGRESS))


def written(before, after):
    """How many progress rows differ between two progress_rows() lists: created, updated
    in place or deleted (a row deleted and created again counts twice)."""
    old, new = ({pk: fields for pk, *fields in listed} for listed in (before, after))
    both = old.keys() & new.keys()
    return len(old.keys() ^ new.keys()) + sum(old[pk] != new[pk] for pk in both)


def stamp(moment):
    """Record `moment` as the end of the last refresh (None: never refreshed)."""
    BadgeRefresh.objects.update_or_create(pk=1, defaults={"refreshed_at": moment})


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

    @staticmethod
    def progress(user, code):
        """The user's stored progress row for `code`, as a Progress, or None."""
        row = BadgeProgress.objects.filter(user=user, code=code).values_list(*PROGRESS).first()
        return None if row is None else Progress(*row)

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

    def test_the_first_run_stores_the_progress(self):
        expected = wanted_progress()

        report = refresh(TODAY)

        self.assertEqual(stored_progress(), expected)
        self.assertEqual(report.progress, len(expected))
        # Ana won 2024: one edition played, and the 2nd places are out of her reach.
        self.assertEqual(self.progress(self.ana, C.VETERAN), Progress(self.ana.id, C.VETERAN, 1))
        self.assertEqual(
            self.progress(self.ana, C.ETERNAL_SECOND),
            Progress(self.ana.id, C.ETERNAL_SECOND, None, reachable=False),
        )

    def test_a_second_run_writes_nothing(self):
        refresh(TODAY)
        before, progress_before = rows(), progress_rows()

        report = refresh(TODAY)

        self.assertEqual(
            (report.added, report.removed, report.kept, report.progress), (0, 0, len(before), 0)
        )
        self.assertEqual(rows(), before)
        self.assertEqual(progress_rows(), progress_before)

    def test_a_second_run_runs_a_fixed_number_of_queries(self):
        refresh(TODAY)

        # compute() on one edition, the lock (get_or_create, then select_for_update), the
        # stored badge rows, the stored progress rows and the stamp, plus the SAVEPOINT and
        # RELEASE of a transaction nested in the test's own (outside a test, the
        # transaction's BEGIN and COMMIT go unlogged).
        with self.assertNumQueries(BADGES_QUERIES(1) + REFRESH_OWN_QUERIES):
            report = refresh(TODAY)

        self.assertEqual((report.added, report.removed, report.progress), (0, 0, 0))

    def test_each_kind_of_progress_write_costs_one_query(self):
        refresh(TODAY)
        tampered = {
            # created again
            "missing": lambda: BadgeProgress.objects.filter(user=self.ana, code=C.VETERAN).delete(),
            # updated in place
            "wrong": lambda: BadgeProgress.objects.filter(user=self.bob, code=C.VETERAN).update(
                value=7
            ),
            # deleted: champion has no progress
            "stray": lambda: BadgeProgress.objects.create(user=self.cat, code=C.CHAMPION, value=1),
        }
        for name, tamper in tampered.items():
            with self.subTest(name):
                tamper()

                with self.assertNumQueries(BADGES_QUERIES(1) + REFRESH_OWN_QUERIES + 1):
                    report = refresh(TODAY)

                self.assertEqual((report.added, report.removed, report.progress), (0, 0, 1))
                self.assertEqual(stored_progress(), wanted_progress())

        for tamper in tampered.values():
            tamper()

        with self.assertNumQueries(BADGES_QUERIES(1) + REFRESH_OWN_QUERIES + 3):
            report = refresh(TODAY)

        self.assertEqual((report.added, report.removed, report.progress), (0, 0, 3))
        self.assertEqual(stored_progress(), wanted_progress())

    def test_a_changed_count_updates_its_row_in_place(self):
        # Eve joins Ana's team: Ana's networker and comrades rows now count her, and Eve
        # gets rows of her own; nobody else's row changes.
        refresh(TODAY)
        before = progress_rows()
        networker = BadgeProgress.objects.get(user=self.ana, code=C.NETWORKER)
        eve = self.person("Eve")
        self.seat(eve, self.e2024, self.teams[0])

        report = refresh(TODAY)

        self.assertEqual(stored_progress(), wanted_progress())
        self.assertEqual(
            self.progress(self.ana, C.NETWORKER), Progress(self.ana.id, C.NETWORKER, 1)
        )
        self.assertEqual(
            self.progress(self.ana, C.COMRADES),
            Progress(self.ana.id, C.COMRADES, 1, partner_id=eve.id),
        )
        self.assertEqual(
            BadgeProgress.objects.get(user=self.ana, code=C.NETWORKER).pk, networker.pk
        )
        self.assertEqual(report.progress, 2 + BadgeProgress.objects.filter(user=eve).count())
        self.assertEqual(written(before, progress_rows()), report.progress)

    def test_a_row_no_longer_computed_is_deleted(self):
        # Bob, 2nd in 2024, is 2nd again in 2025: he earns eternal-second, whose bar goes.
        refresh(TODAY)
        self.assertEqual(
            self.progress(self.bob, C.ETERNAL_SECOND), Progress(self.bob.id, C.ETERNAL_SECOND, 1)
        )
        before = progress_rows()
        e2025, teams = self.edition(2025)
        self.seat(self.bob, e2025, teams[1])

        report = refresh(TODAY)

        self.assertEqual(self.codes(self.bob, C.ETERNAL_SECOND), [C.ETERNAL_SECOND])
        self.assertIsNone(self.progress(self.bob, C.ETERNAL_SECOND))
        self.assertEqual(stored_progress(), wanted_progress())
        self.assertEqual(written(before, progress_rows()), report.progress)

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
        self.assertEqual((report.added, report.removed), (3, 3))  # the two swapped places and goat
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

    def test_the_progress_follows_an_inactive_edition(self):
        # Unlike the badges, a progress row has no edition to keep it by: out of the
        # history, 2024's people have no row, and they get them back once it is reactivated.
        refresh(TODAY)
        expected = stored_progress()
        self.deactivate()

        report = refresh(TODAY)

        self.assertFalse(BadgeProgress.objects.exists())
        self.assertEqual(report.progress, len(expected))

        self.deactivate(active=True)
        refresh(TODAY)

        self.assertEqual(stored_progress(), expected)

    def test_the_lock_row_comes_back(self):
        BadgeRefresh.objects.all().delete()

        report = refresh(TODAY)

        self.assertEqual(list(BadgeRefresh.objects.values_list("pk", flat=True)), [1])
        self.assertEqual(BadgeRefresh.objects.get(pk=1).refreshed_at, report.refreshed_at)
        self.assertEqual(stored(), wanted())

    @staticmethod
    def run_command(*args, today=TODAY):
        """Run refresh_badges with `args` on `today` (a Paris date); returns its output."""
        out = StringIO()
        with mock.patch(
            "olympic_warriors.management.commands.refresh_badges.paris_today", return_value=today
        ):
            call_command("refresh_badges", *args, stdout=out)
        return out.getvalue()

    @staticmethod
    def first_run_output(today=TODAY):
        """What the command prints after a first refresh on `today`."""
        refreshed_at = BadgeRefresh.objects.get(pk=1).refreshed_at
        return (
            f"Badges: {sum(wanted(today).values())} added, 0 removed, 0 kept. "
            f"Progress rows: {len(wanted_progress(today))} written. "
            f"Refreshed at {refreshed_at.isoformat()}.\n"
        )

    def test_the_command_refreshes_and_prints_the_counts_and_the_time(self):
        out = self.run_command()

        self.assertEqual(out, self.first_run_output())
        self.assertEqual(stored(), wanted())
        self.assertEqual(stored_progress(), wanted_progress())

    def test_a_dry_run_lists_the_rows_and_stores_nothing(self):
        out = self.run_command("--dry-run", "--verbose-rows")

        self.assertIn("Dry run: nothing was stored.", out)
        self.assertIn("+ ", out)
        self.assertEqual(stored(), {})
        self.assertFalse(Badge.objects.filter(is_manual=False).exists())

    def test_verbose_rows_lists_the_removed_ones_too(self):
        refresh(TODAY)
        first, second = self.teams[:2]
        Team.objects.filter(pk=first.pk).update(final_rank=2)
        Team.objects.filter(pk=second.pk).update(final_rank=1)

        out = self.run_command("--verbose-rows")

        self.assertIn("  - ", out)
        self.assertIn("  + ", out)

    def test_the_command_refreshes_even_when_not_due(self):
        stamp(datetime(2030, 12, 31, 10, tzinfo=dt_timezone.utc))  # the day before TODAY

        out = self.run_command()

        self.assertEqual(out, self.first_run_output())
        self.assertEqual(stored(), wanted())

    def test_if_due_refreshes_a_first_time(self):
        stamp(None)

        out = self.run_command("--if-due")

        self.assertEqual(out, self.first_run_output())
        self.assertEqual(stored(), wanted())
        self.assertEqual(stored_progress(), wanted_progress())

    def test_if_due_refreshes_the_morning_after_an_edition(self):
        # The last refresh ran during the 2024 edition, which ended on Sept 22.
        stamp(datetime(2024, 9, 21, 20, tzinfo=dt_timezone.utc))
        morning = date(2024, 9, 23)

        out = self.run_command("--if-due", today=morning)

        self.assertEqual(out, self.first_run_output(morning))
        self.assertEqual(stored(), wanted(morning))

    def test_if_due_writes_nothing_when_not_due(self):
        # 10:00 UTC on Dec 31, 2030 is 11:00 in Paris, the day before TODAY.
        last = datetime(2030, 12, 31, 10, tzinfo=dt_timezone.utc)
        stamp(last)

        with self.assertNumQueries(1):  # refresh_due()
            out = self.run_command("--if-due")

        self.assertEqual(out, "Nothing to refresh (last refresh 2030-12-31 11:00 Paris time).\n")
        self.assertFalse(Badge.objects.exists())
        self.assertFalse(BadgeProgress.objects.exists())
        self.assertEqual(BadgeRefresh.objects.get(pk=1).refreshed_at, last)

    def test_if_due_waits_for_the_end_of_an_edition(self):
        # On the edition's last day, it is not finished yet.
        stamp(datetime(2024, 9, 21, 20, tzinfo=dt_timezone.utc))

        out = self.run_command("--if-due", today=date(2024, 9, 22))

        self.assertEqual(out, "Nothing to refresh (last refresh 2024-09-21 22:00 Paris time).\n")
        self.assertFalse(Badge.objects.exists())


class TestMasterRefresh(DisciplineWorld, TestCase):
    """master is a title held, not earned for good: Ana won the relay of 2021 and 2022, so
    she holds it until the relay of 2023 is over."""

    def setUp(self):
        self.ana = self.person("Ana")
        self.win(self.ana, 2021, Relay)
        self.win(self.ana, 2022, Relay)
        self.e2023, _ = self.computed(2023, self.ana)
        refresh(date(2023, 1, 1))  # 2023 not finished yet
        self.held = Badge.objects.get(user=self.ana, code=C.MASTER)

    def test_a_master_held_on_keeps_its_row(self):
        self.results(Relay, self.e2023, [10, 0])
        Badge.objects.filter(pk=self.held.pk).update(is_active=False)  # revoked

        refresh(TODAY)

        kept = Badge.objects.get(user=self.ana, code=C.MASTER)
        self.assertEqual((kept.edition.year, kept.discipline), (2022, "Relay"))
        self.assertEqual((kept.pk, kept.created_at), (self.held.pk, self.held.created_at))
        self.assertFalse(kept.is_active)

    def test_a_master_lost_is_deleted(self):
        self.results(Relay, self.e2023, [0, 10])

        report = refresh(TODAY)

        self.assertFalse(Badge.objects.filter(code=C.MASTER).exists())
        self.assertEqual(report.removed, 1)  # master alone: every other badge stays
        self.assertEqual(stored(), wanted())


class TestRefreshDue(TestCase):
    """
    refresh_due(): whether refresh_badges --if-due refreshes on a Paris date. Unless a test
    says otherwise, the last refresh ended at REFRESHED_AT, 00:05 on July 1, 2031 in Paris
    but still June 30 in UTC, so the Paris date is the one that counts.
    """

    def setUp(self):
        stamp(REFRESHED_AT)

    def due(self, today):
        """refresh_due(today) as (due, refreshed_at), checking it costs 1 query."""
        with self.assertNumQueries(1):
            return refresh_due(today)

    @staticmethod
    def ending(end, is_active=True):
        """An edition of 2031 held on the two days up to `end`."""
        return Edition.objects.create(
            year=2031,
            host="Paris",
            start_date=end - timedelta(days=1),
            end_date=end,
            is_active=is_active,
        )

    def test_due_without_the_refresh_row(self):
        BadgeRefresh.objects.all().delete()

        self.assertEqual(self.due(date(2031, 7, 10)), (True, None))

    def test_due_when_never_refreshed(self):
        stamp(None)

        self.assertEqual(self.due(date(2031, 7, 10)), (True, None))

    def test_not_due_29_days_after_the_last_refresh(self):
        # 30 days after June 30, the refresh's date in UTC.
        self.assertEqual(self.due(date(2031, 7, 30)), (False, REFRESHED_AT))

    def test_due_30_days_after_the_last_refresh(self):
        self.assertEqual(self.due(date(2031, 7, 31)), (True, REFRESHED_AT))

    def test_not_due_for_an_edition_that_ended_before_the_last_refresh_date(self):
        # June 30, the date of the refresh in UTC, is the day before in Paris.
        self.ending(date(2031, 6, 30))

        self.assertEqual(self.due(date(2031, 7, 10)), (False, REFRESHED_AT))

    def test_due_after_an_edition_that_ended_on_the_last_refresh_date(self):
        # A refresh on an edition's last day ran before it was over.
        self.ending(date(2031, 7, 1))

        self.assertEqual(self.due(date(2031, 7, 2)), (True, REFRESHED_AT))

    def test_due_after_an_edition_that_ended_since_the_last_refresh(self):
        self.ending(date(2031, 7, 5))

        self.assertEqual(self.due(date(2031, 7, 6)), (True, REFRESHED_AT))
        self.assertEqual(self.due(date(2031, 7, 10)), (True, REFRESHED_AT))  # a missed night

    def test_not_due_on_the_last_day_of_an_edition(self):
        self.ending(date(2031, 7, 10))

        self.assertEqual(self.due(date(2031, 7, 10)), (False, REFRESHED_AT))
        self.assertEqual(self.due(date(2031, 7, 11)), (True, REFRESHED_AT))

    def test_not_due_during_an_edition(self):
        self.ending(date(2031, 7, 20))

        self.assertEqual(self.due(date(2031, 7, 10)), (False, REFRESHED_AT))

    def test_an_inactive_edition_is_ignored(self):
        self.ending(date(2031, 7, 5), is_active=False)

        self.assertEqual(self.due(date(2031, 7, 10)), (False, REFRESHED_AT))


# What refresh() adds to compute() on a run that writes no badge or progress row; each kind
# of write it needs (a badge delete or create, a progress delete, update or create) adds 1.
REFRESH_OWN_QUERIES = 7

# 22:05 UTC in summer is 00:05 the next day in Paris.
REFRESHED_AT = datetime(2031, 6, 30, 22, 5, tzinfo=dt_timezone.utc)


def a_report():
    """What a patched refresh returns."""
    return RefreshReport(added=3, removed=1, kept=2, progress=4, refreshed_at=REFRESHED_AT)


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestBadgeAdmin(World, TestCase):
    """The Badge admin and the Edition changelist action, as a superuser."""

    BADGES = "/admin/olympic_warriors/badge/"
    EDITIONS = "/admin/olympic_warriors/edition/"

    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.e2024, _ = self.edition(2024, spectator=False)
        self.ana = self.person("Ana")

    def test_the_edition_action_refreshes_every_badge(self):
        with mock.patch("olympic_warriors.admin.refresh", return_value=a_report()) as patched:
            response = self.client.post(
                self.EDITIONS,
                {"action": "refresh_badges", "_selected_action": [self.e2024.id], "index": 0},
                follow=True,
            )

        patched.assert_called_once_with()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [str(message) for message in response.context["messages"]],
            [
                "Badges recalculés à 00:05 (heure de Paris) : "
                "ajout(s) 3, retrait(s) 1, inchangé(s) 2. "
                "Progression : 4 ligne(s) mise(s) à jour."
            ],
        )

    def test_a_view_only_user_does_not_get_the_edition_action(self):
        viewer = User.objects.create_user("viewer", password="pw", is_staff=True)
        viewer.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="olympic_warriors", codename="view_edition"
            )
        )
        self.client.force_login(viewer)

        with mock.patch("olympic_warriors.admin.refresh", return_value=a_report()) as patched:
            page = self.client.get(self.EDITIONS)
            self.client.post(
                self.EDITIONS,
                {"action": "refresh_badges", "_selected_action": [self.e2024.id], "index": 0},
            )

        self.assertEqual(page.status_code, 200)
        form = page.context["action_form"]
        choices = [] if form is None else [name for name, _ in form.fields["action"].choices]
        self.assertNotIn("refresh_badges", choices)
        patched.assert_not_called()

    def test_the_changelist_shows_the_last_refresh(self):
        BadgeRefresh.objects.update_or_create(pk=1, defaults={"refreshed_at": None})
        never = self.client.get(self.BADGES)
        BadgeRefresh.objects.filter(pk=1).update(refreshed_at=REFRESHED_AT)

        refreshed = self.client.get(self.BADGES)

        self.assertContains(never, "Dernier calcul des badges : jamais")
        self.assertContains(
            refreshed, "Dernier calcul des badges : 01/07/2031 à 00:05 (heure de Paris)"
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

    def test_a_computed_row_cannot_be_deleted(self):
        # The next refresh would bring it back: a computed row is revoked, never deleted.
        badge = Badge.objects.create(user=self.ana, code=Badge.Codes.CHAMPION, edition=self.e2024)
        delete = f"{self.BADGES}{badge.id}/delete/"

        page = self.client.get(f"{self.BADGES}{badge.id}/change/")
        response = self.client.post(delete, {"post": "yes"})

        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, delete)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Badge.objects.filter(pk=badge.pk).exists())

    def test_a_manual_row_can_be_deleted(self):
        badge = Badge.objects.create(
            user=self.ana, code=Badge.Codes.MVP, edition=self.e2024, is_manual=True
        )
        delete = f"{self.BADGES}{badge.id}/delete/"

        page = self.client.get(f"{self.BADGES}{badge.id}/change/")
        response = self.client.post(delete, {"post": "yes"})

        self.assertContains(page, delete)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Badge.objects.filter(pk=badge.pk).exists())

    def test_deleting_a_selection_deletes_only_its_manual_rows(self):
        manual = Badge.objects.create(
            user=self.ana, code=Badge.Codes.MVP, edition=self.e2024, is_manual=True
        )
        computed = Badge.objects.create(
            user=self.ana, code=Badge.Codes.CHAMPION, edition=self.e2024
        )
        selection = {"action": "delete_selected", "_selected_action": [manual.id, computed.id]}

        confirmation = self.client.post(self.BADGES, {**selection, "index": 0})
        response = self.client.post(self.BADGES, {**selection, "post": "yes"})

        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(list(confirmation.context["queryset"]), [manual])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(Badge.objects.all()), [computed])

    def test_deleting_an_edition_or_a_user_still_takes_their_computed_badges(self):
        # Their delete pages ask the Badge admin about every badge the cascade takes: the
        # refusal is for the Badge admin's own pages only.
        bob = self.person("Bob")
        e2025, _ = self.edition(2025, spectator=False)
        Badge.objects.create(user=self.ana, code=Badge.Codes.CHAMPION, edition=self.e2024)
        Badge.objects.create(user=bob, code=Badge.Codes.CHAMPION, edition=e2025)

        edition = self.client.post(f"{self.EDITIONS}{self.e2024.id}/delete/", {"post": "yes"})
        user = self.client.post(f"/admin/auth/user/{bob.id}/delete/", {"post": "yes"})

        self.assertEqual((edition.status_code, user.status_code), (302, 302))
        self.assertFalse(Badge.objects.exists())

    def test_delete_queryset_skips_the_computed_rows(self):
        manual = Badge.objects.create(
            user=self.ana, code=Badge.Codes.MVP, edition=self.e2024, is_manual=True
        )
        computed = Badge.objects.create(
            user=self.ana, code=Badge.Codes.CHAMPION, edition=self.e2024
        )

        badge_admin = site._registry[Badge]  # pylint: disable=protected-access

        badge_admin.delete_queryset(None, Badge.objects.filter(pk__in=[manual.pk, computed.pk]))

        self.assertEqual(list(Badge.objects.all()), [computed])

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
    """import_edition refreshes the badges after a real import, once its transaction has
    committed, never after a dry run; a failed refresh leaves the import committed."""

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

    def setUp(self):
        folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "edition.json")
        with open(self.path, "w", encoding="utf-8") as dst:
            json.dump({}, dst)
        self.out, self.err = StringIO(), StringIO()

    def run_import(self, *args, refresh_mock=None):
        """Run the command on a document holding {}, the import patched and badges.refresh
        replaced by `refresh_mock` (by default one returning a_report()), which it returns."""
        refresh_mock = refresh_mock or mock.Mock(return_value=a_report())
        with mock.patch(f"{self.COMMAND}.import_edition", return_value=self.REPORT), mock.patch(
            f"{self.COMMAND}.refresh", refresh_mock
        ):
            call_command("import_edition", self.path, *args, stdout=self.out, stderr=self.err)
        return refresh_mock

    def test_a_real_import_refreshes_the_badges_after_its_transaction(self):
        baseline = len(connection.atomic_blocks)  # the test's own transactions
        depths = []

        def record():
            depths.append(len(connection.atomic_blocks))
            return a_report()

        patched = self.run_import(refresh_mock=mock.Mock(side_effect=record))

        patched.assert_called_once_with()
        self.assertEqual(depths, [baseline])  # outside the import's transaction.atomic()
        out = self.out.getvalue()
        self.assertIn("Imported edition 2024.", out)
        self.assertTrue(
            out.endswith("Badges: 3 added, 1 removed, 2 kept. Progress rows: 4 written.\n")
        )

    def test_a_failed_refresh_keeps_the_import_and_says_so(self):
        with self.assertRaisesMessage(CommandError, "boom"):
            self.run_import(refresh_mock=mock.Mock(side_effect=RuntimeError("boom")))

        self.assertIn("Imported edition 2024.", self.out.getvalue())
        self.assertNotIn("Badges:", self.out.getvalue())
        self.assertEqual(
            self.err.getvalue(),
            "Import committed; badges not refreshed: run manage.py refresh_badges.\n",
        )

    def test_a_dry_run_does_not(self):
        patched = self.run_import("--dry-run")

        patched.assert_not_called()
        out = self.out.getvalue()
        self.assertIn("Dry run: rolled back, nothing persisted.", out)
        self.assertNotIn("Badges:", out)
