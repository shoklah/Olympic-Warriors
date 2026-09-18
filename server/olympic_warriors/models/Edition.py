import logging

import pandas as pd

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.crypto import get_random_string

from ..registration import EMAIL, NAME, RATINGS, compute_ratings, parse_name, resolve_columns
from .Player import Player, PlayerRating

FALLBACK_EMAIL_DOMAIN = "olympicwarriors.com"

logger = logging.getLogger(__name__)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place.
    """

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_form = models.FileField(upload_to="registration_forms/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.year} - {self.host}"

    def create_players_from_registration_form(self, registration_form):
        """
        Create or update users, players and skill ratings from the registration form.

        The whole import runs in one transaction: a bad row leaves nothing written.

        :param registration_form: file-like CSV export of the Google Form.
        :raises ValueError: on missing columns, invalid ratings, or a blank name.
        """
        # After Django stores an upload the pointer sits at end-of-file; rewind
        # so pandas sees the header. Plain file objects passed by callers are
        # rewound too, which is harmless.
        if hasattr(registration_form, "seek"):
            registration_form.seek(0)
        df = pd.read_csv(registration_form)
        columns = resolve_columns(df)
        if EMAIL not in columns:
            logger.warning(
                "Registration form for edition %s has no email column; "
                "generated @%s addresses will be used.",
                self,
                FALLBACK_EMAIL_DOMAIN,
            )
        df = compute_ratings(df, columns)

        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    first_name, last_name, username = parse_name(row[NAME])
                except ValueError as exc:
                    raise ValueError(f"Registration form line {index + 2}: {exc}") from exc

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

                player, _ = Player.objects.get_or_create(
                    user=user, edition=self, defaults={"rating": row["Global_Rating"]}
                )

                for name, spec in RATINGS.items():
                    PlayerRating.objects.update_or_create(
                        player=player,
                        identifier=spec["id"],
                        defaults={"name": name, "rating": row[name]},
                    )

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
            if new_registration_form != getattr(original_obj, "registration_form"):
                super().save(*args, **kwargs)
                self.create_players_from_registration_form(new_registration_form)
                # The row is already written; saving again would replay the
                # caller's flags (Edition.objects.create passes force_insert=True,
                # which would re-INSERT the same pk).
                return
        elif self.registration_form:
            super().save(*args, **kwargs)
            self.create_players_from_registration_form(self.registration_form)
            return

        # Call the original save method to save the object
        super().save(*args, **kwargs)
