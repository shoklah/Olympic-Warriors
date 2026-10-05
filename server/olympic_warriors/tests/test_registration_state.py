"""Whether registration is open: the window, the questionnaire and the late pass."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, LateRegistration, RegistrationSkill
from olympic_warriors.registration_state import (
    CLOSED,
    LATE_PASS,
    NOT_CONFIGURED,
    NOT_YET_OPEN,
    closing_date,
    registration_state,
)

OPENS = date(2027, 5, 1)
START = date(2027, 9, 18)
END = date(2027, 9, 19)


def make_edition(opens=OPENS, closes=None, skills=True):
    edition = Edition.objects.create(
        year=2027, host="Paris", start_date=START, end_date=END,
        registration_opens=opens, registration_closes=closes,
    )
    if skills:
        RegistrationSkill.objects.create(
            edition=edition, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )
    return edition


class TestRegistrationState(TestCase):
    def state(self, edition, today, user=None):
        return registration_state(edition, user, today=today)

    def test_open_from_the_opening_day_inclusive(self):
        edition = make_edition()

        self.assertEqual(self.state(edition, date(2027, 4, 30)).reason, NOT_YET_OPEN)
        self.assertFalse(self.state(edition, date(2027, 4, 30)).is_open)
        self.assertTrue(self.state(edition, OPENS).is_open)
        self.assertEqual(self.state(edition, OPENS).reason, "")

    def test_closes_the_day_before_the_start_by_default(self):
        edition = make_edition()

        self.assertEqual(closing_date(edition), date(2027, 9, 17))
        self.assertTrue(self.state(edition, date(2027, 9, 17)).is_open)
        closed = self.state(edition, date(2027, 9, 18))
        self.assertFalse(closed.is_open)
        self.assertEqual(closed.reason, CLOSED)

    def test_an_explicit_closing_day_is_inclusive(self):
        edition = make_edition(closes=date(2027, 6, 30))

        self.assertTrue(self.state(edition, date(2027, 6, 30)).is_open)
        self.assertEqual(self.state(edition, date(2027, 7, 1)).reason, CLOSED)

    def test_a_fresh_edition_is_closed_until_someone_opens_it(self):
        edition = make_edition(opens=None)

        state = self.state(edition, date(2027, 6, 1))

        self.assertFalse(state.is_open)
        self.assertEqual(state.reason, NOT_CONFIGURED)

    def test_without_a_questionnaire_it_is_never_open(self):
        edition = make_edition(skills=False)

        self.assertEqual(self.state(edition, date(2027, 6, 1)).reason, NOT_CONFIGURED)

    def test_inactive_skills_do_not_count_as_a_questionnaire(self):
        edition = make_edition()
        RegistrationSkill.objects.update(is_active=False)

        self.assertEqual(self.state(edition, date(2027, 6, 1)).reason, NOT_CONFIGURED)


class TestLatePass(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")
        self.bob = User.objects.create(username="bob")
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

    def test_a_pass_opens_a_closed_registration_for_its_user_only(self):
        during = date(2027, 9, 18)

        ana = registration_state(self.edition, self.ana, today=during)
        bob = registration_state(self.edition, self.bob, today=during)
        anonymous = registration_state(self.edition, None, today=during)

        self.assertEqual((ana.is_open, ana.reason), (True, LATE_PASS))
        self.assertEqual((bob.is_open, bob.reason), (False, CLOSED))
        self.assertEqual((anonymous.is_open, anonymous.reason), (False, CLOSED))

    def test_a_pass_works_before_the_opening_too(self):
        state = registration_state(self.edition, self.ana, today=date(2027, 1, 1))

        self.assertEqual((state.is_open, state.reason), (True, LATE_PASS))

    def test_a_pass_lasts_through_the_end_date_then_expires(self):
        last_day = registration_state(self.edition, self.ana, today=END)
        after = registration_state(self.edition, self.ana, today=date(2027, 9, 20))

        self.assertEqual(last_day.reason, LATE_PASS)
        self.assertEqual((after.is_open, after.reason), (False, CLOSED))

    def test_a_pass_does_not_bypass_a_missing_questionnaire(self):
        RegistrationSkill.objects.all().delete()

        state = registration_state(self.edition, self.ana, today=date(2027, 9, 18))

        self.assertEqual((state.is_open, state.reason), (False, NOT_CONFIGURED))

    def test_a_pass_holder_reports_the_pass_even_inside_the_window(self):
        state = registration_state(self.edition, self.ana, today=date(2027, 6, 1))

        self.assertEqual((state.is_open, state.reason), (True, LATE_PASS))
