"""
Seeds a demo edition (year 2040) with 24 registered players to try the team builder locally.
"""

from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from olympic_warriors import enrolment, questionnaire
from olympic_warriors.models import (
    Darts, Edition, Petanque, Player, RegistrationSkill, Relay,
)
from olympic_warriors.models.Player import SportFrequency

DEMO_YEAR = 2040
PREFIX = "demo-"
PASSWORD = "demo-password"
FRONT_URL = f"http://localhost:5173/{DEMO_YEAR}/builder"

# (first name, last name, team_with, team_avoid): two Paul, accents, near-identical first
# names (Mathis/Mathias, Sarah/Sara), and wishes exercising every case of the matcher.
PLAYERS = [
    ("Paul", "Durand", "Léa Martin", ""),
    ("Paul", "Lefèvre", "", ""),
    ("Léa", "Martin", "Paul Durand", ""),
    ("Inès", "Moreau", "Camille", ""),
    ("Élodie", "Bernard", "Paul", ""),
    ("Camille", "Petit", "Inès Moreau", ""),
    ("Hugo", "Roux", "Lia", ""),
    ("Mathis", "Girard", "Sarah Blanc, Théo Garnier", ""),
    ("Mathias", "Faure", "peu importe", ""),
    ("Sarah", "Blanc", "Quelqu'un Dinconnu", ""),
    ("Sara", "Lambert", "", ""),
    ("Théo", "Garnier", "Mathis Girard", ""),
    ("Chloé", "Mercier", "Théo Garnier", ""),
    ("Nathan", "Dupont", "", "Manon Fabre"),
    ("Manon", "Fabre", "", ""),
    ("Louis", "André", "", "Jade Rousseau"),
    ("Jade", "Rousseau", "", ""),
    ("Arthur", "Vincent", "", "Zoé Muller"),
    ("Zoé", "Muller", "", ""),
    ("Lucas", "Morel", "", ""),
    ("Anaïs", "Lopez", "", ""),
    ("Maxime", "Gauthier", "", ""),
    ("Emma", "Perrin", "", ""),
    ("Antoine", "Clément", "", ""),
]
INCOMPLETE = 3  # the last players get no per-skill ratings and no frequency
FREQUENCIES = [f.value for f in SportFrequency]
LEVELS = ["fun", "informal", "club", "league", "regional"]
SPORTS = ["Football", "Judo", "Tennis", "Natation", "Escalade", "Rugby", "Basket"]
DIETARY = {2: "Végétarien", 9: "Sans gluten", 15: "Allergie aux arachides"}
DEMO_SKILLS = [
    ("CARD", "Cardio", "Cardio"),
    ("FORC", "Force", "Strength"),
    ("VITE", "Vitesse", "Speed"),
    ("ADRE", "Adresse", "Dexterity"),
    ("STRA", "Stratégie", "Strategy"),
    ("COLL", "Esprit d'équipe", "Teamwork"),
]


def username(number):
    return f"{PREFIX}{number:02d}"


def _answer(index, skills):
    """A plausible registration answer, different strengths per skill, spread over players."""
    base = 3 + (index * 5) % 6
    ratings = {
        skill.identifier: min(10, max(1, base + ((index * 3 + position * 7) % 5) - 2))
        for position, skill in enumerate(skills)
    }
    sports = [
        {
            "sport": SPORTS[(index + n) % len(SPORTS)],
            "level": LEVELS[(index + 2 * n) % len(LEVELS)],
            "practice": ["no_longer", "occasionally", "regularly"][(index + n) % 3],
            "duration_months": 6 + 12 * ((index + n) % 8),
            "notes": "",
        }
        for n in range(index % 4)
    ]
    first, last, team_with, team_avoid = PLAYERS[index]
    return {
        "ratings": ratings,
        "global_level": 2 + (index * 3) % 8,
        "sport_frequency": FREQUENCIES[index % len(FREQUENCIES)],
        "sports": sports,
        "team_with": team_with,
        "team_avoid": team_avoid,
        "dietary_restrictions": DIETARY.get(index, ""),
        "attendance_confirmed": True,
    }


class Command(BaseCommand):
    """
    Seeds (or with --remove, deletes) the demo edition. DEBUG only.
    """

    help = "Seeds a demo edition (2040) with registered players to try the team builder."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove", action="store_true", help="Delete the demo users and edition 2040."
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_edition only runs with DEBUG on.")
        if options["remove"]:
            self.remove()
        else:
            self.create()

    def remove(self):
        with transaction.atomic():
            users = User.objects.filter(username__startswith=PREFIX).delete()[0]
            editions = Edition.objects.filter(year=DEMO_YEAR).delete()[0]
        self.stdout.write(f"Removed {users} rows for the demo users, {editions} rows for edition {DEMO_YEAR}.")

    def create(self):
        if (
            Edition.objects.filter(year=DEMO_YEAR).exists()
            or User.objects.filter(username__startswith=PREFIX).exists()
        ):
            raise CommandError("The demo already exists: run with --remove first.")
        with transaction.atomic():
            edition = Edition.objects.create(
                year=DEMO_YEAR,
                host="Demo",
                start_date=date(DEMO_YEAR, 9, 14),
                end_date=date(DEMO_YEAR, 9, 15),
                registration_opens=date.today() - timedelta(days=1),
            )
            try:
                questionnaire.copy_skills(edition)
            except questionnaire.QuestionnaireError:
                RegistrationSkill.objects.bulk_create(
                    RegistrationSkill(
                        edition=edition, identifier=identifier, name_fr=fr, name_en=en,
                        weight=1, order=order,
                    )
                    for order, (identifier, fr, en) in enumerate(DEMO_SKILLS)
                )
            skills = list(edition.registrationskill_set.filter(is_active=True).order_by("order", "id"))

            Relay.objects.create(edition=edition)
            darts = Darts.objects.create(edition=edition)
            Petanque.objects.create(edition=edition)
            # Set after creation so no round exists: the builder's Apply reports it « to schedule ».
            type(darts).objects.filter(pk=darts.pk).update(pairing_system="RR")

            User.objects.create_superuser(
                username=f"{PREFIX}admin", password=PASSWORD, email="demo-admin@example.com",
                first_name="Demo", last_name="Admin",
            )
            for index, (first, last, _, _) in enumerate(PLAYERS):
                user = User.objects.create_user(
                    username=username(index + 1), password=PASSWORD,
                    email=f"{username(index + 1)}@example.com",
                    first_name=first, last_name=last,
                )
                if index >= len(PLAYERS) - INCOMPLETE:
                    Player.objects.create(
                        user=user, edition=edition, rating=3 + index % 5, attendance_confirmed=True
                    )
                    continue
                cleaned = enrolment.validate(_answer(index, skills), skills, False, user)
                enrolment.save(user, edition, skills, cleaned)
        self.stdout.write(f"Demo edition {DEMO_YEAR} created with {len(PLAYERS)} players (no teams).")
        self.stdout.write(f"Admin: {PREFIX}admin / {PASSWORD} (players {username(1)}..{username(len(PLAYERS))}, same password)")
        self.stdout.write(f"Team builder: {FRONT_URL}")
        self.stdout.write("Remove: docker compose exec server python manage.py seed_demo_edition --remove")
