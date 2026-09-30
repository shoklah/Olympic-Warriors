"""
Recompute every computed badge and each person's progress toward the badges whose rule is a
count, and store the difference. The host crontab runs it daily with --if-due, which
refreshes only the morning after an edition ends or once the last refresh is 30 days old
(see CLAUDE.md, "Player badges").
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from olympic_warriors.badges import refresh, refresh_due
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
        report = refresh(today)
        self.stdout.write(
            f"Badges: {report.added} added, {report.removed} removed, {report.kept} kept. "
            f"Progress rows: {report.progress} written. "
            f"Refreshed at {report.refreshed_at.isoformat()}."
        )
