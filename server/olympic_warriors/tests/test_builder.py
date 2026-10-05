"""The team builder: draft rules, the payload, the stale check and Apply."""
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, Player, TeamDraft


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


def make_player(edition, username, rating=5, **kw):
    user = User.objects.create(username=username, first_name=username.title(), last_name="Test")
    return Player.objects.create(user=user, edition=edition, rating=rating, **kw)


class TestTeamDraftModel(TestCase):
    def test_one_draft_per_edition_with_an_empty_document_by_default(self):
        edition = make_edition()

        draft = TeamDraft.objects.create(edition=edition)

        self.assertEqual(draft.document, {})
        self.assertEqual(edition.team_draft, draft)
        self.assertIsNotNone(draft.updated_at)
        with self.assertRaises(Exception):
            TeamDraft.objects.create(edition=edition)


from olympic_warriors.builder import DraftError, validate_draft  # noqa: E402

IDS = [1, 2, 3, 4, 5, 6]


def doc(**changes):
    document = {
        "players_per_team": 3,
        "seed": 7,
        "links": [{"player": 1, "kind": "with", "target": 2}],
        "teams": [{"players": [1, 2, 3]}, {"players": [4, 5]}],
        "locked": [1],
    }
    document.update(changes)
    return document


class TestValidateDraft(TestCase):
    def codes(self, document):
        with self.assertRaises(DraftError) as caught:
            validate_draft(document, IDS)
        return caught.exception.codes

    def test_a_good_draft_is_returned_with_exactly_its_keys(self):
        cleaned = validate_draft(doc(extra="ignored"), IDS)

        self.assertEqual(set(cleaned), {"players_per_team", "seed", "links", "teams", "locked"})
        self.assertEqual(cleaned["teams"], [{"players": [1, 2, 3]}, {"players": [4, 5]}])

    def test_a_draft_before_any_proposal_is_valid(self):
        cleaned = validate_draft(doc(teams=[], locked=[], links=[]), IDS)

        self.assertEqual(cleaned["teams"], [])

    def test_shape_errors(self):
        self.assertEqual(self.codes([]), ["invalid_draft"])
        self.assertEqual(self.codes(doc(seed=-1)), ["invalid_draft"])
        self.assertEqual(self.codes(doc(seed=True)), ["invalid_draft"])
        self.assertEqual(self.codes(doc(teams="x")), ["invalid_draft"])
        self.assertEqual(self.codes(doc(teams=[{"players": "x"}])), ["invalid_draft"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "love", "target": 2}])), ["invalid_draft"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "with", "target": 1}])), ["invalid_draft"])

    def test_an_unhashable_or_missing_link_kind_is_invalid_not_a_crash(self):
        for kind in ([], {}, None, 3):
            with self.subTest(kind=kind):
                links = [{"player": 1, "kind": kind, "target": 2}]
                self.assertEqual(self.codes(doc(links=links)), ["invalid_draft"])

    def test_players_per_team_is_two_to_twenty(self):
        for bad in (1, 21, "3", None, True):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(doc(players_per_team=bad)), ["bad_size"])

    def test_unknown_players_are_refused_everywhere(self):
        self.assertEqual(self.codes(doc(teams=[{"players": [1, 99]}], locked=[])), ["unknown_player"])
        self.assertEqual(self.codes(doc(links=[{"player": 1, "kind": "with", "target": 99}])), ["unknown_player"])

    def test_a_player_in_two_teams_is_refused(self):
        self.assertEqual(self.codes(doc(teams=[{"players": [1, 2]}, {"players": [2, 3]}], locked=[])), ["invalid_draft"])

    def test_a_locked_player_must_be_placed(self):
        self.assertEqual(self.codes(doc(locked=[6])), ["invalid_draft"])

    def test_too_many_links(self):
        links = [{"player": 1, "kind": "with", "target": 2}] * 201
        self.assertEqual(self.codes(doc(links=links)), ["too_many_links"])


