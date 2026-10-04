"""
Mail every person without an account their claim link (see claim_mailing.py). Run it from the
host once the SMTP settings and PUBLIC_URL are in place; --dry-run lists who would be mailed.
Safe to run again: whoever has claimed drops out, the others get a fresh link.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from olympic_warriors import claim_mailing
from olympic_warriors.claims import public_url
from django.core.exceptions import ImproperlyConfigured

REASONS = {
    "staff": "organisateurs",
    "inactive": "comptes désactivés",
    "claimed": "compte déjà activé",
    "no_email": "sans adresse e-mail",
    "invalid_email": "adresse invalide",
    "internal": "adresse olympicwarriors.com",
}


class Command(BaseCommand):
    help = "Mail every person without an account their claim link (--dry-run to list only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="List who would be mailed; send nothing."
        )

    def handle(self, *args, **options):
        try:
            public_url()
        except ImproperlyConfigured as error:
            raise CommandError(f"{error} (set PUBLIC_URL)") from error
        if not settings.MAIL_CAN_SEND:
            raise CommandError("Outgoing mail is not configured (set EMAIL_HOST)")

        plan = claim_mailing.plan()
        for user in plan.recipients:
            self.stdout.write(f"  {user.username} <{user.email.strip()}>")
        for reason, label in REASONS.items():
            if plan.skipped.get(reason):
                self.stdout.write(f"Ignorés ({label}) : {len(plan.skipped[reason])}")
        for address, users in sorted(plan.shared.items()):
            names = ", ".join(u.username for u in users)
            self.stdout.write(
                self.style.WARNING(f"Adresse partagée {address} : {names} (réinitialisation impossible)")
            )
        if options["dry_run"]:
            self.stdout.write(f"{len(plan.recipients)} à envoyer (dry run, rien envoyé).")
            return

        sent, failed = claim_mailing.send(plan.recipients)
        self.stdout.write(f"{sent} envoyé(s), {failed} échec(s).")
        if failed:
            self.stderr.write(self.style.ERROR(f"{failed} échec(s) : voir le journal du serveur."))
