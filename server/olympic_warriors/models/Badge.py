from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q


class Badge(models.Model):
    """
    A badge a person earned: computed by olympic_warriors.badges (is_manual False, rebuilt
    by badges.refresh()) or given by hand in the admin (is_manual True, never touched by the
    refresh). See the player badges design spec under docs/superpowers/specs/.
    """

    class Codes(models.TextChoices):
        """The catalogue, in catalogue order: the profile lists badges in this order. The
        front mirrors it in front/src/lib/badges.js (BADGE_CODES in badges.test.js)."""

        # Edition places
        CHAMPION = "champion", "Champion"
        RUNNER_UP = "runner-up", "Dauphin"
        BRONZE = "bronze", "Bronze"
        CHOCOLATE = "chocolate", "Médaille en chocolat"
        WOODEN_SPOON = "wooden-spoon", "Cuillère de bois"
        # Streaks and career
        BACK_TO_BACK = "back-to-back", "Doublé"
        THREEPEAT = "threepeat", "Triplé"
        DYNASTY = "dynasty", "Dynastie"
        PHOENIX = "phoenix", "Phénix"
        LEGEND = "legend", "Légende"
        PODIUM_REGULAR = "podium-regular", "Abonné au podium"
        FULL_SET = "full-set", "Collection complète"
        ETERNAL_SECOND = "eternal-second", "Poulidor"
        JANUS = "janus", "Janus"
        COMEBACK = "comeback", "Remontada"
        ON_THE_RISE = "on-the-rise", "Ascension"
        ICARUS = "icarus", "Icare"
        LUCKY_CHARM = "lucky-charm", "Porte-bonheur"
        # Loyalty
        ROOKIE = "rookie", "Bizut"
        VETERAN = "veteran", "Vétéran"
        ARGONAUT = "argonaut", "Argonaute"
        EVER_PRESENT = "ever-present", "Pénélope"
        HOMECOMING = "homecoming", "Ulysse"
        # Teammates
        COMRADES = "comrades", "Compagnons d'armes"
        NETWORKER = "networker", "Rassembleur"
        # Hall of fame (the all-time table)
        GOAT = "goat", "G.O.A.T"
        ALONE_AT_THE_TOP = "alone-at-the-top", "Seul au sommet"
        HALL_OF_FAME_PODIUM = "hall-of-fame-podium", "Podium du panthéon"
        HALL_OF_FAMER = "hall-of-famer", "Entrée au panthéon"
        REIGN = "reign", "Règne"
        KINGSLAYER = "kingslayer", "Régicide"
        ROCKET = "rocket", "Fusée"
        # Disciplines
        SPECIALIST = "specialist", "Spécialiste"
        MASTER = "master", "Maître"
        ALL_ROUNDER = "all-rounder", "Touche-à-tout"
        DECATHLETE = "decathlete", "Décathlonien"
        BRAINS_AND_BRAWN = "brains-and-brawn", "Tête et jambes"
        CLEAN_SWEEP = "clean-sweep", "Razzia"
        METRONOME = "metronome", "Métronome"
        UNCROWNED = "uncrowned", "Sans couronne"
        PHOTO_FINISH = "photo-finish", "Photo-finish"
        # The gods (a discipline family each) and Mount Olympus
        ATHENA = "athena", "Athéna"
        APOLLO = "apollo", "Apollon"
        ARTEMIS = "artemis", "Artémis"
        HERMES = "hermes", "Hermès"
        HERACLES = "heracles", "Héraclès"
        THESEUS = "theseus", "Thésée"
        ARES = "ares", "Arès"
        HADES = "hades", "Hadès"
        DIONYSUS = "dionysus", "Dionysos"
        OLYMPUS = "olympus", "Olympe"
        # Games
        UNBEATEN = "unbeaten", "Invaincu"
        PERFECT_RUN = "perfect-run", "Sans faute"
        SHUTOUT = "shutout", "Cadenas"
        STEAMROLLER = "steamroller", "Rouleau compresseur"
        PERFECT_PITCH = "perfect-pitch", "Oreille absolue"
        # Given by hand
        MVP = "mvp", "MVP"
        FAIR_PLAY = "fair-play", "Fair-play"
        HYPE = "hype", "Ambianceur"
        COSTUME = "costume", "Plus beau déguisement"
        WOUNDED = "wounded", "Blessé de guerre"
        TORCHBEARER = "torchbearer", "Porteur de flamme"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    code = models.CharField(max_length=32, choices=Codes.choices)
    # The edition the badge was earned at: the one that completed it.
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    # 0 for an untiered badge, 1 to 3 (bronze, silver, gold) for a tiered one.
    tier = models.PositiveSmallIntegerField(default=0)
    # The discipline name, for specialist, master, unbeaten, perfect-run and steamroller.
    discipline = models.CharField(max_length=100, blank=True, default="")
    # The other person, for comrades.
    partner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    is_manual = models.BooleanField(default=False)
    # An organiser's memo on a badge given by hand; never public.
    note = models.CharField(max_length=200, blank=True)
    # Clearing it revokes a badge; the refresh keeps a revoked computed row inactive.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Django 4.2 has no nulls_distinct: rows without a partner stay unique through
            # the refresh's diff, not through this constraint.
            models.UniqueConstraint(
                fields=["user", "code", "edition", "tier", "discipline", "partner"],
                condition=Q(is_manual=False),
                name="badge_unique_computed",
            )
        ]

    def __str__(self):
        return f"{self.get_code_display()} - {self.user} ({self.edition.year})"


# The badges organisers give by hand; the refresh never computes them.
MANUAL_CODES = frozenset(
    {
        Badge.Codes.MVP,
        Badge.Codes.FAIR_PLAY,
        Badge.Codes.HYPE,
        Badge.Codes.COSTUME,
        Badge.Codes.WOUNDED,
        Badge.Codes.TORCHBEARER,
    }
)


class BadgeRefresh(models.Model):
    """
    The one row (pk 1, created by migration 0033) that badges.refresh() locks, so that a
    cron run and an admin action run one after the other, and stamps when a run finishes.
    Not in the admin.
    """

    refreshed_at = models.DateTimeField(null=True, blank=True)