from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from olympic_warriors import builder  # noqa: E402
from olympic_warriors.models import PlayerRating, PlayerSport, RegistrationSkill, Team  # noqa: E402


def make_skill(edition, identifier="CARD", order=0):
    return RegistrationSkill.objects.create(
        edition=edition, name_fr=f"{identifier} fr", name_en=f"{identifier} en",
        identifier=identifier, weight=4, order=order,
    )


class TestPayload(TestCase):
    def setUp(self):
        self.edition = make_edition()
        make_skill(self.edition)
        self.ana = make_player(
            self.edition, "ana", rating=7, global_level=8, sport_frequency="two_hours",
            team_with="Bob", team_avoid="Carl",
        )
        PlayerRating.objects.create(player=self.ana, name="Cardio", identifier="CARD", rating=6)
        PlayerSport.objects.create(
            player=self.ana, sport="Judo", level="league", practice="regularly", notes="Ceinture marron"
        )

    def test_the_roster_carries_the_private_answers_and_nothing_of_the_user(self):
        body = builder.payload(self.edition)

        self.assertEqual(body["edition"], {"year": 2027})
        self.assertEqual(body["skills"], [{"identifier": "CARD", "name_fr": "CARD fr", "name_en": "CARD en"}])
        self.assertFalse(body["teams_exist"])
        self.assertFalse(body["registration_open"])
        self.assertIsNone(body["draft"])
        player = body["players"][0]
        self.assertEqual(
            player,
            {
                "id": self.ana.pk, "first_name": "Ana", "last_name": "Test", "rating": 7,
                "global_level": 8, "ratings": {"CARD": 6}, "sport_frequency": "two_hours",
                "sports": [{"sport": "Judo", "level": "league", "practice": "regularly", "notes": "Ceinture marron"}],
                "team_with": "Bob",
                "team_avoid": "Carl", "team": None,
            },
        )

    def test_registration_open_follows_the_window(self):
        self.assertFalse(builder.payload(self.edition)["registration_open"])
        Edition.objects.filter(pk=self.edition.pk).update(registration_opens=date(2026, 1, 1))
        self.edition.refresh_from_db()

        self.assertTrue(builder.payload(self.edition)["registration_open"])

    def test_only_active_players_of_active_users_are_listed(self):
        gone = make_player(self.edition, "gone")
        Player.objects.filter(pk=gone.pk).update(is_active=False)
        left = make_player(self.edition, "left")
        User.objects.filter(pk=left.user_id).update(is_active=False)

        ids = [p["id"] for p in builder.payload(self.edition)["players"]]

        self.assertEqual(ids, [self.ana.pk])

    def test_teams_exist_and_a_valid_team_are_reported(self):
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(pk=self.ana.pk).update(team=team)

        body = builder.payload(self.edition)

        self.assertTrue(body["teams_exist"])
        self.assertEqual(body["players"][0]["team"], team.pk)

    def test_the_query_count_does_not_grow_with_the_roster(self):
        def count():
            with CaptureQueriesContext(connection) as queries:
                builder.payload(self.edition)
            return len(queries)

        before = count()
        for i in range(5):
            player = make_player(self.edition, f"p{i}")
            PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=5)
            PlayerSport.objects.create(player=player, sport="Tennis")

        self.assertEqual(count(), before)
        self.assertEqual(before, builder.BUILDER_QUERIES)


