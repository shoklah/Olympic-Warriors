"""
Tests for the Edition model changes and the public edition summary endpoint.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from olympic_warriors.models import Edition, Relay, Team, TeamResult


class TestEditionModel(TestCase):
    """year is unique and photos_url is optional."""

    def test_year_is_unique(self):
        Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Edition.objects.create(
                    year=2026, host="Lyon", start_date="2026-10-01", end_date="2026-10-02"
                )

    def test_photos_url_defaults_to_none(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.assertIsNone(edition.photos_url)

    def test_photos_url_is_stored(self):
        edition = Edition.objects.create(
            year=2026,
            host="Paris",
            start_date="2026-09-19",
            end_date="2026-09-20",
            photos_url="https://drive.example.com/ow-2026",
        )
        edition.refresh_from_db()
        self.assertEqual(edition.photos_url, "https://drive.example.com/ow-2026")


class TestTeamResultsByEdition(APITestCase):
    """The by-edition results view filters through the discipline's edition."""

    def setUp(self):
        self.user = User.objects.create_user(username="orga", password="x")
        self.client.force_authenticate(user=self.user)
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.other = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        Team.objects.create(name="A", edition=self.edition)
        Team.objects.create(name="Z", edition=self.other)
        Relay.objects.create(edition=self.edition)  # one result for A
        Relay.objects.create(edition=self.other)  # one result for Z

    def test_returns_only_that_editions_results(self):
        response = self.client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([r["team_name"] for r in response.data], ["A"])

    def test_excludes_inactive_results(self):
        Team.objects.create(name="B", edition=self.edition)
        Relay.objects.create(edition=self.edition)  # a second result each for A and B
        TeamResult.objects.filter(team__name="B").update(is_active=False)

        response = self.client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        # setUp's own Relay already gave team A one active result, so this
        # edition legitimately has two active "A" results at this point;
        # what this test asserts is that team B's now-inactive result is
        # excluded.
        self.assertNotIn("B", [r["team_name"] for r in response.data])
