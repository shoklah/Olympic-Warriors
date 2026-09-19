"""Round-trip tests for exporting an edition and importing it with fresh ids."""
import copy

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import (
    Blindtest,
    BlindtestGuess,
    Edition,
    Game,
    GameEvent,
    Player,
    PlayerRating,
    Rugby,
    RugbyEvent,
    Team,
    TeamResult,
    TeamSportRound,
)
from olympic_warriors.transfer import FORMAT, TABLES, export_edition


def build_edition(year=2024):
    """A small but complete edition: two teams, two players, rugby with a game, a blindtest."""
    edition = Edition.objects.create(
        year=year, host="Test", start_date=f"{year}-08-01", end_date=f"{year}-08-02"
    )
    alice = User.objects.create_user(
        username="alice", first_name="Alice", last_name="A", email="alice@example.com", password="x"
    )
    bob = User.objects.create_user(
        username="bob", first_name="Bob", last_name="B", email="bob@example.com", password="x"
    )
    red = Team.objects.create(name="Red", edition=edition)
    blue = Team.objects.create(name="Blue", edition=edition)
    p_alice = Player.objects.create(user=alice, edition=edition, rating=7, team=red)
    p_bob = Player.objects.create(user=bob, edition=edition, rating=5, team=blue)
    for player in (p_alice, p_bob):
        PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=6)

    rugby = Rugby.objects.create(edition=edition)  # save() creates one TeamResult per team
    round1 = TeamSportRound.objects.create(discipline=rugby, order=1)
    game = Game.objects.create(  # save() gives Red 3 points
        discipline=rugby, round=round1, team1=red, team2=blue, referees=red,
        edition=edition, score1=5, score2=0,
    )
    # Raw saves: RugbyEvent.save() validates and rescores, which is not under test here.
    event = GameEvent(game=game, player1=p_alice, time="2024-08-01T10:00:00+00:00")
    event.save_base(raw=True)
    RugbyEvent(
        gameevent_ptr_id=event.pk, game=game, player1=p_alice,
        time="2024-08-01T10:00:00+00:00", event_type=RugbyEvent.RugbyEventTypes.START,
    ).save_base(raw=True, force_insert=True)

    Blindtest.objects.create(edition=edition)  # save() creates 10 rounds x 2 guesses
    return edition


def snapshot(edition):
    """Row counts per exported table plus the values that save() side effects would change."""
    counts = {
        name: model.objects.filter(**{lookup: edition}).count() for name, model, lookup in TABLES
    }
    results = sorted(
        TeamResult.objects.filter(discipline__edition=edition)
        .values_list("team__name", "discipline__name", "points")
    )
    return counts, results


class ExportEditionTests(TestCase):
    def setUp(self):
        self.edition = build_edition()

    def test_fixture_shape(self):
        counts, results = snapshot(self.edition)
        self.assertEqual(
            counts,
            {
                "Team": 2, "Player": 2, "PlayerRating": 2, "Discipline": 2, "TeamResult": 4,
                "TeamSportRound": 1, "Game": 1, "GameEvent": 1, "BlindtestRound": 10,
                "BlindtestGuess": 20,
            },
        )
        self.assertIn(("Red", "Rugby", 3), results)

    def test_document_has_no_database_ids_and_references_users_by_username(self):
        doc = export_edition(2024)

        self.assertEqual(doc["format"], FORMAT)
        self.assertEqual(doc["edition"]["year"], 2024)
        self.assertNotIn("id", doc["edition"])
        self.assertEqual([u["username"] for u in doc["users"]], ["alice", "bob"])
        self.assertNotIn("password", doc["users"][0])
        self.assertNotIn("is_staff", doc["users"][0])
        players = doc["tables"]["Player"]
        self.assertEqual({p["user"] for p in players}, {"alice", "bob"})
        self.assertNotIn("edition", players[0])
        self.assertNotIn("id", players[0])
        self.assertIn("_id", players[0])

    def test_rows_reference_each_other_by_local_id(self):
        doc = export_edition(2024)

        team_ids = {t["_id"] for t in doc["tables"]["Team"]}
        game = doc["tables"]["Game"][0]
        self.assertIn(game["team1"], team_ids)
        self.assertIn(game["referees"], team_ids)
        self.assertIn(game["round"], {r["_id"] for r in doc["tables"]["TeamSportRound"]})
        self.assertEqual(game["score1"], 5)

    def test_subclass_rows_are_marked(self):
        doc = export_edition(2024)

        disciplines = doc["tables"]["Discipline"]
        self.assertEqual({d["subclass"] for d in disciplines}, {"Rugby", "Blindtest"})
        self.assertEqual(disciplines[0]["child"], {})
        event = doc["tables"]["GameEvent"][0]
        self.assertEqual(event["subclass"], "RugbyEvent")
        self.assertEqual(event["child"], {"event_type": "STA"})
        blindtest = next(d for d in disciplines if d["subclass"] == "Blindtest")
        round_blindtests = {r["blindtest"] for r in doc["tables"]["BlindtestRound"]}
        self.assertEqual(round_blindtests, {blindtest["_id"]})

    def test_dates_and_files_are_strings(self):
        doc = export_edition(2024)

        self.assertEqual(doc["edition"]["start_date"], "2024-08-01")
        self.assertEqual(doc["edition"]["registration_form"], "")
        self.assertEqual(doc["tables"]["GameEvent"][0]["time"], "2024-08-01T10:00:00+00:00")

    def test_missing_year_raises(self):
        with self.assertRaises(Edition.DoesNotExist):
            export_edition(1999)
