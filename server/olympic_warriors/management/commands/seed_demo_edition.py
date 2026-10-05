"""
Seeds a demo edition (year 2040) filled with the real players of an existing edition, to try
the team builder locally. Never touches the source edition or its users.
"""

import secrets
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from olympic_warriors.models import (
    Darts, Edition, Petanque, Player, PlayerRating, PlayerSport, RegistrationSkill, Relay,
)
from olympic_warriors import registration
from olympic_warriors.demo_seed import WISH_LIMIT, load_seed, read_form, seed_path
from olympic_warriors.models.Player import SportFrequency

DEMO_YEAR = 2040
SOURCE_YEAR = 2026
PREFIX = "demo-"
PASSWORD = "demo-password"

INCOMPLETE = 2  # the last players get no per-skill ratings and no frequency
FREQUENCIES = [f.value for f in SportFrequency]
LEVELS = ["fun", "informal", "club", "league", "regional"]
SPORTS = ["Football", "Judo", "Tennis", "Natation", "Escalade", "Rugby", "Basket"]
# What a player says about each sport, by sport: the position or the standing the form's notes field takes.
NOTES = {
    "Football": "Milieu", "Judo": "Ceinture marron", "Tennis": "Classé 30/1", "Natation": "Nage libre",
    "Escalade": "Bloc, 6b", "Rugby": "Troisième ligne", "Basket": "Meneur",
}
DIETARY = ["Végétarien", "Sans gluten", "Sans porc", "Allergie aux arachides"]
HELP = (
    "Seeds a demo edition (2040) with the real players of an existing edition (--from-year, "
    "default 2026) to try the team builder. With a demo seed (server/demo-seed.json, built from "
    "a registration form by build_demo_seed) the players' frequency, sports history, wishes and "
    "missing global level are the real ones, matched by name; without one, or with --generate, "
    "they are generated as below. Copied from the source: the people (same users), "
    "rating, global level, per-skill ratings and the questionnaire skills; a player with no "
    "global level (an edition imported from a CSV) gets the one the form's formula would give "
    "for their skills and rating. Generated, deterministically and coherent with each other "
    "and with the form's answers: sport frequency (following the rating), sports (level and "
    "practice following the frequency, duration, notes), dietary restrictions, and the "
    "team_with / team_avoid texts built from the roster's names, worded like the real form's "
    "answers (two players are left "
    "incomplete: no per-skill ratings, frequency or sports, like a legacy import)."
)


def full_name(player):
    return f"{player.user.first_name} {player.user.last_name}"


def global_level_for(rating, skills, weights):
    """
    The global answer (1..10) a player would have given: the whole number whose blend with their
    skills, through the form's own formula, rounds to their rating (the nearest to the rating
    when several do). Without every skill rated, the rating itself.
    """
    if not weights or any(key not in skills for key in weights):
        return rating
    return min(
        range(1, 11),
        key=lambda g: (abs(round(registration.rate(skills, weights, g)[1]) - rating), abs(g - rating)),
    )


def activity(rating, index):
    """0 to 4, an index into FREQUENCIES: the sport a player does follows their rating, with a spread."""
    return min(max(round((rating - 1) * 4 / 9) + index % 3 - 1, 0), len(FREQUENCIES) - 1)


def sports_for(index, level):
    """
    [(sport, level, practice, duration_months, notes)] of a player of activity `level`: someone who
    does little sport lists past sports they no longer practise, and only an active player
    practises regularly, at the highest level reached.
    """
    count = index % 3 + (1 if level >= 2 else 0)
    rows = []
    for n in range(min(count, 3)):
        sport = SPORTS[(index + 3 * n) % len(SPORTS)]
        if n == 0:
            practice = ["no_longer", "no_longer", "occasionally", "regularly", "regularly"][level]
        else:
            practice = "occasionally" if (index + n) % 2 == 0 else "no_longer"
        rows.append((
            sport,
            LEVELS[min(max(level + index % 2 - n, 0), len(LEVELS) - 1)],
            practice,
            12 * (1 + (index + n) % 10) + (index + 3 * n) % 12,
            NOTES[sport] if (index + n) % 2 == 0 else "",
        ))
    return rows


