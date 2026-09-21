"""
Export an edition and everything attached to it to a JSON file without database ids.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from olympic_warriors.models import Edition
from olympic_warriors.transfer import export_edition


class Command(BaseCommand):
    """
    Export an edition to a transfer document (see olympic_warriors.transfer).
    """

    help = "Export an edition and all its rows to a JSON document without database ids."

    def add_arguments(self, parser):
        parser.add_argument("year", type=int)
        parser.add_argument("--out", required=True, help="Path of the JSON file to write.")

    def handle(self, *args, **options):
        year = options["year"]
        try:
            document = export_edition(year)
        except Edition.DoesNotExist as exc:
            raise CommandError(f"No edition for year {year}") from exc
        except Edition.MultipleObjectsReturned as exc:
            raise CommandError(f"Several editions for year {year}; fix the data first") from exc

        with open(options["out"], "w", encoding="utf-8") as out:
            json.dump(document, out, ensure_ascii=False, indent=2)

        counts = ", ".join(f"{name}={len(rows)}" for name, rows in document["tables"].items())
        self.stdout.write(
            f"Exported edition {year} to {options['out']}: "
            f"{len(document['users'])} users, {counts}"
        )
