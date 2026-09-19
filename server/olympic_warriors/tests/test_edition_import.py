"""End-to-end test: saving an Edition with a registration form creates players."""
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from olympic_warriors.models import Edition, Player, PlayerRating

FIXTURE = Path(__file__).parent / "fixtures" / "registration_2026_sample.csv"


def upload():
    return SimpleUploadedFile("registration_2026_sample.csv", FIXTURE.read_bytes())


class EditionImportTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Uploads land in a throwaway MEDIA_ROOT that dies with the test class.
        media_root = tempfile.TemporaryDirectory()
        cls.addClassCleanup(media_root.cleanup)
        cls.enterClassContext(override_settings(MEDIA_ROOT=media_root.name))

    def setUp(self):
        # Returning player from a previous edition, with the generated fallback email.
        self.thomas = User.objects.create_user(
            username="thomasdupont",
            first_name="Thomas",
            last_name="Dupont",
            email="thomasdupont@olympicwarriors.com",
            password="irrelevant",
        )
        self.edition = Edition.objects.create(
            year=2026,
            host="Toulouse",
            start_date="2026-08-01",
            end_date="2026-08-02",
            registration_form=upload(),
        )

    def test_creates_users_players_and_ratings(self):
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)
        self.assertEqual(PlayerRating.objects.count(), 40)

    def test_returning_player_links_to_existing_user_and_gets_real_email(self):
        player = Player.objects.get(user=self.thomas, edition=self.edition)

        self.thomas.refresh_from_db()
        self.assertEqual(self.thomas.email, "thomas@example.com")
        self.assertEqual(player.rating, 9)

    def test_new_user_gets_form_email_and_fallback_when_blank(self):
        alice = User.objects.get(username="alicemartin")
        chloe = User.objects.get(username="chloédelatour")

        self.assertEqual(alice.email, "alice@example.com")
        self.assertEqual(chloe.email, "chloédelatour@olympicwarriors.com")
        self.assertEqual(chloe.first_name, "Chloé")
        self.assertEqual(chloe.last_name, "DE LA TOUR")

    def test_first_name_only_is_imported_with_empty_last_name(self):
        bob = User.objects.get(username="bob")

        self.assertEqual(bob.first_name, "Bob")
        self.assertEqual(bob.last_name, "")
        self.assertEqual(Player.objects.get(user=bob).rating, 6)  # 5.8 rounded

    def test_player_rating_and_skill_ratings_match_formula(self):
        alice = Player.objects.get(user__username="alicemartin")

        self.assertEqual(alice.rating, 8)  # 7.6 rounded
        cardio = PlayerRating.objects.get(player=alice, identifier="CARD")
        self.assertEqual(cardio.name, "Cardio")
        self.assertEqual(cardio.rating, 6)

    def test_reimport_with_changed_answers_updates_player_and_skill_ratings(self):
        original = FIXTURE.read_text(encoding="utf-8")
        changed = original.replace(
            "Escalade - 10 ans - amateur,6,6,6,6,6,6,6,6,6,6,8",
            "Escalade - 10 ans - amateur,9,9,9,9,9,9,9,9,9,9,9",
        )
        self.assertNotEqual(changed, original)
        self.edition.registration_form = SimpleUploadedFile(
            "changed.csv", changed.encode("utf-8")
        )
        self.edition.save()

        alice = Player.objects.get(user__username="alicemartin", edition=self.edition)
        self.assertEqual(alice.rating, 9)
        self.assertEqual(PlayerRating.objects.get(player=alice, identifier="CARD").rating, 9)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)

    def test_reimport_does_not_duplicate_rows(self):
        self.edition.registration_form = upload()
        self.edition.save()

        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)
        self.assertEqual(PlayerRating.objects.count(), 40)

    def test_resaving_edition_without_form_does_not_import(self):
        edition = Edition.objects.create(
            year=2027, host="Nowhere", start_date="2027-08-01", end_date="2027-08-02"
        )
        edition.host = "Somewhere"
        edition.save()

        edition.refresh_from_db()
        self.assertEqual(edition.host, "Somewhere")
        self.assertFalse(Player.objects.filter(edition=edition).exists())

    def test_failed_import_does_not_leave_a_half_saved_edition(self):
        broken = SimpleUploadedFile("broken.csv", b"Horodateur,Autre\n1,2\n")

        with self.assertRaises(ValueError):
            Edition.objects.create(
                year=2028, host="X", start_date="2028-08-01", end_date="2028-08-02",
                registration_form=broken,
            )
        self.assertFalse(Edition.objects.filter(year=2028).exists())

    def test_blank_name_reports_spreadsheet_row(self):
        rows = FIXTURE.read_text(encoding="utf-8").splitlines(keepends=True)
        # Bob is the second data row; reported as "row 3" (header counts as row 1,
        # wrapped header cells ignored).
        bob = next(i for i, r in enumerate(rows) if r.startswith("2/17/2026"))
        rows[bob] = rows[bob].replace("Bob ", "")
        broken = SimpleUploadedFile("broken.csv", "".join(rows).encode("utf-8"))

        with self.assertRaises(ValueError) as ctx:
            Edition.objects.create(
                year=2027, host="X", start_date="2027-08-01", end_date="2027-08-02",
                registration_form=broken,
            )
        self.assertIn("row 3", str(ctx.exception))

    def test_reimport_reactivates_soft_deleted_rows(self):
        Player.objects.filter(user__username="bob", edition=self.edition).update(is_active=False)
        PlayerRating.objects.filter(player__user__username="bob").update(is_active=False)

        self.edition.registration_form = upload()
        self.edition.save()

        bob = Player.objects.get(user__username="bob", edition=self.edition)
        self.assertTrue(bob.is_active)
        self.assertTrue(PlayerRating.objects.get(player=bob, identifier="CARD").is_active)

    def test_duplicate_existing_rows_fail_with_participant_name(self):
        alice = Player.objects.get(user__username="alicemartin", edition=self.edition)
        PlayerRating.objects.create(player=alice, name="Cardio", identifier="CARD", rating=1)

        self.edition.registration_form = upload()
        with self.assertRaises(ValueError) as ctx:
            self.edition.save()
        self.assertIn("alicemartin", str(ctx.exception))
