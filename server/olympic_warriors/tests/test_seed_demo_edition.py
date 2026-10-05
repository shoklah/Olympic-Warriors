"""The seed_demo_edition command: demo data for trying the team builder locally."""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from olympic_warriors import builder
from olympic_warriors.models import Edition, Player, Team


def run(*args):
    out = StringIO()
    call_command("seed_demo_edition", *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)
class TestSeedDemoEdition(TestCase):
    def test_refuses_without_debug(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                run()
        self.assertFalse(Edition.objects.filter(year=2040).exists())

    def test_creates_players_admin_and_no_teams(self):
        output = run()

        edition = Edition.objects.get(year=2040)
        self.assertEqual(Player.objects.filter(edition=edition).count(), 24)
        self.assertTrue(User.objects.get(username="demo-admin").is_superuser)
        self.assertFalse(Team.objects.filter(edition=edition).exists())
        self.assertIn("demo-password", output)
        self.assertIn("/2040/builder", output)
        data = builder.payload(edition)
        self.assertEqual(len(data["players"]), 24)
        self.assertTrue(data["registration_open"])
        self.assertGreaterEqual(sum(1 for p in data["players"] if not p["ratings"]), 3)
        self.assertGreaterEqual(len(data["skills"]), 1)

    def test_a_second_run_asks_to_remove_first(self):
        run()
        with self.assertRaises(CommandError):
            run()

    def test_remove_deletes_everything_and_is_harmless_twice(self):
        run()

        run("--remove")

        self.assertFalse(Edition.objects.filter(year=2040).exists())
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())
        run("--remove")
