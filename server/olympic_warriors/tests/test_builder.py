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
