"""
Tests for badges.refresh() and the refresh_badges command: the refresh stores the difference
between earned() and the stored computed rows, and never touches the manual ones.
"""

from collections import Counter
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from olympic_warriors.badges import earned, refresh
from olympic_warriors.models import Badge, BadgeRefresh, Team
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
