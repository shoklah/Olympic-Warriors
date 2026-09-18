"""End-to-end test: saving an Edition with a registration form creates players."""
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from olympic_warriors.models import Edition, Player, PlayerRating

FIXTURE = Path(__file__).parent / "fixtures" / "registration_2026_sample.csv"
MEDIA_TMP = tempfile.mkdtemp()


def upload():
    return SimpleUploadedFile("registration_2026_sample.csv", FIXTURE.read_bytes())


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EditionImportTests(TestCase):
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
        self.assertEqual(Player.objects.get(user=bob).rating, 5)

    def test_player_rating_and_skill_ratings_match_formula(self):
        alice = Player.objects.get(user__username="alicemartin")

        self.assertEqual(alice.rating, 7)  # 7.6 truncated by IntegerField
        cardio = PlayerRating.objects.get(player=alice, identifier="CARD")
        self.assertEqual(cardio.name, "Cardio")
        self.assertEqual(cardio.rating, 6)

    def test_reimport_does_not_duplicate_rows(self):
        self.edition.registration_form = upload()
        self.edition.save()

        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Player.objects.filter(edition=self.edition).count(), 4)
        self.assertEqual(PlayerRating.objects.count(), 40)

    def test_blank_name_reports_csv_line(self):
        rows = FIXTURE.read_text(encoding="utf-8").splitlines(keepends=True)
        # Bob is the second data row; reported as "line 3" (header counts as line 1,
        # wrapped header cells ignored).
        rows[-3] = rows[-3].replace("Bob ", "")
        broken = SimpleUploadedFile("broken.csv", "".join(rows).encode("utf-8"))

        with self.assertRaises(ValueError) as ctx:
            Edition.objects.create(
                year=2027, host="X", start_date="2027-08-01", end_date="2027-08-02",
                registration_form=broken,
            )
        self.assertIn("line 3", str(ctx.exception))
