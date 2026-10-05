import logging

import pandas as pd

from django.core.exceptions import MultipleObjectsReturned
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.crypto import get_random_string

from ..registration import (
    CONFIRMED,
    EMAIL,
    FREQUENCY,
    GLOBAL_LEVEL,
    IMPORTED_SPORT,
    NAME,
    SPORTS,
    WISHES,
    clean_text,
    compute_ratings,
    parse_confirmation,
    parse_frequency,
    parse_name,
    resolve_columns,
    resolve_extras,
)
from .Player import Player, PlayerRating, PlayerSport

FALLBACK_EMAIL_DOMAIN = "olympicwarriors.com"

logger = logging.getLogger(__name__)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place.
    """

    year = models.IntegerField(
        unique=True, validators=[MinValueValidator(2020), MaxValueValidator(2030)]
    )
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    photos_url = models.URLField(blank=True, null=True)
    # False while the dates are provisional (an edition created early so players can
    # register): the hub then hides the date range and the countdown.
    dates_confirmed = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.year} - {self.host}"

    @property
    def ranking_is_manual(self) -> bool:
        """
        True when an active team of the edition carries a final_rank: the edition
        ranking is then that stored order, and totals are not shown.
        """
        return self.team_set.filter(is_active=True, final_rank__isnull=False).exists()

    def create_players_from_registration_form(self, registration_form):
        """
        Create or update users, players and skill ratings from the registration form.

        The whole import runs in one transaction: a bad row leaves nothing written.
        Re-importing overwrites ``Player.rating`` and every ``PlayerRating`` of the
        listed participants, including values edited by hand in the admin.

        :param registration_form: file-like CSV export of the Google Form.
        :raises ValueError: on missing columns, invalid ratings, or a blank name.
        """
        # After Django stores an upload the pointer sits at end-of-file; rewind
        # so pandas sees the header. Plain file objects passed by callers are
        # rewound too, which is harmless.
        if hasattr(registration_form, "seek"):
            registration_form.seek(0)
        df = pd.read_csv(registration_form)
        columns, ratings = resolve_columns(df)
        extras = resolve_extras(df)
        if EMAIL not in columns:
            logger.warning(
                "Registration form for edition %s has no email column; "
                "generated @%s addresses will be used.",
                self,
                FALLBACK_EMAIL_DOMAIN,
            )
        df = compute_ratings(df, columns, ratings)

        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    first_name, last_name, username = parse_name(row[NAME])
                except ValueError as exc:
                    # 1-based spreadsheet row, header is row 1
                    raise ValueError(f"Registration form row {index + 2}: {exc}") from exc

                email = row.get(EMAIL)
                email = email.strip() if isinstance(email, str) else ""

                user = User.objects.filter(username=username).first()
                if user is None:
                    user = User.objects.create_user(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        password=get_random_string(length=8),
                        email=email or f"{username}@{FALLBACK_EMAIL_DOMAIN}",
                    )
                elif email and user.email.endswith(f"@{FALLBACK_EMAIL_DOMAIN}"):
                    user.email = email
                    user.save(update_fields=["email"])

                try:
                    defaults = {
                        "rating": round(row["Global_Rating"]),
                        "global_level": round(row[GLOBAL_LEVEL]),
                        "is_active": True,
                    }
                    if FREQUENCY in extras:
                        defaults["sport_frequency"] = parse_frequency(row[extras[FREQUENCY]])
                    if WISHES in extras:
                        defaults["team_wishes"] = clean_text(row[extras[WISHES]])
                    if CONFIRMED in extras:
                        defaults["attendance_confirmed"] = parse_confirmation(
                            row[extras[CONFIRMED]]
                        )
                    player, _ = Player.objects.update_or_create(
                        user=user, edition=self, defaults=defaults
                    )
                    history = clean_text(row[extras[SPORTS]]) if SPORTS in extras else ""
                    if history:
                        # filter().first(), not update_or_create: an organiser may have
                        # added a second row of that name, which is no reason to fail.
                        imported = PlayerSport.objects.filter(
                            player=player, sport=IMPORTED_SPORT
                        ).first()
                        if imported is None:
                            PlayerSport.objects.create(
                                player=player, sport=IMPORTED_SPORT, notes=history
                            )
                        else:
                            imported.notes = history
                            imported.save(update_fields=["notes"])
                    for name, spec in ratings.items():
                        PlayerRating.objects.update_or_create(
                            player=player,
                            identifier=spec["id"],
                            defaults={"name": name, "rating": row[name], "is_active": True},
                        )
                except MultipleObjectsReturned as exc:
                    # Editions imported before ratings were update-or-created may
                    # hold duplicate (player, identifier) rows.
                    raise ValueError(
                        f"Duplicate player or rating rows already exist for {username!r}; "
                        "remove them in the admin before re-importing."
                    ) from exc

    def save(self, *args, **kwargs):
        """
        Override the save method to create players from the registration form of the edition.
        """
        # Check if the object is already in the database
        if self.pk is not None:
            # Get the original object from the database
            original_obj = Edition.objects.get(pk=self.pk)
            # Compare registration from to see if it has been updated
            new_registration_form = getattr(self, "registration_form")
            if new_registration_form and new_registration_form != getattr(
                original_obj, "registration_form"
            ):
                # The Edition row and its import share one transaction: a bad
                # form leaves neither a row nor half the players behind.
                with transaction.atomic():
                    super().save(*args, **kwargs)
                    self.create_players_from_registration_form(new_registration_form)
                # The row is already written; saving again would replay the
                # caller's flags.
                return
        elif self.registration_form:
            with transaction.atomic():
                super().save(*args, **kwargs)
                self.create_players_from_registration_form(self.registration_form)
            # Same reason as above; here Edition.objects.create passes
            # force_insert=True, which a second save would replay as a
            # duplicate INSERT of the same pk.
            return

        # Call the original save method to save the object
        super().save(*args, **kwargs)


def latest_edition():
    """
    The active edition with the highest year: the only one the site may edit. None when
    there is no edition at all.
    """
    return Edition.objects.filter(is_active=True).order_by("-year").first()
