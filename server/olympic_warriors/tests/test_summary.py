"""
Tests for the Edition model changes and the public edition summary endpoint.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition


class TestEditionModel(TestCase):
    """year is unique and photos_url is optional."""

    def test_year_is_unique(self):
        Edition.objects.create(year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20")
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
