"""
Seeds a demo edition (year 2040) filled with the real players of an existing edition, to try
the team builder locally. Never touches the source edition or its users.
"""

from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from olympic_warriors.models import (
    Darts, Edition, Petanque, Player, PlayerRating, PlayerSport, RegistrationSkill, Relay,
)
from olympic_warriors.models.Player import SportFrequency

DEMO_YEAR = 2040
SOURCE_YEAR = 2026
PREFIX = "demo-"
PASSWORD = "demo-password"
FRONT_URL = f"http://localhost:5173/{DEMO_YEAR}/builder"

INCOMPLETE = 2  # the last players get no per-skill ratings and no frequency
FREQUENCIES = [f.value for f in SportFrequency]
LEVELS = ["fun", "informal", "club", "league", "regional"]
SPORTS = ["Football", "Judo", "Tennis", "Natation", "Escalade", "Rugby", "Basket"]
PRACTICES = ["no_longer", "occasionally", "regularly"]
HELP = (
    "Seeds a demo edition (2040) with the real players of an existing edition (--from-year, "
    "default 2026) to try the team builder. Copied from the source: the people (same users), "
    "rating, global level, per-skill ratings and the questionnaire skills. Generated, "
    "deterministically: sport frequency, sports, and the team_with / team_avoid texts built "
    "from the roster's names (two players are left incomplete)."
)


def full_name(player):
    return f"{player.user.first_name} {player.user.last_name}"


def with_typo(first_name):
    """The first name with one letter changed."""
    position = len(first_name) // 2
    letter = "a" if first_name[position].lower() != "a" else "e"
    return first_name[:position] + letter + first_name[position + 1:]


def wishes(players):
    """
    {player index: (team_with, team_avoid)} over the roster sorted by name. Wishers are the
    first players, their targets come from the end, so reruns on one roster are identical.
    """
    n = len(players)
    firsts = [p.user.first_name for p in players]
    unique = [i for i in range(n) if firsts.count(firsts[i]) == 1]
    shared = [f for f in dict.fromkeys(firsts) if firsts.count(f) > 1]
    result = {}

    def target(k):
        index = (n - 1 - k) % n
        return index if index != k else None

    def put(k, with_=None, avoid=None):
        if k < n:
            result[k] = (with_ or "", avoid or "")

    # A mutual pair by full name.
    if n >= 2:
        put(0, full_name(players[1]))
        put(1, full_name(players[0]))
    # A unique first name only.
    pool = [i for i in reversed(unique) if i > 2]
    if pool:
        put(2, firsts[pool[0]])
    # The ambiguous case: a first name two players share.
    if shared:
        put(3, shared[0])
    # A one-typo first name.
    if len(pool) > 1:
        put(4, with_typo(firsts[pool[1]]))
    # A comma list of two names.
    if n >= 8 and target(5) is not None and target(6) is not None:
        put(5, f"{full_name(players[target(5)])}, {full_name(players[target(6)])}")
    put(6, "peu importe")
    put(7, "Quelqu'un d'inconnu")
    # Two « à éviter » pairs.
    for k in (9, 10):
        if target(k) is not None and k < n:
            put(k, None, full_name(players[target(k)]))
    return result


