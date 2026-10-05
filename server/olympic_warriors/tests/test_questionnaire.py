"""Copying a questionnaire, locking its skill set, recomputing ratings after a weight change."""
from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, Player, PlayerRating, RegistrationSkill
from olympic_warriors.questionnaire import (
    QuestionnaireError,
    copy_skills,
    recompute_ratings,
    skills_locked,
)


def make_edition(year):
    return Edition.objects.create(
        year=year, host="Paris", start_date=f"{year}-09-18", end_date=f"{year}-09-19"
    )


def add_skill(edition, identifier, weight, order=0, is_active=True):
    return RegistrationSkill.objects.create(
        edition=edition,
        name_fr=identifier,
        name_en=identifier,
        identifier=identifier,
        weight=weight,
        order=order,
        is_active=is_active,
    )


def add_player(edition, username, rating, global_level, **ratings):
    player = Player.objects.create(
        user=User.objects.create(username=username),
        edition=edition,
        rating=rating,
        global_level=global_level,
    )
    for identifier, value in ratings.items():
        PlayerRating.objects.create(
            player=player, name=identifier, identifier=identifier, rating=value
        )
    return player


class TestSkillsLocked(TestCase):
    def test_locked_once_a_player_has_a_rating(self):
        edition = make_edition(2027)
        self.assertFalse(skills_locked(edition))

        add_player(edition, "ana", 5, 5)
        self.assertFalse(skills_locked(edition))  # a player without ratings does not lock

        add_player(edition, "bob", 5, 5, AAA=6)
        self.assertTrue(skills_locked(edition))

    def test_another_editions_ratings_do_not_lock(self):
        add_player(make_edition(2026), "ana", 5, 5, AAA=6)

        self.assertFalse(skills_locked(make_edition(2027)))


class TestCopySkills(TestCase):
    def test_copies_the_active_skills_of_the_closest_earlier_questionnaire(self):
        make_edition(2024)  # no questionnaire: skipped
        older, previous, new = make_edition(2025), make_edition(2026), make_edition(2027)
        add_skill(older, "OLD", 9)
        add_skill(previous, "AAA", 2, order=0)
        add_skill(previous, "BBB", 3, order=1)
        add_skill(previous, "OFF", 1, order=2, is_active=False)

        year, count = copy_skills(new)

        self.assertEqual((year, count), (2026, 2))
        self.assertEqual(
            list(new.registrationskill_set.values_list("identifier", "weight", "order")),
            [("AAA", 2, 0), ("BBB", 3, 1)],
        )
        self.assertEqual(previous.registrationskill_set.count(), 3)  # untouched

    def test_refuses_an_edition_that_already_has_a_questionnaire(self):
        previous, new = make_edition(2026), make_edition(2027)
        add_skill(previous, "AAA", 2)
        add_skill(new, "ZZZ", 1)

        with self.assertRaises(QuestionnaireError):
            copy_skills(new)
        self.assertEqual(new.registrationskill_set.count(), 1)

    def test_refuses_when_no_earlier_edition_has_a_questionnaire(self):
        with self.assertRaises(QuestionnaireError):
            copy_skills(make_edition(2027))


class TestRecomputeRatings(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        add_skill(self.edition, "AAA", 1)
        add_skill(self.edition, "BBB", 1)

    def test_a_weight_change_moves_the_stored_rating(self):
        # Equal weights: weighted 6, blend (6 + 5 * 4) / 5 = 5.2, stored 5.
        player = add_player(self.edition, "ana", 5, 5, AAA=10, BBB=2)
        RegistrationSkill.objects.filter(identifier="AAA").update(weight=3)

        report = recompute_ratings(self.edition)

        # Weights 3 and 1: weighted 8, blend (8 + 20) / 5 = 5.6, stored 6.
        player.refresh_from_db()
        self.assertEqual(player.rating, 6)
        self.assertEqual((report.updated, report.unchanged), (1, 0))
        self.assertTrue(report.has_questionnaire)

    def test_a_second_run_changes_nothing(self):
        add_player(self.edition, "ana", 5, 5, AAA=10, BBB=2)
        RegistrationSkill.objects.filter(identifier="AAA").update(weight=3)
        recompute_ratings(self.edition)

        report = recompute_ratings(self.edition)

        self.assertEqual((report.updated, report.unchanged), (0, 1))

    def test_players_without_a_global_level_are_skipped_and_counted(self):
        player = add_player(self.edition, "old", 7, None, AAA=10, BBB=2)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual(report.no_global_level, 1)
        self.assertEqual(report.updated, 0)

    def test_players_missing_a_skill_are_skipped_and_counted(self):
        player = add_player(self.edition, "ana", 7, 5, AAA=10)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual(report.incomplete, 1)

    def test_inactive_players_are_left_alone(self):
        player = add_player(self.edition, "ana", 7, 5, AAA=10, BBB=2)
        Player.objects.filter(pk=player.pk).update(is_active=False)

        report = recompute_ratings(self.edition)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertEqual((report.updated, report.unchanged), (0, 0))

    def test_an_edition_without_a_questionnaire_changes_nothing(self):
        bare = make_edition(2028)
        player = add_player(bare, "ana", 7, 5, AAA=10, BBB=2)

        report = recompute_ratings(bare)

        player.refresh_from_db()
        self.assertEqual(player.rating, 7)
        self.assertFalse(report.has_questionnaire)
