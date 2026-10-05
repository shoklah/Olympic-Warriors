"""The seed_demo_edition command: demo data for trying the team builder locally."""
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from olympic_warriors import builder
from olympic_warriors.models import (
    Edition, Player, PlayerRating, PlayerSport, RegistrationSkill, Team,
)

NAMES = [
    ("Paul", "Durand"), ("Paul", "Lefevre"), ("Lea", "Martin"), ("Ines", "Moreau"),
    ("Camille", "Petit"), ("Hugo", "Roux"), ("Mathis", "Girard"), ("Sarah", "Blanc"),
    ("Theo", "Garnier"), ("Chloe", "Mercier"), ("Nathan", "Dupont"), ("Manon", "Fabre"),
    ("Louis", "Andre"), ("Jade", "Rousseau"),
]


def run(*args):
    out = StringIO()
    call_command("seed_demo_edition", *args, stdout=out)
    return out.getvalue()


def make_source(year=2026, inactive_user=False):
    edition = Edition.objects.create(
        year=year, host="Real", start_date=date(year, 9, 1), end_date=date(year, 9, 2)
    )
    RegistrationSkill.objects.create(
        edition=edition, identifier="CARD", name_fr="Cardio", name_en="Cardio", weight=1, order=0
    )
    users = []
    for i, (first, last) in enumerate(NAMES):
        user = User.objects.create_user(username=f"real{i}", first_name=first, last_name=last)
        users.append(user)
        player = Player.objects.create(
            user=user, edition=edition, rating=4 + i % 5, global_level=3 + i % 6
        )
        if i != 5:  # one player without any PlayerRating
            PlayerRating.objects.create(player=player, name="Cardio", identifier="CARD", rating=5)
    return edition, users


@override_settings(DEBUG=True)
class TestSeedDemoEdition(TestCase):
    def test_refuses_without_debug(self):
        make_source()
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                run()
        self.assertFalse(Edition.objects.filter(year=2040).exists())

    def test_copies_the_real_players_with_generated_extras(self):
        _, users = make_source()
        before = User.objects.count()

        output = run()

        edition = Edition.objects.get(year=2040)
        self.assertEqual(User.objects.count(), before + 1)  # demo-admin only
        self.assertTrue(User.objects.get(username="demo-admin").is_superuser)
        players = Player.objects.filter(edition=edition)
        self.assertEqual({p.user_id for p in players}, {u.pk for u in users})
        self.assertFalse(Team.objects.filter(edition=edition).exists())
        self.assertTrue(all(p.attendance_confirmed for p in players))
        self.assertEqual(
            list(edition.registrationskill_set.values_list("identifier", flat=True)), ["CARD"]
        )
        self.assertIn("/2040/builder", output)
        self.assertIn("Generated", output)

        data = builder.payload(edition)
        self.assertTrue(data["registration_open"])
        self.assertEqual(len(data["players"]), len(NAMES))
        texts = [p["team_with"] for p in data["players"] if p["team_with"]]
        self.assertIn("peu importe", texts)
        self.assertIn("Quelqu'un d'inconnu", texts)
        self.assertTrue(any(p["team_avoid"] for p in data["players"]))
        self.assertTrue(any(p["sports"] for p in data["players"]))
        incomplete = [p for p in data["players"] if not p["ratings"] and not p["sport_frequency"]]
        self.assertEqual(len(incomplete), 2)

    def test_is_deterministic(self):
        make_source()
        run()
        first = list(
            Player.objects.filter(edition__year=2040).order_by("user_id").values_list(
                "user_id", "team_with", "team_avoid", "sport_frequency"
            )
        )
        run("--remove")
        run()
        second = list(
            Player.objects.filter(edition__year=2040).order_by("user_id").values_list(
                "user_id", "team_with", "team_avoid", "sport_frequency"
            )
        )
        self.assertEqual(first, second)

    def test_from_year_and_missing_source(self):
        with self.assertRaises(CommandError):
            run()
        make_source(2025)
        with self.assertRaises(CommandError):
            run()
        run("--from-year", "2025")
        self.assertEqual(Player.objects.filter(edition__year=2040).count(), len(NAMES))

    def test_source_without_active_players(self):
        edition, _ = make_source()
        Player.objects.filter(edition=edition).update(is_active=False)
        with self.assertRaises(CommandError):
            run()

    def test_a_second_run_asks_to_remove_first(self):
        make_source()
        run()
        with self.assertRaises(CommandError):
            run()

    def test_remove_keeps_real_users_and_the_source(self):
        source, users = make_source()
        run()
        User.objects.create_user(username="demo-01")  # a leftover of the previous version

        run("--remove")

        self.assertFalse(Edition.objects.filter(year=2040).exists())
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())
        self.assertEqual(User.objects.filter(username__startswith="real").count(), len(users))
        self.assertEqual(Player.objects.filter(edition=source).count(), len(NAMES))
        self.assertEqual(PlayerRating.objects.count(), len(NAMES) - 1)
        run("--remove")
