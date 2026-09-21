"""
Import an edition exported with export_edition, giving every row a fresh id.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from olympic_warriors.transfer import TransferError, import_edition


class DryRun(Exception):
    """Raised inside the transaction to roll a dry run back."""


class Command(BaseCommand):
    """
    Import a transfer document (see olympic_warriors.transfer).
    """

    help = "Import an edition JSON document, matching users by username and creating fresh ids."

    def add_arguments(self, parser):
        parser.add_argument("path", help="JSON file written by export_edition.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Run the import, print the report, roll back."
        )
        parser.add_argument(
            "--replace", action="store_true",
            help="Delete an existing edition with the same year first (users are kept).",
        )

    def handle(self, *args, **options):
        with open(options["path"], encoding="utf-8") as src:
            document = json.load(src)

        try:
            with transaction.atomic():
                report = import_edition(document, replace=options["replace"])
                self._print(report)
                if options["dry_run"]:
                    raise DryRun
        except DryRun:
            self.stdout.write(self.style.WARNING("Dry run: rolled back, nothing persisted."))
        except TransferError as exc:
            raise CommandError(str(exc)) from exc
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported edition {report['year']}."))

    def _print(self, report):
        self.stdout.write(f"Edition {report['year']} -> id {report['edition_id']}")
        self.stdout.write(
            f"Users: {report['users_reused']} reused, {report['users_created']} created"
        )
        if report["created_users"]:
            self.stdout.write(
                "  created (set a password in the admin before they can log in): "
                + ", ".join(report["created_users"])
            )
        for table, count in report["counts"].items():
            self.stdout.write(f"  {table:<16} {count}")
        for path in report["missing_files"]:
            self.stdout.write(self.style.WARNING(f"Missing media file: {path}"))