def with_typo(first_name):
    """The first name with one letter changed."""
    position = len(first_name) // 2
    letter = "a" if first_name[position].lower() != "a" else "e"
    return first_name[:position] + letter + first_name[position + 1:]


def wishes(players):
    """
    {player index: (team_with, team_avoid)} over the roster sorted by name, worded the way the
    real form's answers are (first names, full names, nicknames and typos, lists over several
    lines, « peu importe », names of people who are not players, emoji, a mix of both wishes)
    and covering what the builder's name matcher must handle. Wishers are the first players,
    their targets come from the end, so reruns on one roster are identical.
    """
    n = len(players)
    firsts = [p.user.first_name for p in players]
    unique = [i for i in range(n) if firsts.count(firsts[i]) == 1]
    shared = [f for f in dict.fromkeys(firsts) if firsts.count(f) > 1]
    result = {}

    def target(k, offset=0):
        index = (n - 1 - k - offset) % n
        return index if index != k else None

    def name_of(k, offset=0, first=False):
        index = target(k, offset)
        if index is None:
            return None
        return firsts[index] if first else full_name(players[index])

    def put(k, with_=None, avoid=None):
        if k < n:
            result[k] = ((with_ or "")[:WISH_LIMIT], (avoid or "")[:WISH_LIMIT])

    # A mutual pair by full name.
    if n >= 2:
        put(0, f"Avec {full_name(players[1])} !")
        put(1, f"Être en équipe avec {full_name(players[0])}")
    # A unique first name only, or a member of the organisation.
    pool = [i for i in reversed(unique) if i > 2]
    if pool:
        put(2, f"Avec {firsts[pool[0]]} ! Ou un membre du Comité")
    # The ambiguous case: a first name two players share.
    if shared:
        put(3, f"Je voudrais être avec {shared[0]} si possible svp 😁")
    # A one-typo first name.
    if len(pool) > 1:
        put(4, f"{with_typo(firsts[pool[1]])} ")
    # A list over several lines, one of them with a comment.
    if n >= 8 and target(5) is not None and target(6) is not None:
        put(5, f"{name_of(5, first=True)} \n{name_of(6)} \n{name_of(5, 2, first=True) or name_of(6, 2, first=True)} (pour le ❤️)")
    # No preference, or one with a name nobody has, or both of them at once.
    put(6, f"Peu importe / {name_of(6, first=True)}" if target(6) is not None else "Peu importe")
    put(7, f"Antoine Dupont si il est là, sinon je me contenterais de {name_of(7, first=True) or 'Sarah'}")
    put(8, "M'en fous (mais svp prenez en compte le fait que je ne sais pas du tout jouer au volley)")
    # Two « à éviter » asks, one of them naming two people and giving a general answer.
    if target(9) is not None:
        put(9, None, f"Ne pas être avec {name_of(9)}")
    if target(10) is not None and target(10, 1) is not None:
        put(10, None, f"Ne pas être avec {name_of(10, first=True)} ou {name_of(10, 1, first=True)}. Le reste pas de préférence")
    # Both wishes at once, as the in-app form takes them, and a wish with no name in it.
    if target(11) is not None and target(11, 1) is not None:
        put(11, f"Idéalement, je souhaiterai être avec {name_of(11).upper()}", f"Pas avec {name_of(11, 1, first=True)}")
    put(12, "Pas de personne en particulier, mais je veux bien être avec des gens « chill » (je ne veux pas être le boulet de ceux qui ont la gagne à tout prix 😅)")
    put(13, "Une petite préférence avec les premiers participants des olympiades")
    return result