class Command(BaseCommand):
    """
    Seeds (or with --remove, deletes) the demo edition. DEBUG only.
    """

    help = HELP

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove", action="store_true",
            help="Delete edition 2040 (and its players' rows) and the demo- users; real users stay.",
        )
        parser.add_argument(
            "--from-year", type=int, default=SOURCE_YEAR,
            help=f"Edition whose players fill the demo (default {SOURCE_YEAR}).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_edition only runs with DEBUG on.")
        if options["remove"]:
            self.remove()
        else:
            self.create(options["from_year"])

    def remove(self):
        with transaction.atomic():
            editions = Edition.objects.filter(year=DEMO_YEAR).delete()[0]
            users = User.objects.filter(username__startswith=PREFIX).delete()[0]
        self.stdout.write(f"Removed {editions} rows for edition {DEMO_YEAR}, {users} rows for the demo users.")

    def create(self, from_year):
        if (
            Edition.objects.filter(year=DEMO_YEAR).exists()
            or User.objects.filter(username__startswith=PREFIX).exists()
        ):
            raise CommandError("The demo already exists: run with --remove first.")
        source = Edition.objects.filter(year=from_year).first()
        if source is None:
            raise CommandError(f"Edition {from_year} does not exist.")
        sources = list(
            Player.objects.filter(edition=source, is_active=True, user__is_active=True)
            .select_related("user")
            .order_by("user__last_name", "user__first_name", "id")
        )
        if not sources:
            raise CommandError(f"Edition {from_year} has no active players.")
        wished = wishes(sources)
        with transaction.atomic():
            edition = Edition.objects.create(
                year=DEMO_YEAR,
                host="Demo",
                start_date=date(DEMO_YEAR, 9, 14),
                end_date=date(DEMO_YEAR, 9, 15),
                registration_opens=date.today() - timedelta(days=1),
            )
            RegistrationSkill.objects.bulk_create(
                RegistrationSkill(
                    edition=edition, identifier=s.identifier, name_fr=s.name_fr,
                    name_en=s.name_en, weight=s.weight, order=s.order,
                )
                for s in source.registrationskill_set.filter(is_active=True)
            )
            Relay.objects.create(edition=edition)
            darts = Darts.objects.create(edition=edition)
            Petanque.objects.create(edition=edition)
            # Set after creation so no round exists: the builder's Apply reports it « to schedule ».
            type(darts).objects.filter(pk=darts.pk).update(pairing_system="RR")

            User.objects.create_superuser(
                username=f"{PREFIX}admin", password=PASSWORD, email="demo-admin@example.com",
                first_name="Demo", last_name="Admin",
            )
            for index, old in enumerate(sources):
                incomplete = index >= len(sources) - INCOMPLETE
                team_with, team_avoid = wished.get(index, ("", ""))
                player = Player.objects.create(
                    user=old.user, edition=edition, rating=old.rating,
                    global_level=old.global_level, attendance_confirmed=True,
                    sport_frequency="" if incomplete else FREQUENCIES[index % len(FREQUENCIES)],
                    team_with=team_with, team_avoid=team_avoid,
                )
                if not incomplete:
                    PlayerRating.objects.bulk_create(
                        PlayerRating(player=player, name=r.name, identifier=r.identifier, rating=r.rating)
                        for r in PlayerRating.objects.filter(player=old, is_active=True)
                    )
                real = list(PlayerSport.objects.filter(player=old).order_by("order", "id"))
                if real:
                    PlayerSport.objects.bulk_create(
                        PlayerSport(
                            player=player, order=s.order, sport=s.sport, level=s.level,
                            practice=s.practice, duration_months=s.duration_months, notes=s.notes,
                        )
                        for s in real
                    )
                elif index % 3 == 0 and not incomplete:
                    PlayerSport.objects.bulk_create(
                        PlayerSport(
                            player=player, order=n, sport=SPORTS[(index + n) % len(SPORTS)],
                            level=LEVELS[(index + 2 * n) % len(LEVELS)],
                            practice=PRACTICES[(index + n) % 3],
                            duration_months=6 + 12 * ((index + n) % 8),
                        )
                        for n in range(1 + index % 2)
                    )
        self.stdout.write(
            f"Demo edition {DEMO_YEAR} created with the {len(sources)} players of {from_year} (no teams)."
        )
        self.stdout.write("Copied: users, rating, global level, skills ratings. Generated: frequency, sports, team wishes.")
        self.stdout.write(f"Admin: {PREFIX}admin / {PASSWORD}")
        self.stdout.write(f"Team builder: {FRONT_URL}")
        self.stdout.write("Remove: docker compose exec server python manage.py seed_demo_edition --remove")
