"""
Recompute every computed badge and store the difference. The nightly host crontab runs it
(see CLAUDE.md, "Player badges").
"""

from django.core.management.base import BaseCommand

from olympic_warriors.badges import refresh


class Command(BaseCommand):
    help = "Recompute every computed badge and store the difference (the nightly cron job)."

    def handle(self, *args, **options):
        report = refresh()
        self.stdout.write(
            f"Badges: {report.added} added, {report.removed} removed, {report.kept} kept. "
            f"Refreshed at {report.refreshed_at.isoformat()}."
        )
