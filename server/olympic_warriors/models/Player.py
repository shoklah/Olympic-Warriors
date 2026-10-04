from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator


class SportFrequency(models.TextChoices):
    """How often a player does sport: the five answers of the registration form."""

    RARE = "rare", "Moins d'une fois par mois"
    MONTHLY = "monthly", "Moins d'une fois par semaine mais plusieurs fois par mois"
    HOUR = "hour", "Environ une heure par semaine"
    TWO_HOURS = "two_hours", "Au moins deux heures par semaine"
    FOUR_HOURS = "four_hours", "Au moins quatre heures par semaine"


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # What the player says at registration. Private: organisers only, never in a public payload.
    global_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Raw global estimate; `rating` blends it, so it cannot be recovered from it.",
    )
    dietary_restrictions = models.TextField(
        blank=True, default="", validators=[MaxLengthValidator(500)]
    )
    sport_frequency = models.CharField(
        max_length=10, choices=SportFrequency.choices, blank=True, default=""
    )
    team_wishes = models.TextField(blank=True, default="", validators=[MaxLengthValidator(1000)])
    attendance_confirmed = models.BooleanField(
        default=False,
        help_text="The player's own tick: paid and will be there. Nothing checks it.",
    )

    def __str__(self) -> str:
        return self.user.first_name + " " + self.user.last_name

    def clean(self):
        """
        Refuse a team of another edition, and a second active row for the same person in
        the same edition. Both errors sit on `team`: it is the one field every admin form
        of a player shows (the changelist, the team inline, the change form), and an
        error on a field the form lacks makes Django raise ValueError instead of showing
        it. Imports insert without clean(), so they are not affected.

        `self.team` (not `team_id`) is the right accessor here: on the TeamAdmin add page
        the inline hands this an unsaved parent team, so `team_id` is still None while
        `team` already carries the edition chosen on the team's own form. For a nullable
        FK, `self.team` returns None cheaply (no query) when nothing is assigned or cached.
        """
        super().clean()
        errors = []
        team = self.team
        if (
            team is not None
            and team.edition_id is not None
            and self.edition_id is not None
            and team.edition_id != self.edition_id
        ):
            errors.append("This team belongs to another edition.")
        if self.is_active and self.user_id is not None and self.edition_id is not None:
            duplicates = Player.objects.filter(
                user_id=self.user_id, edition_id=self.edition_id, is_active=True
            ).exclude(pk=self.pk)
            if duplicates.exists():
                errors.append("This person already has an active player in this edition.")
        if errors:
            raise ValidationError({"team": errors})


class PlayerRating(models.Model):
    """
    A player rating on a specific area, with its name and identifier.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)


class PlayerSport(models.Model):
    """
    One sport a player has practised, as entered at registration. Private.
    """

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Débutant"
        AMATEUR = "amateur", "Amateur"
        CLUB = "club", "Club"
        COMPETITION = "competition", "Compétition"

    class Practice(models.TextChoices):
        NO_LONGER = "no_longer", "Ne pratique plus"
        OCCASIONALLY = "occasionally", "Pratique occasionnelle"
        REGULARLY = "regularly", "Pratique régulière"

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)
    sport = models.CharField(max_length=80)
    level = models.CharField(max_length=12, choices=Level.choices, blank=True, default="")
    practice = models.CharField(max_length=12, choices=Practice.choices, blank=True, default="")
    duration_months = models.PositiveIntegerField(null=True, blank=True)
    # A TextField so the CSV import can keep a whole imported history; the validator guards
    # admin edits and the registration API.
    notes = models.TextField(blank=True, default="", validators=[MaxLengthValidator(200)])

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.sport
