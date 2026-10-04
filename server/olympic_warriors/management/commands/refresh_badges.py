"""
Recompute every computed badge and each person's progress toward the badges whose rule is a
count, and store the difference. The host crontab runs it daily with --if-due, which
refreshes only the morning after an edition ends or once the last refresh is 30 days old
(see CLAUDE.md, "Player badges").
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from olympic_warriors.badges import refresh, refresh_due
from olympic_warriors.models import Edition
from olympic_warriors.profiles import PARIS, paris_today


class Command(BaseCommand):
    help = (
        "Recompute every computed badge and the badge progress, and store the difference "
        "(the daily cron job runs it with --if-due)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-due",
            action="store_true",
            help="Refresh only when an edition has ended since the last refresh, or the last "
            "refresh is 30 days old (badges.refresh_due); otherwise write nothing.",
        )

        parser.add_argument(
            "--verbose-rows",
            action="store_true",
            help="List every badge added and removed (user, code, edition year, tier).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute and report the difference, then roll everything back.",
        )

    def describe(self, row, sign):
        user = row.user if row.user_id else None
        name = f"{user.first_name} {user.last_name}".strip() if user else row.user_id
        year = row.edition.year if row.edition_id else "?"
        extra = f" tier {row.tier}" if row.tier else ""
        extra += f" [{row.discipline}]" if row.discipline else ""
        self.stdout.write(f"  {sign} {name} ({row.user_id}): {row.code} @ {year}{extra}")

    def handle(self, *args, **options):
        today = paris_today()
        if options["if_due"]:
            due, refreshed_at = refresh_due(today)
            if not due:
                last = timezone.localtime(refreshed_at, PARIS)
                self.stdout.write(
                    f"Nothing to refresh (last refresh {last:%Y-%m-%d %H:%M} Paris time)."
                )
                return
        with transaction.atomic():
            report = refresh(today)
            if options["dry_run"]:
                transaction.set_rollback(True)
        if options["verbose_rows"]:
            for row in report.added_rows:
                row.user = User.objects.get(pk=row.user_id)
                row.edition = Edition.objects.get(pk=row.edition_id)
                self.describe(row, "+")
            for row in report.removed_rows:
                self.describe(row, "-")
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing was stored.")
        self.stdout.write(
            f"Badges: {report.added} added, {report.removed} removed, {report.kept} kept. "
            f"Progress rows: {report.progress} written. "
            f"Refreshed at {report.refreshed_at.isoformat()}."
        )