class TestSaveDraft(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.ana = make_player(self.edition, "ana")
        self.bob = make_player(self.edition, "bob")
        self.document = {"players_per_team": 3, "seed": 1, "links": [], "teams": [], "locked": []}

    def test_a_first_save_creates_the_row_and_stamps_the_author(self):
        saved = builder.save_draft(self.edition, self.boss, self.document, None)

        self.assertEqual(saved.updated_by, self.boss)
        self.assertEqual(saved.document["players_per_team"], 3)

    def test_a_save_based_on_the_current_version_updates_it(self):
        first = builder.save_draft(self.edition, self.boss, self.document, None)

        second = builder.save_draft(
            self.edition, self.boss, {**self.document, "seed": 2}, first.updated_at.isoformat()
        )

        self.assertEqual(second.document["seed"], 2)
        self.assertEqual(TeamDraft.objects.count(), 1)

    def test_a_stale_save_is_refused_and_hands_back_the_stored_draft(self):
        first = builder.save_draft(self.edition, self.boss, self.document, None)
        builder.save_draft(self.edition, self.boss, {**self.document, "seed": 2}, first.updated_at.isoformat())

        with self.assertRaises(builder.StaleDraft) as stale:
            builder.save_draft(self.edition, self.boss, {**self.document, "seed": 3}, first.updated_at.isoformat())

        self.assertEqual(stale.exception.current.document["seed"], 2)

    def test_a_save_without_a_base_over_an_existing_draft_is_stale(self):
        builder.save_draft(self.edition, self.boss, self.document, None)

        with self.assertRaises(builder.StaleDraft):
            builder.save_draft(self.edition, self.boss, self.document, None)

    def test_a_save_based_on_a_cleared_draft_is_stale_with_no_current(self):
        with self.assertRaises(builder.StaleDraft) as stale:
            builder.save_draft(self.edition, self.boss, self.document, "2027-01-01T00:00:00+00:00")

        self.assertIsNone(stale.exception.current)

    def test_save_and_apply_both_lock_the_edition_row_first(self):
        with CaptureQueriesContext(connection) as saving:
            builder.save_draft(self.edition, self.boss, self.document, None)
        edition_table = Edition._meta.db_table
        locks = [q["sql"] for q in saving if "FOR UPDATE" in q["sql"]]
        self.assertTrue(locks and edition_table in locks[0], locks)

        with CaptureQueriesContext(connection) as applying:
            with self.assertRaises(builder.ApplyRefused):
                builder.apply(self.edition, "x")
        locks = [q["sql"] for q in applying if "FOR UPDATE" in q["sql"]]
        self.assertTrue(locks and edition_table in locks[0], locks)

    def test_a_lost_first_save_race_is_stale_with_the_stored_draft(self):
        # The winner's row exists but this save's read did not see it (it read before the winner committed).
        TeamDraft.objects.create(edition=self.edition, document={**self.document, "seed": 9}, updated_by=self.boss)
        blind = MagicMock()
        blind.filter.return_value.first.return_value = None

        with patch.object(TeamDraft.objects, "select_for_update", return_value=blind):
            with self.assertRaises(builder.StaleDraft) as stale:
                builder.save_draft(self.edition, self.boss, self.document, None)

        self.assertEqual(stale.exception.current.document["seed"], 9)

    def test_an_invalid_document_is_refused(self):
        with self.assertRaises(DraftError):
            builder.save_draft(self.edition, self.boss, {**self.document, "teams": [{"players": [999]}]}, None)


from olympic_warriors.models import Darts, Discipline, Relay, TeamResult  # noqa: E402


class TestApply(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.players = [make_player(self.edition, f"p{i}") for i in range(5)]
        self.ids = [p.pk for p in self.players]

    def store(self, teams, **extra):
        document = {"players_per_team": 3, "seed": 1, "links": [], "teams": teams, "locked": [], **extra}
        return builder.save_draft(self.edition, self.boss, document, None)

    def apply(self):
        """Apply the stored draft as a page that has just saved it would."""
        return builder.apply(self.edition, TeamDraft.objects.get().updated_at.isoformat())

    def test_creates_the_teams_sets_the_players_and_deletes_the_draft(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        result = self.apply()

        self.assertEqual([t["name"] for t in result["teams"]], ["Équipe 1", "Équipe 2"])
        teams = list(Team.objects.filter(edition=self.edition).order_by("id"))
        self.assertEqual([t.name for t in teams], ["Équipe 1", "Équipe 2"])
        for player in self.players[:3]:
            player.refresh_from_db()
            self.assertEqual(player.team, teams[0])
        self.players[4].refresh_from_db()
        self.assertEqual(self.players[4].team, teams[1])
        self.assertFalse(TeamDraft.objects.exists())

    def test_backfills_a_result_per_team_in_every_existing_discipline(self):
        relay = Relay.objects.create(edition=self.edition)
        darts = Darts.objects.create(edition=self.edition)
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        self.apply()

        for discipline in (relay, darts):
            self.assertEqual(TeamResult.objects.filter(discipline=discipline).count(), 2)

    def test_reports_the_disciplines_with_a_pairing_system_and_no_round(self):
        scheduled = Darts.objects.create(edition=self.edition)
        Discipline.objects.filter(pk=scheduled.pk).update(pairing_system=Discipline.PairingSystem.ROUND_ROBIN)
        Relay.objects.create(edition=self.edition)
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])

        result = self.apply()

        self.assertEqual([d["id"] for d in result["unscheduled"]], [scheduled.pk])

    def test_refusals(self):
        with self.assertRaises(builder.ApplyRefused) as refused:
            builder.apply(self.edition, None)
        self.assertEqual((refused.exception.code, refused.exception.status), ("no_draft", 409))

        self.store([{"players": self.ids[:3]}])  # one team, two players unplaced
        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()
        self.assertEqual((refused.exception.code, refused.exception.status), ("bad_size", 400))

        builder.save_draft(
            self.edition, self.boss,
            {"players_per_team": 3, "seed": 1, "links": [], "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:4]}], "locked": []},
            TeamDraft.objects.get().updated_at.isoformat(),
        )  # one player missing
        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()
        self.assertEqual((refused.exception.code, refused.exception.status), ("incomplete", 400))

    def test_unbalanced_sizes_are_refused(self):
        self.store([{"players": self.ids[:4]}, {"players": self.ids[4:]}])

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual(refused.exception.code, "bad_size")
        self.assertFalse(Team.objects.exists())

    def test_existing_teams_refuse_the_apply(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        Team.objects.create(name="Red", edition=self.edition)

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual((refused.exception.code, refused.exception.status), ("teams_exist", 409))

    def test_a_player_who_left_since_the_draft_makes_it_incomplete(self):
        self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        Player.objects.filter(pk=self.ids[0]).update(is_active=False)

        with self.assertRaises(builder.ApplyRefused) as refused:
            self.apply()

        self.assertEqual(refused.exception.code, "incomplete")

    def test_a_draft_saved_by_someone_else_since_is_refused_and_nothing_is_created(self):
        first = self.store([{"players": self.ids[:3]}, {"players": self.ids[3:]}])
        seen = first.updated_at.isoformat()
        builder.save_draft(
            self.edition, self.boss,
            {"players_per_team": 3, "seed": 2, "links": [], "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:]}], "locked": []},
            seen,
        )

        with self.assertRaises(builder.ApplyRefused) as refused:
            builder.apply(self.edition, seen)

        self.assertEqual((refused.exception.code, refused.exception.status), ("stale_draft", 409))
        self.assertFalse(Team.objects.exists())
        self.assertTrue(TeamDraft.objects.exists())


from rest_framework.test import APIClient  # noqa: E402


class TestBuilderAPI(TestCase):
    def setUp(self):
        self.edition = make_edition(2027)
        self.boss = User.objects.create_user("boss", is_staff=True)
        self.player_user = User.objects.create_user("lea")
        self.ids = [make_player(self.edition, f"p{i}").pk for i in range(4)]
        self.client = APIClient()
        self.client.force_authenticate(self.boss)
        self.url = "/builder/2027/"
        self.document = {
            "players_per_team": 3, "seed": 5, "links": [],
            "teams": [{"players": self.ids[:2]}, {"players": self.ids[2:]}], "locked": [],
        }

    def test_the_routes_are_staff_only(self):
        for client_user in (None, self.player_user):
            client = APIClient()
            if client_user:
                client.force_authenticate(client_user)
            for method, url in (("get", self.url), ("put", self.url + "draft/"), ("post", self.url + "apply/")):
                with self.subTest(user=client_user, url=url):
                    response = getattr(client, method)(url, {}, format="json") if method != "get" else client.get(url)
                    self.assertEqual(response.status_code, 403 if client_user else 401)

    def test_get_serves_the_payload_uncached(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["players"]), 4)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("username", str(response.json()))

    def test_only_the_latest_edition_and_a_known_year(self):
        make_edition(2028)

        self.assertEqual(self.client.get("/builder/2027/").status_code, 409)
        self.assertEqual(self.client.get("/builder/2027/").json(), {"error": "not_latest"})
        self.assertEqual(self.client.get("/builder/2999/").status_code, 404)

    def test_put_saves_and_returns_the_new_version(self):
        response = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document"]["seed"], 5)
        self.assertIn("updated_at", response.json())

    def test_put_refuses_an_invalid_document_with_its_codes(self):
        bad = {**self.document, "teams": [{"players": [999]}]}

        response = self.client.put(self.url + "draft/", {"document": bad, "based_on": None}, format="json")

        self.assertEqual((response.status_code, response.json()), (400, {"errors": ["unknown_player"]}))

    def test_a_stale_put_is_409_with_the_stored_draft(self):
        first = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json").json()
        self.client.put(self.url + "draft/", {"document": {**self.document, "seed": 6}, "based_on": first["updated_at"]}, format="json")

        response = self.client.put(self.url + "draft/", {"document": self.document, "based_on": first["updated_at"]}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "stale_draft")
        self.assertEqual(response.json()["draft"]["document"]["seed"], 6)

    def test_delete_clears_the_draft(self):
        self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json")

        self.assertEqual(self.client.delete(self.url + "draft/").status_code, 204)
        self.assertFalse(TeamDraft.objects.exists())

    def test_apply_creates_the_teams(self):
        saved = self.client.put(self.url + "draft/", {"document": self.document, "based_on": None}, format="json").json()

        response = self.client.post(self.url + "apply/", {"based_on": saved["updated_at"]}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["teams"]), 2)
        self.assertEqual(response.json()["unscheduled"], [])

    def test_apply_refusals_carry_their_status(self):
        no_draft = self.client.post(self.url + "apply/", {"based_on": None}, format="json")
        self.assertEqual((no_draft.status_code, no_draft.json()), (409, {"error": "no_draft"}))
        saved = self.client.put(self.url + "draft/", {"document": {**self.document, "teams": [{"players": self.ids[:1]}]}, "based_on": None}, format="json").json()

        response = self.client.post(self.url + "apply/", {"based_on": saved["updated_at"]}, format="json")
        self.assertEqual((response.status_code, response.json()), (400, {"error": "bad_size"}))

        stale = self.client.post(self.url + "apply/", {"based_on": "2000-01-01T00:00:00+00:00"}, format="json")
        self.assertEqual((stale.status_code, stale.json()), (409, {"error": "stale_draft"}))


from django.test import override_settings  # noqa: E402


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestEditionAdminLink(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))

    def test_the_latest_edition_page_links_to_the_builder_when_the_front_is_known(self):
        edition = make_edition(2027)

        with override_settings(PUBLIC_URL="https://ow.example"):
            response = self.client.get(f"/admin/olympic_warriors/edition/{edition.pk}/change/")

        self.assertContains(response, 'href="https://ow.example/2027/builder"')

    def test_no_link_without_a_public_url_or_for_an_older_edition(self):
        old = make_edition(2026)
        make_edition(2027)

        with override_settings(PUBLIC_URL="https://ow.example"):
            older = self.client.get(f"/admin/olympic_warriors/edition/{old.pk}/change/")
        with override_settings(PUBLIC_URL=""):
            latest = self.client.get(f"/admin/olympic_warriors/edition/{Edition.objects.get(year=2027).pk}/change/")

        self.assertNotContains(older, "/builder")
        self.assertNotContains(latest, "/builder")
