"""
Tests for the Badge model: the catalogue, the constraint on computed rows, and the one
BadgeRefresh row the migration creates.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import MANUAL_CODES, Badge, BadgeRefresh, Edition


class TestCatalogue(TestCase):
    def test_codes_are_the_spec_catalogue_in_order(self):
        codes = Badge.Codes.values
        self.assertEqual(len(codes), 63)
        self.assertEqual(len(set(codes)), 63)
        self.assertEqual(codes[:5], ["champion", "runner-up", "bronze", "chocolate", "wooden-spoon"])
        self.assertEqual(codes[-6:], ["mvp", "fair-play", "hype", "costume", "wounded", "torchbearer"])

    def test_six_codes_are_given_by_hand(self):
        self.assertEqual(
            sorted(MANUAL_CODES),
            sorted(["mvp", "fair-play", "hype", "costume", "wounded", "torchbearer"]),
        )


class TestBadgeRows(TestCase):
    def setUp(self):
        self.edition = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.user = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")

    def badge(self, **kwargs):
        return Badge.objects.create(user=self.user, edition=self.edition, **kwargs)

    def test_defaults(self):
        badge = self.badge(code=Badge.Codes.CHAMPION)
        self.assertEqual(
            (badge.tier, badge.discipline, badge.partner, badge.is_manual, badge.note, badge.is_active),
            (0, "", None, False, "", True),
        )
        self.assertIsNotNone(badge.created_at)

    def test_a_computed_row_is_unique_on_its_key(self):
        other = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        self.badge(code=Badge.Codes.COMRADES, partner=other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.badge(code=Badge.Codes.COMRADES, partner=other)

    def test_the_same_key_twice_is_fine_by_hand(self):
        self.badge(code=Badge.Codes.MVP, is_manual=True)
        self.badge(code=Badge.Codes.MVP, is_manual=True)
        self.assertEqual(Badge.objects.filter(code="mvp").count(), 2)

    def test_str_names_the_badge_person_and_year(self):
        badge = self.badge(code=Badge.Codes.RUNNER_UP)
        self.assertEqual(str(badge), "Dauphin - ana (2024)")


class TestBadgeRefresh(TestCase):
    def test_the_migration_created_the_one_row(self):
        self.assertTrue(BadgeRefresh.objects.filter(pk=1).exists())
        self.assertIsNone(BadgeRefresh.objects.get(pk=1).refreshed_at)
