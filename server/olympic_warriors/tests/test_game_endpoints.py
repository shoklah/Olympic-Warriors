"""
Game lists by team role and by round: a token is required (global IsAuthenticated),
and each answers with the matching active games.
"""

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import Darts, Edition, Game, Team, TeamSportRound


class GameEndpointsSetup(APITestCase):
    """
    Darts over two rounds. A plays g1 (played) and g2 (not played yet), referees g3, and
    plays the inactive g4, which no list returns.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.d = Team.objects.create(name="D", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)
        self.round1 = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.round2 = TeamSportRound.objects.create(discipline=self.darts, order=1)
        self.g1 = self.game(self.round1, self.a, self.b, self.c, is_played=True)
        self.g2 = self.game(self.round2, self.c, self.a, self.b)
        self.g3 = self.game(self.round1, self.b, self.d, self.a)
        self.g4 = self.game(self.round2, self.a, self.d, self.c, is_active=False)

        user = User.objects.create_user(username="player", password="x")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get(user=user).key}")

    def game(self, round_, team1, team2, referees, **fields):
        return Game.objects.create(
            discipline=self.darts, round=round_, team1=team1, team2=team2,
            referees=referees, edition=self.edition, **fields,
        )

    def ids(self, response):
        """Sorted game ids, duplicates kept, so a join that repeats a row fails."""
        return sorted(game["id"] for game in response.data)


class TestGameEndpoints(GameEndpointsSetup):

    def test_played_games_by_team(self):
        response = self.client.get(f"/games/team/{self.a.id}/played/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), sorted([self.g1.id, self.g2.id]))

    def test_played_games_by_team_match_the_discipline_scoped_list(self):
        """'Played' is the role (team1 or team2), not is_played: g2 is listed before it is played."""
        response = self.client.get(f"/games/team/{self.a.id}/played/")
        scoped = self.client.get(f"/games/discipline/{self.darts.id}/team/{self.a.id}/played/")
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(self.ids(response), self.ids(scoped))

    def test_refereed_games_by_team(self):
        response = self.client.get(f"/games/team/{self.a.id}/refereed/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [self.g3.id])

    def test_games_by_round(self):
        response = self.client.get(f"/games/round/{self.round1.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), sorted([self.g1.id, self.g3.id]))

    def test_games_by_round_skip_inactive_games(self):
        response = self.client.get(f"/games/round/{self.round2.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [self.g2.id])

    def test_every_list_needs_a_token(self):
        client = APIClient()
        self.assertEqual(client.get(f"/games/team/{self.a.id}/played/").status_code, 401)
        self.assertEqual(client.get(f"/games/team/{self.a.id}/refereed/").status_code, 401)
        self.assertEqual(client.get(f"/games/round/{self.round1.id}/").status_code, 401)