class Command(BaseCommand):
    """
    Seeds (or with --remove, deletes) the demo edition. DEBUG, or STAGE_DEMO on the staging server.
    """

    help = HELP

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove", action="store_true",
            help="Delete edition 2040 (and its players' rows) and the demo- users; real users stay.",
        )
        parser.add_argument(
            "--form", metavar="PATH",
            help="Registration form CSV (read only), read directly instead of the demo seed; "
            "players without a row stay blank.",
        )
        parser.add_argument(
            "--generate", action="store_true",
            help="Generate every answer even when a demo seed exists.",
        )
        parser.add_argument(
            "--from-year", type=int, default=SOURCE_YEAR,
            help=f"Edition whose players fill the demo (default {SOURCE_YEAR}).",
        )

    def handle(self, *args, **options):
        if not (settings.DEBUG or settings.STAGE_DEMO):
            raise CommandError("seed_demo_edition only runs with DEBUG or STAGE_DEMO on.")
        if options["remove"]:
            self.remove()
        else:
            self.create(options["from_year"], options["form"], options["generate"])

    def remove(self):
        with transaction.atomic():
            editions = Edition.objects.filter(year=DEMO_YEAR).delete()[0]
            users = User.objects.filter(username__startswith=PREFIX).delete()[0]
        self.stdout.write(f"Removed {editions} rows for edition {DEMO_YEAR}, {users} rows for the demo users.")

    def create(self, from_year, form=None, generate=False):
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
        label = form
        if form:
            form_rows = read_form(form)
        elif generate or not seed_path().exists():
            form_rows = None
        else:
            label = seed_path()
            form_rows = load_seed(label)
        matched = 0
        weights = {s.identifier: s.weight for s in source.registrationskill_set.filter(is_active=True)}
        wished = {} if form_rows is not None else wishes(sources)
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

            # The fixed password is for a local DEBUG database only: staging holds a copy of
            # prod's data on a public host, so its demo admin gets a random one, shown once.
            password = PASSWORD if settings.DEBUG else secrets.token_urlsafe(16)
            User.objects.create_superuser(
                username=f"{PREFIX}admin", password=password, email="demo-admin@example.com",
                first_name="Demo", last_name="Admin",
            )
            for index, old in enumerate(sources):
                incomplete = form_rows is None and index >= len(sources) - INCOMPLETE
                team_with, team_avoid = wished.get(index, ("", ""))
                level = activity(old.rating, index)
                frequency = "" if incomplete else FREQUENCIES[level]
                history = ""
                entry = None
                if form_rows is not None:
                    frequency = ""
                    entry = form_rows.get(registration.parse_name(full_name(old))[2])
                    if entry:
                        matched += 1
                        frequency, history, team_with, team_avoid = entry[:4]
                rating, global_level = old.rating, old.global_level
                if global_level is None and entry and entry.global_level:
                    global_level = entry.global_level
                if global_level is None:
                    skills = {
                        r.identifier: r.rating
                        for r in PlayerRating.objects.filter(player=old, is_active=True)
                    }
                    global_level = global_level_for(rating, skills, weights)
                    if weights and all(key in skills for key in weights):
                        rating = round(registration.rate(skills, weights, global_level)[1])
                player = Player.objects.create(
                    user=old.user, edition=edition, rating=rating,
                    global_level=global_level, attendance_confirmed=True,
                    sport_frequency=frequency,
                    team_with=team_with, team_avoid=team_avoid,
                    dietary_restrictions="" if form_rows is not None or index % 6 else DIETARY[index // 6 % len(DIETARY)],
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
                elif form_rows is not None:
                    if history:
                        PlayerSport.objects.create(
                            player=player, sport=registration.IMPORTED_SPORT, notes=history
                        )
                elif not incomplete:
                    PlayerSport.objects.bulk_create(
                        PlayerSport(
                            player=player, order=n, sport=sport, level=sport_level,
                            practice=practice, duration_months=months, notes=notes,
                        )
                        for n, (sport, sport_level, practice, months, notes) in enumerate(
                            sports_for(index, level)
                        )
                    )
        self.stdout.write(
            f"Demo edition {DEMO_YEAR} created with the {len(sources)} players of {from_year} (no teams)."
        )
        if form_rows is not None:
            self.stdout.write(
                f"Answers of {label}: {matched} players matched to a form row, {len(sources) - matched} not "
                "(left blank). Nothing generated."
            )
        else:
            self.stdout.write(
                "Copied: users, rating, global level (derived when the source has none), skills ratings. "
                "Generated: frequency, sports, dietary restrictions, team wishes."
            )
        self.stdout.write(f"Admin: {PREFIX}admin / {password}")
        front = (settings.PUBLIC_URL or "http://localhost:5173").rstrip("/")
        self.stdout.write(f"Team builder: {front}/{DEMO_YEAR}/builder")
        self.stdout.write("Remove: docker compose exec server python manage.py seed_demo_edition --remove")
