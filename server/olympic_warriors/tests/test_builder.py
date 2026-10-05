"""The team builder: draft rules, the payload, the stale check and Apply."""
from datetime import date

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
        PlayerSport.objects.create(player=self.ana, sport="Judo", level="league")

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
                "sports": [{"sport": "Judo", "level": "league"}], "team_with": "Bob",
                "team_avoid": "Carl", "team": None,
            },
        )

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

    def test_an_invalid_document_is_refused(self):
        with self.assertRaises(DraftError):
            builder.save_draft(self.edition, self.boss, {**self.document, "teams": [{"players": [999]}]}, None)
