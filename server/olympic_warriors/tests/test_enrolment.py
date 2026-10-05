"""Validating, saving, withdrawing and presenting a registration."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors import enrolment
from olympic_warriors.enrolment import (
    RegistrationError, WithdrawalRefused, removed_by_organiser, usable_email, validate,
)
from olympic_warriors.models import (
    Edition, Player, PlayerRating, PlayerSport, Relay, RegistrationSkill, Team,
)
from olympic_warriors.registration_state import RegistrationState


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19),
        registration_opens=date(year, 1, 1),
    )


def add_skill(edition, identifier, weight, order=0, **kw):
    return RegistrationSkill.objects.create(
        edition=edition, name_fr=f"{identifier} fr", name_en=f"{identifier} en",
        identifier=identifier, weight=weight, order=order, **kw
    )


def good(**changes):
    data = {
        "ratings": {"AAA": 6, "BBB": 6},
        "global_level": 8,
        "sport_frequency": "two_hours",
        "sports": [{"sport": "Judo", "level": "informal", "practice": "no_longer",
                    "duration_months": 30, "notes": "Ceinture orange"}],
        "team_with": "Avec Bob",
        "team_avoid": "Pas Carl",
        "dietary_restrictions": "Végane",
        "attendance_confirmed": True,
    }
    data.update(changes)
    return data


class Setup(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.aaa = add_skill(self.edition, "AAA", 1, 0)
        self.bbb = add_skill(self.edition, "BBB", 1, 1)
        self.skills = [self.aaa, self.bbb]
        self.ana = User.objects.create(username="ana", email="ana@example.com")

    def codes(self, data, email_editable=False, user=None):
        with self.assertRaises(RegistrationError) as ctx:
            validate(data, self.skills, email_editable, user)
        return ctx.exception.codes


class TestUsableEmail(TestCase):
    def test_blank_and_placeholder_addresses_are_not_usable(self):
        self.assertFalse(usable_email(""))
        self.assertFalse(usable_email(None))
        self.assertFalse(usable_email("anamartin@olympicwarriors.com"))
        self.assertFalse(usable_email(" AnaMartin@OlympicWarriors.com "))
        # Subdomains too, as the claim mailing treats them (one shared definition).
        self.assertFalse(usable_email("ana@mail.olympicwarriors.com"))
        self.assertTrue(usable_email("ana@notolympicwarriors.com"))
        self.assertTrue(usable_email("ana@example.com.olympicwarriors.org"))
        self.assertTrue(usable_email("ana@example.com"))


class TestValidate(Setup):
    def test_a_good_answer_is_cleaned(self):
        cleaned = validate(good(team_with="  Avec Bob \n", team_avoid=" Pas Carl "), self.skills, False)

        self.assertEqual(cleaned["ratings"], {"AAA": 6, "BBB": 6})
        self.assertEqual(cleaned["global_level"], 8)
        self.assertEqual(cleaned["team_with"], "Avec Bob")
        self.assertEqual(cleaned["team_avoid"], "Pas Carl")
        self.assertEqual(cleaned["sports"][0]["sport"], "Judo")
        self.assertIsNone(cleaned["email"])

    def test_optional_parts_may_be_absent(self):
        data = good()
        for key in ("sports", "team_with", "team_avoid", "dietary_restrictions"):
            del data[key]

        cleaned = validate(data, self.skills, False)

        self.assertEqual(cleaned["sports"], [])
        self.assertEqual(
            (cleaned["team_with"], cleaned["team_avoid"], cleaned["dietary_restrictions"]), ("", "", "")
        )

    def test_a_missing_or_invalid_rating(self):
        self.assertEqual(self.codes(good(ratings={"AAA": 6})), ["missing_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": 6, "BBB": 11})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": 6, "BBB": True})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": "6", "BBB": 6})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings="six")), ["missing_rating"])

    def test_the_global_level(self):
        for bad in (0, 11, "8", None, 7.5, True):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(good(global_level=bad)), ["invalid_global_level"])

    def test_the_frequency(self):
        self.assertEqual(self.codes(good(sport_frequency="")), ["missing_frequency"])
        self.assertEqual(self.codes(good(sport_frequency=None)), ["missing_frequency"])
        self.assertEqual(self.codes(good(sport_frequency="always")), ["invalid_frequency"])

    def test_sports(self):
        rows = [{"sport": "x"}] * 16
        self.assertEqual(self.codes(good(sports=rows)), ["too_many_sports"])
        self.assertEqual(self.codes(good(sports="judo")), ["invalid_sport"])
        for bad in (
            {"sport": ""}, {"sport": "x" * 81}, {"sport": "Judo", "level": "god"},
            {"sport": "Judo", "practice": "always"}, {"sport": "Judo", "duration_months": -1},
            {"sport": "Judo", "duration_months": "3"}, "Judo",
        ):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(good(sports=[bad])), ["invalid_sport"])
        self.assertEqual(
            self.codes(good(sports=[{"sport": "Judo", "notes": "x" * 201}])), ["too_long"]
        )

    def test_texts(self):
        for key in ("team_with", "team_avoid"):
            with self.subTest(key=key):
                self.assertEqual(self.codes(good(**{key: "x" * 501})), ["too_long"])
                self.assertEqual(self.codes(good(**{key: 5})), ["invalid_text"])
                validate(good(**{key: "x" * 500}), self.skills, False)
        self.assertEqual(self.codes(good(dietary_restrictions="x" * 501)), ["too_long"])
        validate(good(dietary_restrictions="x" * 500), self.skills, False)

    def test_a_body_that_still_sends_the_legacy_wishes_has_them_ignored(self):
        cleaned = validate(good(team_wishes="Avec Bob"), self.skills, False)

        self.assertNotIn("team_wishes", cleaned)

    def test_a_nul_byte_is_refused_not_a_server_error(self):
        # Postgres refuses a NUL in a text column: it must be a 400, never a 500.
        for key in ("team_with", "team_avoid", "dietary_restrictions"):
            self.assertEqual(self.codes(good(**{key: "a\x00b"})), ["invalid_text"])
        self.assertEqual(self.codes(good(dietary_restrictions="\x00")), ["invalid_text"])
        self.assertEqual(self.codes(good(sports=[{"sport": "Ju\x00do"}])), ["invalid_sport"])
        self.assertEqual(
            self.codes(good(sports=[{"sport": "Judo", "notes": "x\x00"}])), ["invalid_sport"]
        )

    def test_a_non_string_level_or_practice_is_refused(self):
        for bad in (0, False, [], {}, 5):
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.codes(good(sports=[{"sport": "Judo", "level": bad}])), ["invalid_sport"]
                )
                self.assertEqual(
                    self.codes(good(sports=[{"sport": "Judo", "practice": bad}])),
                    ["invalid_sport"],
                )

    def test_the_presence_tick_is_required(self):
        self.assertEqual(self.codes(good(attendance_confirmed=False)), ["attendance_required"])
        self.assertEqual(self.codes(good(attendance_confirmed="true")), ["attendance_required"])

    def test_every_problem_is_reported_once_in_order(self):
        codes = self.codes(
            good(ratings={}, global_level=0, sport_frequency="", attendance_confirmed=False)
        )

        self.assertEqual(
            codes,
            ["missing_rating", "invalid_global_level", "missing_frequency", "attendance_required"],
        )

    def test_the_email_is_only_read_when_the_account_has_no_usable_one(self):
        self.assertIsNone(validate(good(email="other@example.com"), self.skills, False)["email"])
        self.assertEqual(
            validate(good(email=" New@Example.com "), self.skills, True)["email"], "new@example.com"
        )
        self.assertEqual(self.codes(good(), email_editable=True), ["no_email"])
        self.assertEqual(self.codes(good(email="  "), email_editable=True), ["no_email"])
        self.assertEqual(
            self.codes(good(email="anamartin@olympicwarriors.com"), email_editable=True),
            ["no_email"],
        )
        self.assertEqual(self.codes(good(email="not an email"), email_editable=True), ["invalid_email"])

    def test_an_address_of_another_active_account_is_refused(self):
        other = User.objects.create(username="bob", email="Bob@Example.com")
        newbie = User.objects.create(username="newbie", email="")

        self.assertEqual(
            self.codes(good(email="bob@example.com"), email_editable=True, user=newbie),
            ["email_taken"],
        )
        # An inactive account's address is free; so is one's own.
        User.objects.filter(pk=other.pk).update(is_active=False)
        self.assertEqual(
            validate(good(email="bob@example.com"), self.skills, True, newbie)["email"],
            "bob@example.com",
        )
        self.assertEqual(
            validate(good(email="ana@example.com"), self.skills, True, self.ana)["email"],
            "ana@example.com",
        )


class TestSave(Setup):
    def save(self, **changes):
        return enrolment.save(self.ana, self.edition, self.skills, validate(good(**changes), self.skills, False))

    def test_a_save_never_touches_the_legacy_wishes(self):
        Player.objects.create(user=self.ana, edition=self.edition, rating=5, team_wishes="Ancien texte")

        player = self.save()

        player.refresh_from_db()
        self.assertEqual(player.team_wishes, "Ancien texte")

    def test_creates_the_player_ratings_and_sports(self):
        player = self.save()

        self.assertEqual((player.user, player.edition, player.is_active), (self.ana, self.edition, True))
        self.assertEqual(player.rating, 8)  # skills 6 and 6, global 8: (6 + 32) / 5 = 7.6
        self.assertEqual(player.global_level, 8)
        self.assertEqual(player.sport_frequency, "two_hours")
        self.assertEqual(player.team_with, "Avec Bob")
        self.assertEqual(player.team_avoid, "Pas Carl")
        self.assertEqual(player.dietary_restrictions, "Végane")
        self.assertTrue(player.attendance_confirmed)
        self.assertIsNone(player.team)
        self.assertEqual(
            sorted(player.playerrating_set.values_list("identifier", "name", "rating")),
            [("AAA", "AAA en", 6.0), ("BBB", "BBB en", 6.0)],
        )
        sport = player.playersport_set.get()
        self.assertEqual((sport.sport, sport.level, sport.practice, sport.duration_months), ("Judo", "informal", "no_longer", 30))

    def test_a_second_save_updates_in_place_keeps_the_team_and_replaces_the_sports(self):
        first = self.save()
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(pk=first.pk).update(team=team)

        second = self.save(
            ratings={"AAA": 10, "BBB": 2}, global_level=5,
            sports=[{"sport": "Tennis"}, {"sport": "Golf"}],
        )

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(Player.objects.filter(user=self.ana).count(), 1)
        self.assertEqual(second.team, team)
        self.assertEqual(second.rating, 5)  # weighted 6, blend (6 + 20) / 5 = 5.2
        self.assertEqual(PlayerRating.objects.filter(player=second).count(), 2)
        self.assertEqual(
            list(second.playersport_set.values_list("sport", "order")), [("Tennis", 0), ("Golf", 1)]
        )

    def test_a_withdrawn_player_is_reactivated_not_duplicated(self):
        first = self.save()
        enrolment.withdraw(self.ana, self.edition)

        again = self.save()

        self.assertEqual(again.pk, first.pk)
        self.assertTrue(again.is_active)

    def test_it_saves_the_email_when_one_is_given(self):
        user = User.objects.create(username="newbie", email="newbie@olympicwarriors.com")
        cleaned = validate(good(email="real@example.com"), self.skills, True)

        enrolment.save(user, self.edition, self.skills, cleaned)

        user.refresh_from_db()
        self.assertEqual(user.email, "real@example.com")

    def test_inactive_skills_are_not_required_nor_rated(self):
        add_skill(self.edition, "OLD", 5, 2, is_active=False)

        player = self.save()

        self.assertFalse(player.playerrating_set.filter(identifier="OLD").exists())


class TestWithdraw(Setup):
    def test_soft_deletes_marks_the_withdrawal_and_keeps_the_answers(self):
        player = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 1)

        player.refresh_from_db()
        self.assertFalse(player.is_active)
        self.assertIsNotNone(player.withdrawn_at)
        self.assertEqual(player.team_with, "Avec Bob")
        self.assertEqual(player.team_avoid, "Pas Carl")
        self.assertEqual(player.playersport_set.count(), 1)

    def test_withdrawing_twice_or_never_registered_is_fine(self):
        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 0)

    def test_a_player_in_a_team_cannot_withdraw(self):
        player = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        Player.objects.filter(pk=player.pk).update(team=Team.objects.create(name="Red", edition=self.edition))

        with self.assertRaises(WithdrawalRefused):
            enrolment.withdraw(self.ana, self.edition)

        player.refresh_from_db()
        self.assertTrue(player.is_active)

    def test_a_team_that_is_no_longer_active_does_not_hold_the_player(self):
        player = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        team = Team.objects.create(name="Red", edition=self.edition, is_active=False)
        Player.objects.filter(pk=player.pk).update(team=team)

        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 1)

        player.refresh_from_db()
        self.assertFalse(player.is_active)

    def test_every_active_row_of_the_person_is_withdrawn(self):
        first = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        second = Player.objects.create(user=self.ana, edition=self.edition, rating=5)  # an import's twin

        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 2)

        for player in (first, second):
            player.refresh_from_db()
            self.assertFalse(player.is_active)
            self.assertIsNotNone(player.withdrawn_at)

    def test_a_placed_twin_blocks_the_withdrawal_of_both(self):
        first = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.create(user=self.ana, edition=self.edition, rating=5, team=team)

        with self.assertRaises(WithdrawalRefused):
            enrolment.withdraw(self.ana, self.edition)

        first.refresh_from_db()
        self.assertTrue(first.is_active)

    def test_saving_again_clears_the_withdrawal_mark(self):
        player = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        enrolment.withdraw(self.ana, self.edition)

        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        player.refresh_from_db()
        self.assertTrue(player.is_active)
        self.assertIsNone(player.withdrawn_at)


class TestRemovedByOrganiser(Setup):
    def test_an_inactive_row_nobody_withdrew_was_removed_by_an_organiser(self):
        player = Player.objects.create(user=self.ana, edition=self.edition, rating=5)
        self.assertFalse(removed_by_organiser(self.ana, self.edition))  # active

        Player.objects.filter(pk=player.pk).update(is_active=False)
        self.assertTrue(removed_by_organiser(self.ana, self.edition))

    def test_a_self_withdrawal_is_not_a_removal(self):
        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))
        enrolment.withdraw(self.ana, self.edition)

        self.assertFalse(removed_by_organiser(self.ana, self.edition))

    def test_nobody_registered_is_not_a_removal(self):
        self.assertFalse(removed_by_organiser(self.ana, self.edition))


class TestPayload(Setup):
    def payload(self, user=None, edition=None, state=None):
        return enrolment.form_payload(
            user or self.ana, edition or self.edition, state or RegistrationState(True)
        )

    def test_the_form(self):
        Relay.objects.create(edition=self.edition)
        self.edition.registration_intro_fr = "Bienvenue"
        self.edition.skills_month_fr = "août"
        self.edition.save()

        body = self.payload()

        self.assertEqual(body["edition"]["year"], 2027)
        self.assertEqual(body["edition"]["opens"], "2027-01-01")
        self.assertEqual(body["edition"]["closes"], "2027-09-17")  # the day before the start
        self.assertTrue(body["edition"]["dates_confirmed"])
        self.assertEqual(body["state"], {"is_open": True, "reason": ""})
        self.assertEqual(body["intro"], {"fr": "Bienvenue", "en": ""})
        self.assertEqual(body["skills_month"], {"fr": "août", "en": ""})
        self.assertEqual(
            body["skills"],
            [
                {"identifier": "AAA", "name_fr": "AAA fr", "name_en": "AAA en"},
                {"identifier": "BBB", "name_fr": "BBB fr", "name_en": "BBB en"},
            ],
        )
        self.assertEqual([c["value"] for c in body["choices"]["frequency"]],
                         ["rare", "monthly", "hour", "two_hours", "four_hours"])
        self.assertEqual([c["value"] for c in body["choices"]["level"]],
                         ["fun", "informal", "club", "league", "regional"])
        self.assertEqual([c["value"] for c in body["choices"]["practice"]],
                         ["no_longer", "occasionally", "regularly"])
        self.assertEqual(body["disciplines"], ["Relay"])
        self.assertIsNone(body["registration"])
        self.assertIsNone(body["suggested"])

    def test_the_email_is_read_only_only_when_usable(self):
        self.assertEqual(self.payload()["email"], {"value": "ana@example.com", "editable": False})
        self.ana.email = "ana@olympicwarriors.com"

        self.assertEqual(self.payload()["email"], {"value": "", "editable": True})

    def test_the_saved_answers_of_a_registered_and_of_a_withdrawn_player(self):
        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        registered = self.payload()["registration"]
        enrolment.withdraw(self.ana, self.edition)
        withdrawn = self.payload()["registration"]

        self.assertTrue(registered["registered"])
        self.assertFalse(withdrawn["registered"])
        self.assertFalse(registered["removed_by_organiser"])
        self.assertFalse(withdrawn["removed_by_organiser"])
        for answers in (registered, withdrawn):
            self.assertEqual(answers["ratings"], {"AAA": 6, "BBB": 6})
            self.assertEqual(answers["global_level"], 8)
            self.assertEqual(answers["sport_frequency"], "two_hours")
            self.assertEqual(answers["team_with"], "Avec Bob")
            self.assertEqual(answers["team_avoid"], "Pas Carl")
            self.assertNotIn("team_wishes", answers)
            self.assertEqual(answers["dietary_restrictions"], "Végane")
            self.assertTrue(answers["attendance_confirmed"])
            self.assertEqual(
                answers["sports"],
                [{"sport": "Judo", "level": "informal", "practice": "no_longer",
                  "duration_months": 30, "notes": "Ceinture orange"}],
            )

    def test_suggestions_come_from_the_latest_previous_registration_only(self):
        old = make_edition(2026)
        older = make_edition(2025)
        Player.objects.create(
            user=self.ana, edition=older, rating=5, dietary_restrictions="Vieux",
            sport_frequency="rare", team_with="x", global_level=3,
        )
        previous = Player.objects.create(
            user=self.ana, edition=old, rating=5, dietary_restrictions="Sans gluten",
            sport_frequency="hour", team_with="Avec Bob", team_avoid="Pas Carl", global_level=7, attendance_confirmed=True,
        )
        PlayerSport.objects.create(player=previous, sport="Tennis", notes="30/1")

        suggested = self.payload()["suggested"]

        self.assertNotIn("team_with", suggested)
        self.assertNotIn("team_avoid", suggested)
        self.assertEqual(
            suggested,
            {
                "year": 2026,
                "sport_frequency": "hour",
                "dietary_restrictions": "Sans gluten",
                "sports": [{"sport": "Tennis", "level": "", "practice": "",
                            "duration_months": None, "notes": "30/1"}],
            },
        )

    def test_no_suggestion_once_registered_in_this_edition(self):
        Player.objects.create(user=self.ana, edition=make_edition(2026), rating=5, sport_frequency="hour")
        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        self.assertIsNone(self.payload()["suggested"])
