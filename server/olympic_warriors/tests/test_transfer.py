"""Round-trip tests for exporting an edition and importing it with fresh ids."""
import copy
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from olympic_warriors.models import (
    Blindtest,
    BlindtestGuess,
    Crossfit,
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
from olympic_warriors.transfer import (
    FORMAT,
    TABLES,
    EditionExists,
    TransferError,
    export_edition,
    import_edition,
)


def build_edition(year=2024):
    """A small but complete edition: two teams, two players, rugby with a game, a blindtest."""
    edition = Edition.objects.create(
        year=year, host="Test", start_date=f"{year}-08-01", end_date=f"{year}-08-02"
    )
    # Name a file without uploading one and without replaying Edition.save(), which
    # would try to import the CSV.
    Edition.objects.filter(pk=edition.pk).update(registration_form="registration_forms/test.csv")
    edition.refresh_from_db()
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
    event = GameEvent(game=game, player1=p_alice, time=f"{year}-08-01T10:00:00+00:00")
    event.save_base(raw=True)
    RugbyEvent(
        gameevent_ptr_id=event.pk, game=game, player1=p_alice,
        time=f"{year}-08-01T10:00:00+00:00", event_type=RugbyEvent.RugbyEventTypes.START,
    ).save_base(raw=True, force_insert=True)

    Blindtest.objects.create(edition=edition)  # save() creates 10 rounds x 2 guesses
    Crossfit.objects.create(edition=edition)  # TIME discipline: two TeamResults with a time
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
                "Team": 2, "Player": 2, "PlayerRating": 2, "Discipline": 3, "TeamResult": 6,
                "TeamSportRound": 1, "Game": 1, "GameEvent": 1, "BlindtestRound": 10,
                "BlindtestGuess": 20,
            },
        )
        self.assertIn(("Red", "Rugby", 3), results)

    def test_document_has_no_database_ids_and_references_users_by_username(self):
        doc = export_edition(self.edition.year)

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
        doc = export_edition(self.edition.year)

        team_ids = {t["_id"] for t in doc["tables"]["Team"]}
        game = doc["tables"]["Game"][0]
        self.assertIn(game["team1"], team_ids)
        self.assertIn(game["referees"], team_ids)
        self.assertIn(game["round"], {r["_id"] for r in doc["tables"]["TeamSportRound"]})
        self.assertEqual(game["score1"], 5)

    def test_subclass_rows_are_marked(self):
        doc = export_edition(self.edition.year)

        disciplines = doc["tables"]["Discipline"]
        self.assertEqual({d["subclass"] for d in disciplines}, {"Rugby", "Blindtest", "Crossfit"})
        self.assertEqual(next(d for d in disciplines if d["subclass"] == "Rugby")["child"], {})
        event = doc["tables"]["GameEvent"][0]
        self.assertEqual(event["subclass"], "RugbyEvent")
        self.assertEqual(event["child"], {"event_type": "STA"})
        blindtest = next(d for d in disciplines if d["subclass"] == "Blindtest")
        round_blindtests = {r["blindtest"] for r in doc["tables"]["BlindtestRound"]}
        self.assertEqual(round_blindtests, {blindtest["_id"]})

    def test_dates_and_files_are_strings(self):
        doc = export_edition(self.edition.year)

        self.assertEqual(doc["edition"]["start_date"], "2024-08-01")
        self.assertEqual(doc["edition"]["registration_form"], "registration_forms/test.csv")
        self.assertEqual(doc["tables"]["GameEvent"][0]["time"], "2024-08-01T10:00:00+00:00")
        self.assertIsNone(doc["tables"]["GameEvent"][0]["player2"])
        self.assertIn("00:00:00", {r["time"] for r in doc["tables"]["TeamResult"]})

    def test_missing_year_raises(self):
        with self.assertRaises(Edition.DoesNotExist):
            export_edition(1999)


class ImportEditionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.enterClassContext(override_settings(MEDIA_ROOT=tmp.name))

    def setUp(self):
        self.edition = build_edition()
        self.before = snapshot(self.edition)
        self.document = export_edition(self.edition.year)
        Edition.objects.filter(year=2024).delete()
        # bob must be recreated by the import; alice pre-exists with different data.
        User.objects.filter(username="bob").delete()
        User.objects.filter(username="alice").update(email="kept@example.com")
        self.alice_id = User.objects.get(username="alice").pk

    def test_round_trip_recreates_every_row_without_side_effects(self):
        report = import_edition(self.document)

        edition = Edition.objects.get(year=2024)
        self.assertEqual(snapshot(edition), self.before)
        self.assertEqual(report["counts"], self.before[0])
        self.assertEqual(report["year"], 2024)
        self.assertEqual(report["edition_id"], edition.pk)
        self.assertNotEqual(edition.pk, self.edition.pk)
        self.assertEqual(edition.registration_form.name, "registration_forms/test.csv")
        self.assertEqual(report["missing_files"], ["registration_forms/test.csv"])

    def test_existing_user_is_reused_untouched_and_missing_user_created(self):
        report = import_edition(self.document)

        alice = User.objects.get(username="alice")
        bob = User.objects.get(username="bob")
        self.assertEqual(alice.pk, self.alice_id)
        self.assertEqual(alice.email, "kept@example.com")
        self.assertEqual(
            (bob.first_name, bob.last_name, bob.email), ("Bob", "B", "bob@example.com")
        )
        self.assertFalse(bob.is_staff)
        self.assertFalse(bob.is_superuser)
        self.assertTrue(bob.has_usable_password())
        self.assertFalse(bob.check_password("x"))
        self.assertEqual((report["users_reused"], report["users_created"]), (1, 1))
        self.assertEqual(Player.objects.get(user=alice).team.name, "Red")

    def test_foreign_keys_point_at_the_new_rows(self):
        import_edition(self.document)

        edition = Edition.objects.get(year=2024)
        game = Game.objects.get(edition=edition)
        self.assertEqual(
            (game.team1.edition_id, game.team2.edition_id, game.referees.edition_id),
            (edition.pk, edition.pk, edition.pk),
        )
        self.assertEqual(
            (game.team1.name, game.team2.name, game.referees.name), ("Red", "Blue", "Red")
        )
        self.assertEqual(game.round.discipline.edition_id, edition.pk)
        self.assertEqual(Rugby.objects.get(edition=edition).pk, game.discipline_id)
        event = RugbyEvent.objects.get(game=game)
        self.assertEqual(event.event_type, "STA")
        self.assertEqual(event.player1.user.username, "alice")
        self.assertIsNone(event.player2)
        red_guesses = BlindtestGuess.objects.filter(
            blindtest_round__blindtest__edition=edition, team__name="Red"
        )
        self.assertEqual(red_guesses.count(), 10)
        self.assertEqual(red_guesses.first().team.edition_id, edition.pk)
        bob_player = Player.objects.get(user__username="bob", edition=edition)
        self.assertEqual(bob_player.team.name, "Blue")
        self.assertEqual(Blindtest.objects.get(edition=edition).name, "Blindtest")
        crossfit = TeamResult.objects.get(
            discipline__edition=edition, discipline__name="Crossfit", team__name="Red"
        )
        self.assertEqual(str(crossfit.time), "00:00:00")

    def test_existing_year_aborts_unless_replace(self):
        import_edition(self.document)
        first_id = Edition.objects.get(year=2024).pk

        with self.assertRaises(EditionExists):
            import_edition(self.document)
        self.assertEqual(Edition.objects.filter(year=2024).count(), 1)
        self.assertEqual(snapshot(Edition.objects.get(year=2024)), self.before)

        import_edition(self.document, replace=True)
        edition = Edition.objects.get(year=2024)
        self.assertNotEqual(edition.pk, first_id)
        self.assertEqual(snapshot(edition), self.before)
        self.assertEqual(User.objects.filter(username__in=["alice", "bob"]).count(), 2)

    def test_unknown_reference_rolls_back(self):
        broken = copy.deepcopy(self.document)
        broken["tables"]["Game"][0]["team1"] = 999999

        with self.assertRaises(TransferError) as ctx:
            import_edition(broken)
        self.assertIn("Game", str(ctx.exception))
        self.assertIn("999999", str(ctx.exception))
        self.assertFalse(Edition.objects.filter(year=2024).exists())
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_unknown_user_rolls_back(self):
        broken = copy.deepcopy(self.document)
        broken["tables"]["Player"][0]["user"] = "nobody"

        with self.assertRaises(TransferError) as ctx:
            import_edition(broken)
        self.assertIn("nobody", str(ctx.exception))
        self.assertFalse(Edition.objects.filter(year=2024).exists())

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(TransferError):
            import_edition({**self.document, "format": 2})
        self.assertFalse(Edition.objects.filter(year=2024).exists())

    def test_unknown_table_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken["tables"]["Tiebreak"] = [{"_id": 1}]

        with self.assertRaises(TransferError) as ctx:
            import_edition(broken)
        self.assertIn("Tiebreak", str(ctx.exception))
        self.assertFalse(Edition.objects.filter(year=2024).exists())

    def test_missing_media_files_are_reported(self):
        doc = copy.deepcopy(self.document)
        doc["edition"]["registration_form"] = "registration_forms/nope.csv"

        report = import_edition(doc)

        self.assertEqual(report["missing_files"], ["registration_forms/nope.csv"])
        self.assertEqual(
            Edition.objects.get(year=2024).registration_form.name, "registration_forms/nope.csv"
        )
