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
