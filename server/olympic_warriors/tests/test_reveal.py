"""
The game, round and result read endpoints apply the summary's reveal rule: scores and
stored values are null until the discipline is revealed, except for staff. They also
leave out what the summary leaves out: games of an inactive round or discipline,
results of an inactive discipline or team, and every row of an inactive edition.
"""

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Crossfit,
    Darts,
    Discipline,
    Edition,
    Game,
    Team,
    TeamResult,
    TeamSportRound,
)

# Queries of a game list (the client is force-authenticated, so no auth query): the
# games with their discipline. Pinned so the reveal check cannot fan out per game.
GAME_LIST_QUERIES = 1
# Queries of a result list over one edition: the results with their team, discipline and
# edition, then one standings computation (teams, results, games).
RESULT_LIST_QUERIES = 4


class RevealSetup(APITestCase):
    """
    2026 with teams A, B, C; a hidden Darts with one round and one played game, A 7-3 B
    refereed by C (A 3 league points, +4); a hidden Crossfit with A's time 13:15.
    """

    def setUp(self):
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.a = Team.objects.create(name="A", edition=self.edition)
        self.b = Team.objects.create(name="B", edition=self.edition)
        self.c = Team.objects.create(name="C", edition=self.edition)
        self.darts = Darts.objects.create(edition=self.edition)  # hidden, PTS, no round yet
        self.round = TeamSportRound.objects.create(discipline=self.darts, order=0)
        self.game = Game.objects.create(
            discipline=self.darts, round=self.round, team1=self.a, team2=self.b,
            referees=self.c, edition=self.edition, score1=7, score2=3, is_played=True,
        )
        self.result = TeamResult.objects.get(discipline=self.darts, team=self.a)
        self.crossfit = Crossfit.objects.create(edition=self.edition)  # hidden, TIM
        self.time_result = TeamResult.objects.get(discipline=self.crossfit, team=self.a)
        TeamResult.objects.filter(id=self.time_result.id).update(time="00:13:15")

        self.staff = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.player = User.objects.create_user(username="player", password="x")

    def as_user(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    def reveal(self, discipline):
        Discipline.objects.filter(id=discipline.id).update(reveal_score=True)

    def game_urls(self):
        """Every endpoint that serialises self.game, rounds included."""
        game, round_, darts = self.game.id, self.round.id, self.darts.id
        team, referee = self.a.id, self.c.id
        return [
            f"/game/{game}/",
            "/games/",
            f"/games/discipline/{darts}/",
            f"/games/team/{team}/",
            f"/games/team/{team}/played/",
            f"/games/team/{referee}/refereed/",
            f"/games/edition/{self.edition.id}/",
            f"/games/discipline/{darts}/team/{team}/",
            f"/games/discipline/{darts}/team/{team}/played/",
            f"/games/discipline/{darts}/team/{referee}/refereed/",
            f"/games/round/{round_}/",
            f"/round/{round_}/",
            "/rounds/",
            f"/rounds/discipline/{darts}/",
        ]

    def result_urls(self, result):
        """Every endpoint that serialises `result`."""
        return [
            f"/result/{result.id}/",
            "/results/",
            f"/results/team/{result.team_id}/",
            f"/results/discipline/{result.discipline_id}/",
            f"/results/edition/{self.edition.id}/",
        ]

    def games(self, client, url):
        """The games a response carries: one game, a list, or the games of rounds."""
        response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        rows = response.data if isinstance(response.data, list) else [response.data]
        games = []
        for row in rows:
            games.extend(row["games"] if "games" in row else [row])
        return games

    def game_row(self, client, url):
        rows = [g for g in self.games(client, url) if g["id"] == self.game.id]
        self.assertEqual(len(rows), 1, url)
        return rows[0]

    def results(self, client, url):
        response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response.data if isinstance(response.data, list) else [response.data]

    def result_row(self, client, url, result):
        rows = [r for r in self.results(client, url) if r["id"] == result.id]
        self.assertEqual(len(rows), 1, url)
        return rows[0]


class TestGameScores(RevealSetup):

    def test_player_gets_null_scores_before_the_reveal(self):
        client = self.as_user(self.player)
        for url in self.game_urls():
            game = self.game_row(client, url)
            self.assertEqual((game["score1"], game["score2"]), (None, None), url)
            # the pairing, the referee and the played flag stay visible, as in the summary
            self.assertEqual((game["team1"], game["team2"]), (self.a.id, self.b.id), url)
            self.assertEqual(game["referees"], self.c.id, url)
            self.assertTrue(game["is_played"], url)

    def test_player_gets_the_scores_after_the_reveal(self):
        self.reveal(self.darts)
        client = self.as_user(self.player)
        for url in self.game_urls():
            game = self.game_row(client, url)
            self.assertEqual((game["score1"], game["score2"]), (7, 3), url)

    def test_staff_always_get_the_scores(self):
        client = self.as_user(self.staff)
        for url in self.game_urls():
            game = self.game_row(client, url)
            self.assertEqual((game["score1"], game["score2"]), (7, 3), url)
        self.reveal(self.darts)
        for url in self.game_urls():
            game = self.game_row(client, url)
            self.assertEqual((game["score1"], game["score2"]), (7, 3), url)

    def test_every_endpoint_needs_a_token(self):
        client = self.as_user(None)
        for url in self.game_urls() + self.result_urls(self.result):
            self.assertEqual(client.get(url).status_code, 401, url)

    def test_game_list_runs_in_a_fixed_number_of_queries(self):
        darts = Darts.objects.create(edition=self.edition)
        round_ = TeamSportRound.objects.create(discipline=darts, order=0)
        for _ in range(3):
            Game.objects.create(
                discipline=darts, round=round_, team1=self.b, team2=self.c,
                referees=self.a, edition=self.edition,
            )
        client = self.as_user(self.player)
        with self.assertNumQueries(GAME_LIST_QUERIES):
            response = client.get(f"/games/edition/{self.edition.id}/")
        self.assertEqual(len(response.data), 4)


class TestResultValues(RevealSetup):

    def test_player_gets_null_values_before_the_reveal(self):
        client = self.as_user(self.player)
        for result in (self.result, self.time_result):
            for url in self.result_urls(result):
                row = self.result_row(client, url, result)
                for field in ("points", "time", "ranking", "points_difference", "global_points"):
                    self.assertIsNone(row[field], (url, field))
                self.assertEqual(row["team_name"], "A", url)

    def test_player_gets_the_values_after_the_reveal(self):
        self.reveal(self.darts)
        self.reveal(self.crossfit)
        client = self.as_user(self.player)
        for url in self.result_urls(self.result):
            row = self.result_row(client, url, self.result)
            self.assertEqual(row["points"], 3, url)  # league points of the win
            self.assertEqual(row["points_difference"], 4, url)
            self.assertEqual(row["ranking"], 1, url)
            self.assertEqual(row["global_points"], 5, url)  # 3 registered, first: 3 + 2
        for url in self.result_urls(self.time_result):
            row = self.result_row(client, url, self.time_result)
            self.assertEqual(row["time"], "00:13:15", url)
            self.assertEqual(row["ranking"], 1, url)

    def test_staff_get_stored_values_but_no_ranking_before_the_reveal(self):
        client = self.as_user(self.staff)
        for url in self.result_urls(self.result):
            row = self.result_row(client, url, self.result)
            self.assertEqual(row["points"], 3, url)
            self.assertIsNone(row["ranking"], url)
            self.assertIsNone(row["points_difference"], url)
            self.assertIsNone(row["global_points"], url)
        for url in self.result_urls(self.time_result):
            row = self.result_row(client, url, self.time_result)
            self.assertEqual(row["time"], "00:13:15", url)
            self.assertIsNone(row["ranking"], url)

    def test_revealed_results_are_the_same_for_everyone(self):
        self.reveal(self.darts)
        url = f"/results/discipline/{self.darts.id}/"
        self.assertEqual(
            self.results(self.as_user(self.player), url),
            self.results(self.as_user(self.staff), url),
        )

    def test_result_list_computes_the_standings_once(self):
        self.reveal(self.darts)
        self.reveal(self.crossfit)
        client = self.as_user(self.player)
        with self.assertNumQueries(RESULT_LIST_QUERIES):
            response = client.get(f"/results/edition/{self.edition.id}/")
        self.assertEqual(len(response.data), 6)  # 3 teams x 2 disciplines


class TestInactiveRows(RevealSetup):
    """What the summary leaves out, these endpoints leave out: lists skip it, details 404."""

    def assert_game_gone(self, client):
        self.assertEqual(client.get(f"/game/{self.game.id}/").status_code, 404)
        for url in self.game_urls():
            if url.startswith(("/game/", "/round/")):
                continue
            self.assertNotIn(self.game.id, [g["id"] for g in self.games(client, url)], url)

    def test_game_of_an_inactive_round(self):
        TeamSportRound.objects.filter(id=self.round.id).update(is_active=False)
        client = self.as_user(self.staff)
        self.assert_game_gone(client)
        self.assertEqual(client.get(f"/round/{self.round.id}/").status_code, 404)
        self.assertEqual(self.games(client, f"/games/round/{self.round.id}/"), [])

    def test_game_and_results_of_an_inactive_discipline(self):
        Discipline.objects.filter(id=self.darts.id).update(is_active=False)
        client = self.as_user(self.staff)
        self.assert_game_gone(client)
        self.assertEqual(client.get(f"/round/{self.round.id}/").status_code, 404)
        self.assertEqual(self.results(client, f"/rounds/discipline/{self.darts.id}/"), [])
        self.assertEqual(client.get(f"/result/{self.result.id}/").status_code, 404)
        for url in self.result_urls(self.result)[1:]:
            ids = [r["id"] for r in self.results(client, url)]
            self.assertNotIn(self.result.id, ids, url)

    def test_inactive_game_is_left_out_of_its_round(self):
        Game.objects.filter(id=self.game.id).update(is_active=False)
        client = self.as_user(self.staff)
        self.assert_game_gone(client)
        self.assertEqual(self.games(client, f"/round/{self.round.id}/"), [])

    def test_result_of_an_inactive_team(self):
        Team.objects.filter(id=self.a.id).update(is_active=False)
        client = self.as_user(self.staff)
        self.assertEqual(client.get(f"/result/{self.result.id}/").status_code, 404)
        for url in self.result_urls(self.result)[1:]:
            ids = [r["id"] for r in self.results(client, url)]
            self.assertNotIn(self.result.id, ids, url)

    def test_rows_of_an_inactive_edition(self):
        """A player's token reads no more than the public, whose summary of it is a 404."""
        self.reveal(self.darts)
        self.reveal(self.crossfit)
        Edition.objects.filter(id=self.edition.id).update(is_active=False)
        self.assertEqual(self.client.get("/edition/year/2026/summary/").status_code, 404)
        for client in (self.as_user(self.player), self.as_user(self.staff)):
            self.assert_game_gone(client)
            self.assertEqual(client.get(f"/round/{self.round.id}/").status_code, 404)
            for url in ("/rounds/", f"/rounds/discipline/{self.darts.id}/"):
                self.assertNotIn(self.round.id, [r["id"] for r in self.results(client, url)], url)
            for result in (self.result, self.time_result):
                self.assertEqual(client.get(f"/result/{result.id}/").status_code, 404)
                for url in self.result_urls(result)[1:]:
                    ids = [r["id"] for r in self.results(client, url)]
                    self.assertNotIn(result.id, ids, url)
