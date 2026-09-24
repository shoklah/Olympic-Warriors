"""
Blindtest points: each correct artist or song of a guess adds 1 to the team's result in
that blindtest, and flipping it back takes the point away.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from olympic_warriors.models import Blindtest, BlindtestGuess, Edition, Team, TeamResult


class BlindtestSetup(TestCase):
    """Two teams, one blindtest (10 rounds of one guess per team), nothing correct yet."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.red = Team.objects.create(name="Red", edition=self.edition)
        self.blue = Team.objects.create(name="Blue", edition=self.edition)
        self.blindtest = Blindtest.objects.create(edition=self.edition)
        self.round = self.blindtest.blindtest.get(order=1)

    def guess(self, team, blindtest_round=None):
        return BlindtestGuess.objects.get(team=team, blindtest_round=blindtest_round or self.round)

    def points(self, team, blindtest=None):
        return TeamResult.objects.get(team=team, discipline=blindtest or self.blindtest).points

    def flip(self, guess, **flags):
        for flag, value in flags.items():
            setattr(guess, flag, value)
        guess.save()


class TestBlindtestPoints(BlindtestSetup):

    def test_results_start_empty(self):
        self.assertEqual((self.points(self.red), self.points(self.blue)), (None, None))

    def test_correct_artist_adds_one(self):
        self.flip(self.guess(self.red), is_artist_correct=True)
        self.assertEqual(self.points(self.red), 1)

    def test_correct_song_adds_one(self):
        self.flip(self.guess(self.red), is_song_correct=True)
        self.assertEqual(self.points(self.red), 1)

    def test_artist_and_song_add_one_each(self):
        self.flip(self.guess(self.red), is_artist_correct=True, is_song_correct=True)
        self.assertEqual(self.points(self.red), 2)

    def test_points_accumulate_over_rounds(self):
        self.flip(self.guess(self.red), is_artist_correct=True)
        second_round = self.blindtest.blindtest.get(order=2)
        self.flip(self.guess(self.red, second_round), is_artist_correct=True, is_song_correct=True)
        self.assertEqual(self.points(self.red), 3)

    def test_unflipping_artist_takes_the_point_back(self):
        guess = self.guess(self.red)
        self.flip(guess, is_artist_correct=True, is_song_correct=True)
        self.flip(guess, is_artist_correct=False)
        self.assertEqual(self.points(self.red), 1)

    def test_unflipping_song_takes_the_point_back(self):
        guess = self.guess(self.red)
        self.flip(guess, is_artist_correct=True, is_song_correct=True)
        self.flip(guess, is_song_correct=False)
        self.assertEqual(self.points(self.red), 1)

    def test_unflipping_everything_leaves_zero(self):
        guess = self.guess(self.red)
        self.flip(guess, is_artist_correct=True)
        self.flip(guess, is_artist_correct=False)
        self.assertEqual(self.points(self.red), 0)

    def test_saving_without_a_flag_change_leaves_points_alone(self):
        guess = self.guess(self.red)
        self.flip(guess, is_artist_correct=True)
        self.flip(guess, artist="Daft Punk", song="One More Time")
        self.flip(guess, is_artist_correct=True)
        self.assertEqual(self.points(self.red), 1)

    def test_guess_created_correct_scores_on_creation(self):
        second_round = self.blindtest.blindtest.get(order=2)
        BlindtestGuess.objects.filter(blindtest_round=second_round).delete()
        BlindtestGuess.objects.create(
            team=self.red, blindtest_round=second_round, is_artist_correct=True
        )
        BlindtestGuess.objects.create(
            team=self.blue, blindtest_round=second_round,
            is_artist_correct=True, is_song_correct=True,
        )
        self.assertEqual((self.points(self.red), self.points(self.blue)), (1, 2))

    def test_guess_created_wrong_scores_nothing(self):
        BlindtestGuess.objects.create(team=self.red, blindtest_round=self.round)
        self.assertIsNone(self.points(self.red))


class TestBlindtestPointsTarget(BlindtestSetup):
    """Points land on the guess's team, in the guess's blindtest, and nowhere else."""

    def test_points_land_on_the_guess_team_in_that_blindtest_only(self):
        other_blindtest = Blindtest.objects.create(edition=self.edition)
        previous = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        previous_red = Team.objects.create(name="Red", edition=previous)
        previous_blindtest = Blindtest.objects.create(edition=previous)

        self.flip(self.guess(self.red), is_artist_correct=True, is_song_correct=True)

        self.assertEqual(self.points(self.red), 2)
        self.assertIsNone(self.points(self.blue))
        self.assertIsNone(self.points(self.red, other_blindtest))
        self.assertIsNone(self.points(self.blue, other_blindtest))
        self.assertIsNone(self.points(previous_red, previous_blindtest))

    def test_points_follow_the_round_of_another_blindtest(self):
        other_blindtest = Blindtest.objects.create(edition=self.edition)
        other_round = other_blindtest.blindtest.get(order=1)

        self.flip(self.guess(self.red, other_round), is_song_correct=True)

        self.assertIsNone(self.points(self.red))
        self.assertEqual(self.points(self.red, other_blindtest), 1)


