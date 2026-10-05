"""
Builds the local demo seed from a registration form CSV: the real frequency, sports history,
wishes and global level of each player, by name, for seed_demo_edition to use. The seed holds
private answers, so it is a gitignored file (server/demo-seed.json), never committed.
"""

from django.core.management.base import BaseCommand

from olympic_warriors.demo_seed import read_form, save_seed, seed_path


class Command(BaseCommand):
    help = "Writes the demo seed (server/demo-seed.json) from a registration form CSV. Read only on the form."

    def add_arguments(self, parser):
        parser.add_argument("form", metavar="CSV", help="The registration form CSV export.")
        parser.add_argument("--out", metavar="PATH", help="Where to write it (default: the demo seed path).")

    def handle(self, *args, **options):
        rows = read_form(options["form"])
        path = options["out"] or seed_path()
        save_seed(rows, path)
        wished = sum(1 for r in rows.values() if r.team_with or r.team_avoid)
        self.stdout.write(f"Seed written to {path}: {len(rows)} players, {wished} with wishes.")
        self.stdout.write("It holds private answers: keep it out of git (it is ignored) and off shared hosts.")
