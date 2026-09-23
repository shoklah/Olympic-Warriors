"""
The API is organisers only by default (DEFAULT_PERMISSION_CLASSES is IsOrganiser): a view is
public or open to any token only when it says so, and the sweep fails on any other exception.
"""

from django.contrib.auth.models import User
from django.urls import get_resolver
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Blindtest,
    BlindtestGuess,
    Darts,
    Edition,
    Game,
    GameEvent,
    Player,
    PlayerRating,
    Team,
    TeamSportRound,
)
from olympic_warriors.permissions import IsOrganiser

PUBLIC = {
    "getEdition",
    "getEditions",
    "getEditionSummary",
    "getDiscipline",
    "getDisciplines",
    "getDisciplinesByEdition",
}
ANY_TOKEN = {"getCurrentUser"}


def wired_views():
    """Every views.py view urls.py routes to, by name: its DRF class, or None for a plain view."""
    views = {}
    for pattern in get_resolver().url_patterns:
        callback = getattr(pattern, "callback", None)
        if callback is None or callback.__module__ != "olympic_warriors.views":
            continue
        view = getattr(callback, "cls", None)
        views[view.__name__ if view else callback.__name__] = view
    return views


class TestDefaultPolicy(APITestCase):

    def test_every_view_is_organisers_only_unless_listed(self):
        views = wired_views()
        self.assertLessEqual(PUBLIC | ANY_TOKEN, set(views))
        for name, view in views.items():
            with self.subTest(view=name):
                self.assertIsNotNone(view, "not an @api_view: no DRF auth or permission runs")
                if name in PUBLIC:
                    expected = [AllowAny]
                elif name in ANY_TOKEN:
                    expected = [IsAuthenticated]
                else:
                    expected = [IsOrganiser]
                self.assertEqual(list(view.permission_classes), expected)


class ClosedSetup(APITestCase):
    """2026 (latest) and 2025, each with a Darts game, a game event and a Blindtest."""

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.old = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.user = User.objects.create_user(username="player", password="x")

        self.game, self.event, self.guess = self.edition_with_rows(self.edition, "A", "B")
        self.old_game, self.old_event, self.old_guess = self.edition_with_rows(self.old, "Y", "Z")
        self.player = Player.objects.get(edition=self.edition, team__name="A")
        self.rating = PlayerRating.objects.create(
            player=self.player, name="Cardio", identifier="CAR", rating=7
        )

    def edition_with_rows(self, edition, first, second):
        """Two teams, a player, a played Darts game with one event, a Blindtest; its rows."""
        team1 = Team.objects.create(name=first, edition=edition)
        team2 = Team.objects.create(name=second, edition=edition)
        player = Player.objects.create(user=self.user, edition=edition, team=team1, rating=5)
        darts = Darts.objects.create(edition=edition)
        game = Game.objects.create(
            discipline=darts,
            round=TeamSportRound.objects.create(discipline=darts, order=0),
            team1=team1, team2=team2, referees=team2, edition=edition,
        )
        event = GameEvent.objects.create(game=game, player1=player)
        blindtest = Blindtest.objects.create(edition=edition)
        guess = BlindtestGuess.objects.get(
            team=team1, blindtest_round__blindtest=blindtest, blindtest_round__order=1
        )
        return game, event, guess

    def as_user(self, user=None):
        client = APIClient()
        client.default_format = "json"
        if user is not None:
            client.force_authenticate(user=user)
        return client

    def private_reads(self):
        return [
            "/players/",
            f"/players/user/{self.user.id}/edition/{self.edition.id}/",
            "/ratings/",
            f"/ratings/player/{self.player.id}/",
            "/results/",  # stored points before the reveal
            "/games/",  # scores before the reveal
            f"/games/team/{self.game.team1_id}/played/",
            f"/games/team/{self.game.team1_id}/refereed/",
        ]


class TestPrivateReads(ClosedSetup):

    def test_need_a_token(self):
        client = self.as_user()
        for url in self.private_reads():
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 401)

    def test_refuse_a_player(self):
        client = self.as_user(self.user)
        for url in self.private_reads():
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 403)

    def test_answer_an_organiser(self):
        client = self.as_user(self.staff)
        for url in self.private_reads():
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)
        ratings = client.get(f"/ratings/player/{self.player.id}/").data
        self.assertEqual([(row["identifier"], row["rating"]) for row in ratings], [("CAR", 7)])
        played = client.get(f"/games/team/{self.game.team1_id}/played/").data
        self.assertEqual([row["id"] for row in played], [self.game.id])


class TestOpenViews(ClosedSetup):

    def test_public_reads_need_no_token(self):
        client = self.as_user()
        discipline = self.game.discipline_id
        for url in (
            "/editions/",
            f"/edition/{self.edition.id}/",
            "/edition/year/2026/summary/",
            "/disciplines/",
            f"/discipline/{discipline}/",
            f"/disciplines/{self.edition.id}/",
        ):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)

    def test_current_user_needs_a_token_of_any_user(self):
        self.assertEqual(self.as_user().get("/user/current/").status_code, 401)
        self.assertEqual(self.as_user(self.user).get("/user/current/").status_code, 200)

    def test_any_user_can_still_get_a_token(self):
        response = APIClient().post("/auth/token/", {"username": "player", "password": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)


class TestWrites(ClosedSetup):

    def answer(self, client, guess):
        return client.patch(
            f"/blindtest/guess/{guess.id}/answer/", {"artist": "Queen", "song": "Bohemian Rhapsody"}
        )

    def create_event(self, client, game):
        return client.post("/event/create/", {"game": game.id, "player1": self.player.id})

    def delete_event(self, client, event):
        return client.delete(f"/event/{event.id}/delete/")

    def assert_untouched(self):
        self.guess.refresh_from_db()
        self.assertEqual((self.guess.artist, self.guess.song), ("", ""))
        self.assertEqual(GameEvent.objects.filter(is_active=True).count(), 2)

    def test_need_a_token(self):
        client = self.as_user()
        self.assertEqual(self.answer(client, self.guess).status_code, 401)
        self.assertEqual(self.create_event(client, self.game).status_code, 401)
        self.assertEqual(self.delete_event(client, self.event).status_code, 401)
        self.assert_untouched()

    def test_refuse_a_player(self):
        client = self.as_user(self.user)
        self.assertEqual(self.answer(client, self.guess).status_code, 403)
        self.assertEqual(self.create_event(client, self.game).status_code, 403)
        self.assertEqual(self.delete_event(client, self.event).status_code, 403)
        self.assert_untouched()

    def test_an_organiser_writes_the_latest_edition(self):
        client = self.as_user(self.staff)
        response = self.answer(client, self.guess)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            (response.data["artist"], response.data["song"]), ("Queen", "Bohemian Rhapsody")
        )

        response = self.create_event(client, self.game)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(GameEvent.objects.filter(game=self.game, is_active=True).count(), 2)

        self.assertEqual(self.delete_event(client, self.event).status_code, 200)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_active)

    def test_409_outside_the_latest_edition(self):
        client = self.as_user(self.staff)
        self.assertEqual(self.answer(client, self.old_guess).status_code, 409)
        self.assertEqual(self.create_event(client, self.old_game).status_code, 409)
        self.assertEqual(self.delete_event(client, self.old_event).status_code, 409)
        self.old_guess.refresh_from_db()
        self.assertEqual(self.old_guess.artist, "")
        self.assertEqual(GameEvent.objects.filter(game=self.old_game, is_active=True).count(), 1)