class TestBlindtestLateTeam(BlindtestSetup):
    """A team created after the blindtest has neither guesses nor a result in it."""

    def setUp(self):
        super().setUp()
        self.green = Team.objects.create(name="Green", edition=self.edition)

    def results(self, team):
        return TeamResult.objects.filter(team=team, discipline=self.blindtest)

    def test_late_team_has_no_result(self):
        self.assertFalse(self.results(self.green).exists())

    def test_correct_guess_creates_the_result_with_its_point(self):
        BlindtestGuess.objects.create(
            team=self.green, blindtest_round=self.round, is_song_correct=True
        )
        self.assertEqual(list(self.results(self.green).values_list("points", flat=True)), [1])

    def test_flipping_a_late_guess_creates_the_result_once(self):
        guess = BlindtestGuess.objects.create(team=self.green, blindtest_round=self.round)
        self.assertFalse(self.results(self.green).exists())
        self.flip(guess, is_artist_correct=True)
        self.flip(guess, is_song_correct=True)
        self.assertEqual(list(self.results(self.green).values_list("points", flat=True)), [2])


class TestBlindtestOtherEditionTeam(BlindtestSetup):
    """A team of another edition is refused rather than given a result in this blindtest."""

    def setUp(self):
        super().setUp()
        previous = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.stranger = Team.objects.create(name="Red", edition=previous)

    def test_correct_guess_raises_and_creates_nothing(self):
        with self.assertRaises(ValidationError):
            BlindtestGuess.objects.create(
                team=self.stranger, blindtest_round=self.round, is_artist_correct=True
            )
        self.assertFalse(TeamResult.objects.filter(team=self.stranger).exists())
        self.assertFalse(BlindtestGuess.objects.filter(team=self.stranger).exists())

    def test_guess_without_points_is_refused_too(self):
        with self.assertRaises(ValidationError):
            BlindtestGuess.objects.create(team=self.stranger, blindtest_round=self.round)
        guess = self.guess(self.red)
        guess.team = self.stranger
        with self.assertRaises(ValidationError):
            guess.save()
        self.assertEqual(self.guess(self.red).team_id, self.red.pk)

    def test_full_clean_refuses_the_guess(self):
        guess = BlindtestGuess(team=self.stranger, blindtest_round=self.round)
        with self.assertRaisesMessage(
            ValidationError, "The team is not part of the edition of the blindtest"
        ):
            guess.full_clean()

    def test_full_clean_accepts_a_team_of_the_edition_without_answers(self):
        self.guess(self.red).full_clean()


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestBlindtestAdmin(BlindtestSetup):
    """Organisers flip the flags in the admin: the guess form and the round's inline."""

    def setUp(self):
        super().setUp()
        User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(User.objects.get(username="root"))

    def guess_form(self, guess, **overrides):
        # Answers left blank: a team may give no artist or no song.
        data = {
            "team": guess.team_id,
            "blindtest_round": guess.blindtest_round_id,
            "artist": "",
            "song": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_guess_change_form_scores(self):
        guess = self.guess(self.red)
        response = self.client.post(
            f"/admin/olympic_warriors/blindtestguess/{guess.pk}/change/",
            self.guess_form(guess, is_artist_correct="on", is_song_correct="on"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.points(self.red), 2)

    def test_round_inline_scores_each_team(self):
        guesses = [self.guess(self.red), self.guess(self.blue)]
        data = {
            "blindtest": self.blindtest.pk,
            "order": self.round.order,
            "is_active": "on",
            "blindtest_round-TOTAL_FORMS": len(guesses),
            "blindtest_round-INITIAL_FORMS": len(guesses),
            "blindtest_round-MIN_NUM_FORMS": 0,
            "blindtest_round-MAX_NUM_FORMS": 1000,
        }
        for index, guess in enumerate(guesses):
            prefix = f"blindtest_round-{index}-"
            data[prefix + "id"] = guess.pk
            data[prefix + "blindtest_round"] = self.round.pk
            for field, value in self.guess_form(guess).items():
                if field != "blindtest_round":
                    data[prefix + field] = value
        data["blindtest_round-0-is_song_correct"] = "on"
        data["blindtest_round-1-is_artist_correct"] = "on"
        data["blindtest_round-1-is_song_correct"] = "on"

        response = self.client.post(
            f"/admin/olympic_warriors/blindtestround/{self.round.pk}/change/", data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual((self.points(self.red), self.points(self.blue)), (1, 2))

    def add_round(self, team, blindtest=None, **flags):
        data = {
            "blindtest": blindtest.pk if blindtest else "",
            "order": 1,
            "is_active": "on",
            "blindtest_round-TOTAL_FORMS": 1,
            "blindtest_round-INITIAL_FORMS": 0,
            "blindtest_round-MIN_NUM_FORMS": 0,
            "blindtest_round-MAX_NUM_FORMS": 1000,
            "blindtest_round-0-team": team.pk,
            "blindtest_round-0-artist": "",
            "blindtest_round-0-song": "",
            "blindtest_round-0-is_active": "on",
        }
        for flag in flags:
            data[f"blindtest_round-0-{flag}"] = "on"
        return self.client.post("/admin/olympic_warriors/blindtestround/add/", data)

    def test_adding_a_round_scores_its_inline_guess(self):
        response = self.add_round(self.red, self.blindtest, is_song_correct=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.blindtest.blindtest.count(), 11)
        self.assertEqual(self.points(self.red), 1)

    def test_adding_a_round_refuses_a_team_of_another_edition(self):
        previous = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        stranger = Team.objects.create(name="Red", edition=previous)

        response = self.add_round(stranger, self.blindtest, is_song_correct=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The team is not part of the edition of the blindtest")
        self.assertEqual(self.blindtest.blindtest.count(), 10)
        self.assertFalse(TeamResult.objects.filter(team=stranger).exists())

    def test_adding_a_round_without_its_blindtest_shows_the_form_error(self):
        response = self.add_round(self.red, is_song_correct=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.blindtest.blindtest.count(), 10)
        self.assertIsNone(self.points(self.red))

    def test_guess_form_refuses_a_team_of_another_edition(self):
        previous = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        stranger = Team.objects.create(name="Red", edition=previous)
        guess = self.guess(self.red)

        response = self.client.post(
            f"/admin/olympic_warriors/blindtestguess/{guess.pk}/change/",
            self.guess_form(guess, team=stranger.pk, is_artist_correct="on"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The team is not part of the edition of the blindtest")
        self.assertEqual(self.guess(self.red).team_id, self.red.pk)
        self.assertFalse(TeamResult.objects.filter(team=stranger).exists())


class TestBlindtestGuessEndpoints(BlindtestSetup):
    """Guesses listed by blindtest, and by team and blindtest, through the round."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        # The guess views are staff-only, like the rest of the API outside the reveal-aware reads.
        self.client.force_authenticate(
            user=User.objects.create_user("orga", "orga@example.com", "pw", is_staff=True)
        )
        self.other_blindtest = Blindtest.objects.create(edition=self.edition)
        self.hidden = self.guess(self.red)
        self.hidden.is_active = False
        self.hidden.save()

    def ids(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return sorted(guess["id"] for guess in response.json())

    def expected(self, **filters):
        guesses = BlindtestGuess.objects.filter(is_active=True, **filters)
        return sorted(guesses.values_list("id", flat=True))

    def test_guesses_by_blindtest(self):
        ids = self.ids(f"/blindtest/guesses/blindtest/{self.blindtest.pk}/")
        self.assertEqual(len(ids), 19)
        self.assertEqual(ids, self.expected(blindtest_round__blindtest=self.blindtest))
        self.assertNotIn(self.hidden.pk, ids)

    def test_guesses_by_team_and_blindtest(self):
        ids = self.ids(f"/blindtest/guesses/blindtest/{self.blindtest.pk}/team/{self.blue.pk}/")
        self.assertEqual(len(ids), 10)
        self.assertEqual(
            ids, self.expected(blindtest_round__blindtest=self.blindtest, team=self.blue)
        )

    def test_unknown_blindtest_lists_nothing(self):
        self.assertEqual(self.ids("/blindtest/guesses/blindtest/0/"), [])

    def test_answer_may_leave_the_song_blank(self):
        guess = self.guess(self.blue)
        response = self.client.patch(
            f"/blindtest/guess/{guess.pk}/answer/",
            {"artist": "Daft Punk", "song": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        guess.refresh_from_db()
        self.assertEqual((guess.artist, guess.song), ("Daft Punk", ""))
